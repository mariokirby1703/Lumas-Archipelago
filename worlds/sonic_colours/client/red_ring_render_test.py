"""Owned Red Ring materials; the shared model resources remain unchanged."""
import math
import struct

from ..world_constants import load_data
from .memory import MemoryUnavailable, valid_range
from .item_colors import LUMA
from .native_read import read_stage_objects, read_actors

ALLOCATION_SITE = 0x801D52E0
ORIGINAL = bytes.fromhex('38a00000')
BUFFERED = bytes.fromhex('38a00900')  # private TEV colors and TEV stages
FORWARD_SITE = 0x800BA5A8
FORWARD_ORIGINAL = bytes.fromhex('38c00000')
FORWARD_BUFFERED = bytes.fromhex('70e60900')  # andi. r6,r7,0x900
ACTOR_VTABLE = 0x8076F8D0
MODEL_VTABLE = 0x807AA950
PALETTE = {'purple': (175, 112, 255), 'blue': (48, 91, 216), 'light_blue': (100, 200, 255),
           'purple_dim': (44, 14, 64), 'gold':(240,228,66), 'accessible_blue':(0,114,178),
           'gray':(153,153,153), 'orange':(213,94,0)}
PALETTE.update({'luma_' + name: tuple(bytes.fromhex(color[1:])) for name,color in LUMA.items()})
SHADED = {name + '_shaded': name for name in ('purple', 'blue', 'light_blue','gold','accessible_blue','gray','orange',*("luma_" + name for name in LUMA))}


def allocation_patches():
    return [(ALLOCATION_SITE, ORIGINAL, BUFFERED),
            (FORWARD_SITE, FORWARD_ORIGINAL, FORWARD_BUFFERED)]


def normalize(data, base):
    for site, original, patched in ((ALLOCATION_SITE, ORIGINAL, BUFFERED),
                                    (FORWARD_SITE, FORWARD_ORIGINAL, FORWARD_BUFFERED)):
        if base <= site < base + len(data):
            offset = site - base
            if data[offset:offset+4] == patched:
                data = data[:offset] + original + data[offset+4:]
    return data


def solid_material(registers, stages, color):
    """Flat-color visibility proof. Alpha commands and texture resources stay intact."""
    if len(registers) != 128 or len(stages) != 512 or color not in PALETTE:
        raise ValueError('unsupported ring test material')
    registers, stages = bytearray(registers), bytearray(stages)
    red, green, blue = PALETTE[color]
    found = set()
    offset = 0
    while offset < len(registers):
        if registers[offset] == 0:
            offset += 1
            continue
        if registers[offset] != 0x61 or offset + 5 > len(registers):
            raise ValueError('unexpected TEV color command')
        register = registers[offset+1]
        value = int.from_bytes(registers[offset+2:offset+5], 'big')
        if value & 0x800000 and register in (0xE0, 0xE1):
            value = ((value & 0xFFF000) | red) if register == 0xE0 else (0x800000 | green << 12 | blue)
            registers[offset+2:offset+5] = value.to_bytes(3, 'big')
            found.add(register)
        offset += 5
    if found != {0xE0, 0xE1}:
        raise ValueError('ring test color registers missing')
    found = set()
    offset = 32
    while offset < len(stages):
        if stages[offset] == 0:
            offset += 1
            continue
        if stages[offset] != 0x61 or offset + 5 > len(stages):
            raise ValueError('unexpected TEV stage command')
        register = stages[offset+1]
        if 0xC0 <= register <= 0xDE and register % 2 == 0:
            # A=B=C=zero, D=KONST; use K0 instead of lighting-owned C0.
            stages[offset+2:offset+5] = (0x08FFFE).to_bytes(3, 'big')
            found.add(register)
        elif 0xF6 <= register < 0xF6 + (stages[12]+1)//2:
            value = int.from_bytes(stages[offset+2:offset+5], 'big')
            value = (value & ~((31 << 4) | (31 << 14))) | (12 << 4) | (12 << 14)
            stages[offset+2:offset+5] = value.to_bytes(3, 'big')
        offset += 5
    if found != {0xC0 + 2*i for i in range(stages[12])}:
        raise ValueError('ring test stage count mismatch')
    return bytes(registers), bytes(stages)


def shaded_material(registers, stages, color):
    # Keep the PAL lighting/texture combiner. Sample texture red as luminance
    # through swap table 3, tint at stage 4, then retain the final highlight.
    tinted, _ = solid_material(registers, stages, color)
    stages = bytearray(stages)
    if stages[12] != 6:
        raise ValueError('shaded ring test requires the six-stage PAL material')
    found = set()
    mask = 0xFFFFFF
    offset = 32
    while offset < len(stages):
        if stages[offset] == 0:
            offset += 1
            continue
        if stages[offset] != 0x61 or offset + 5 > len(stages):
            raise ValueError('unexpected TEV stage command')
        register = stages[offset+1]
        value = int.from_bytes(stages[offset+2:offset+5], 'big')
        replacement = value
        if register == 0xFE:
            mask = value
        else:
            if register == 0xFC and mask & 15 == 15:
                replacement = value & ~15  # swap 3: R=R, G=R
                found.add('swap_rg')
            elif register == 0xFD and mask & 15 == 15:
                replacement = (value & ~15) | 12  # B=R, A=A
                found.add('swap_ba')
            elif register == 0xF8 and mask & (31 << 4) == 31 << 4:
                replacement = (value & ~(31 << 4)) | (12 << 4)  # stage 4: K0
                found.add('tint')
            elif register in (0xC7, 0xCB) and mask & 12 == 12:
                replacement = (value & ~12) | 12  # texture swap 3, same alpha inputs
                found.add(register)
            mask = 0xFFFFFF
        stages[offset+2:offset+5] = replacement.to_bytes(3, 'big')
        offset += 5
    if found != {'swap_rg', 'swap_ba', 'tint', 0xC7, 0xCB}:
        raise ValueError('shaded ring material commands differ from PAL')
    return tinted, bytes(stages)


def inspect(memory, *, stage=None, actors=None, verify=True):
    if verify:
        memory.verify_revision()
    if stage is None:
        stage = read_stage_objects(memory, include_pickups=False)[0]
    if stage.get('scene') != 'gameplay' or not stage.get('mission'):
        raise MemoryUnavailable('Enter a normal Act before probing Red Ring models')
    definitions = {(int(r['object_id']), int(r['instance'])): r for r in load_data('red_rings.json')
                   if r['mission_id'] == stage['mission']}
    result = []
    if actors is None:
        actors = read_actors(memory, stage['context'])
    manager = memory.read_ptr_checked(stage['context']+0x18,0x20)
    for actor in actors:
        if memory.read_u32(actor) != ACTOR_VTABLE:
            continue
        if memory.read_u32(actor+0x34) != manager:
            raise MemoryUnavailable('ring actor owner changed')
        wrapper = memory.read_ptr_checked(actor + 0x64, 0x18)
        record = memory.read_ptr_checked(wrapper + 8, 0x28)
        descriptor = memory.read_ptr_checked(wrapper + 12, 0x20)
        if (memory.read_u32(wrapper+4) != actor or memory.read_u32(descriptor) != 0x80770FA0
                or memory.read_u32(descriptor+0x10) != record or memory.read_u32(descriptor+0x1C) != wrapper):
            raise MemoryUnavailable('ring instance owner changed')
        instance = memory.read_u32(descriptor+0x14)
        definition = definitions.get((memory.read_u32(record) & 0xFFFFF, instance))
        if definition is None:
            continue
        count = memory.read_u32(record+0x1C)
        if not 0 <= instance < count <= 4096:
            raise MemoryUnavailable('ring placement count invalid')
        vector = memory.read_ptr_checked(record+0x18, count*24)
        position = struct.unpack('>3f', memory.read_bytes(vector+instance*24, 12))
        if any(not math.isfinite(a) or abs(a-float(definition[k])) > max(.002, abs(a)*1e-6)
               for a, k in zip(position, ('x', 'y', 'z'))):
            raise MemoryUnavailable('ring canonical placement mismatch')
        ring = int(definition['red_ring_number'])
        if memory.read_u32(record+0x24) != ring-1:
            raise MemoryUnavailable('ring template number mismatch')
        graphics = memory.read_ptr_checked(actor+0xB4, 0x3C)
        if memory.read_u32(graphics) != graphics or memory.read_u32(graphics+8) != 0x8079F6C0:
            raise MemoryUnavailable('ring graphics wrapper mismatch')
        model = memory.read_ptr_checked(graphics+0x1C, 0x1A0)
        if memory.read_u32(model) != MODEL_VTABLE:
            raise MemoryUnavailable('ring ScnMdl vtable mismatch')
        resource = memory.read_ptr_checked(model+0xE8, 0x80)
        if memory.read_bytes(resource, 4) != b'MDL0' or memory.read_u32(resource+8) != 11:
            raise MemoryUnavailable('ring model resource mismatch')
        name = resource + memory.read_s32(resource+0x48)
        if not valid_range(name, 20):
            raise MemoryUnavailable('ring model name pointer invalid')
        if memory.read_bytes(name, 20) != b'cmn_obj_starring_SD\0':
            if memory.read_bytes(name, 25) == b'cmn_obj_starring_hide_SD\0':
                continue
            raise MemoryUnavailable('ring model name mismatch')
        material_group = resource + memory.read_s32(resource+0x30)
        if memory.read_u32(material_group+4) != 1:
            raise MemoryUnavailable('ring material count differs from PAL resource')
        material = material_group + memory.read_s32(material_group+8+16+12)
        material_dl = material + memory.read_s32(material+0x3C)
        dirty, registers, stages = (memory.read_u32(model+o) for o in (0x140, 0x168, 0x174))
        row = dict(ring=ring, mission=stage['mission'], context=stage['context'], actor=actor,
                   graphics=graphics, model=model, resource=resource, dirty=dirty,
                   registers=registers, stages=stages, original_registers=material_dl+32,
                   original_stages=material+memory.read_s32(material+0x28))
        # ResMat.toResTev is at +0x28 in this exact PAL v11 resource.
        result.append(row)
    if len({r['ring'] for r in result}) != len(result):
        raise MemoryUnavailable('ambiguous ring instances')
    return result


def validate_row(memory, row, snapshot=None):
    if (memory.read_bytes(ALLOCATION_SITE, 4) != BUFFERED
            or memory.read_bytes(FORWARD_SITE, 4) != FORWARD_BUFFERED):
        raise MemoryUnavailable('Ring material test ISO required; private buffers were not requested')
    if snapshot is None:
        rows = inspect(memory)
    else:
        stage = next(iter(snapshot.evidence.get('native_data',{}).get('stage_objects',[])),{})
        if stage.get('context') != row['context'] or stage.get('mission') != row['mission']:
            raise MemoryUnavailable('ring stage owner changed')
        rows = inspect(memory,stage=stage,actors=[row['actor']],verify=False)
    current = next((r for r in rows if r['ring'] == row['ring']), None)
    if current != row:
        raise MemoryUnavailable('ring material owner changed')
    intervals = [(row['dirty'], 4), (row['registers'], 128), (row['stages'], 512)]
    if not row['dirty']+4 <= row['registers'] or not row['registers']+128 <= row['stages']:
        raise MemoryUnavailable('ring material allocation order invalid')
    for address, size in intervals:
        if not (valid_range(address, size) and row['model']+0x1A0 <= address
                and address+size <= row['model']+0x10000):
            raise MemoryUnavailable('ring material buffer is not model-owned')
        if any(address < source+length and source < address+size
               for source, length in ((row['original_registers'], 128), (row['original_stages'], 512))):
            raise MemoryUnavailable('ring material buffer aliases the shared resource')
    for i, (a, size) in enumerate(intervals):
        if any(a < b+n and b < a+size for b, n in intervals[i+1:]):
            raise MemoryUnavailable('ring material buffers overlap')
    for other in rows:
        if other['actor'] != row['actor'] and any(other[k] == row[k] for k in ('model', 'registers', 'stages')):
            raise MemoryUnavailable('ring material buffer is shared')
    if snapshot is not None:
        for other in getattr(memory,'_red_ring_visual_rows',None) or ():
            if other['actor'] == row['actor']:
                continue
            # Re-read loaded neighbours, rather than trusting cached pointers.
            if memory.read_u32(other['actor']) != ACTOR_VTABLE:
                continue
            graphics = memory.read_ptr_checked(other['actor']+0xB4,0x3C)
            model = memory.read_ptr_checked(graphics+0x1C,0x1A0)
            if (model == row['model'] or memory.read_u32(model+0x168) == row['registers']
                    or memory.read_u32(model+0x174) == row['stages']):
                raise MemoryUnavailable('ring material buffer is shared with a neighbour')


def apply(memory, row, color, *, operation='ring_material_test'):
    if operation not in ('ring_material_test', 'red_ring_material'):
        raise ValueError('unsupported material operation')
    if color not in (*PALETTE, *SHADED, 'red'):
        raise ValueError('Use purple_shaded, blue_shaded, light_blue_shaded or red')
    validate_row(memory, row, snapshot=getattr(memory,'_red_ring_visual_snapshot',None)
                 if operation == 'red_ring_material' else None)
    registers = memory.read_bytes(row['original_registers'], 128)
    original = memory.read_bytes(row['original_stages'], 512)
    # CopyTo may relocate metadata; only restore/replace the BP command area.
    stages = memory.read_bytes(row['stages'], 32) + original[32:]
    if color in SHADED:
        registers, stages = shaded_material(registers, stages, SHADED[color])
    elif color != 'red':
        registers, stages = solid_material(registers, stages, color)
    flags = memory.read_u32(row['dirty'])
    # These bits request restoration from the shared resource on the next CALC_MAT.
    # Leave them clear so the explicit test does not vanish before its first draw.
    flags &= ~0x900
    values = {row['dirty']: flags.to_bytes(4, 'big')}
    if row['registers'] + len(registers) == row['stages']:
        values[row['registers']] = registers + stages
    else:
        values.update({row['registers']:registers, row['stages']:stages})
    tx = {'row': row, 'values': values, 'color': color}
    memory._ring_material_test = tx
    try:
        for address, data in values.items():
            old = memory.read_bytes(address, len(data))
            if old != data:
                memory.write_bytes_verified(address, data, expected=old, operation=operation)
    finally:
        memory._ring_material_test = None
    return {'ring': row['ring'], 'color': color,
            'mode': 'shaded material experiment' if color in SHADED else 'flat-color experiment; original alpha retained'}
