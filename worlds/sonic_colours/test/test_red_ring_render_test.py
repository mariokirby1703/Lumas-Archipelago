from types import SimpleNamespace
import struct

import pytest

from ..client import red_ring_render_test as render
from ..client.memory import SonicMemory, MemoryUnavailable
from ..client.state import WritePolicy
from .test_memory import FakeBackend


def material():
    registers = bytearray(128)
    commands = bytes.fromhex('61e200000061e300000061e080000061e1800000')
    registers[:len(commands)] = commands
    stages = bytearray(512)
    stages[:4] = (512).to_bytes(4, 'big')
    stages[12] = 1
    stages[32:42] = bytes.fromhex('61c008afee61c108fff0')
    return bytes(registers), bytes(stages)


@pytest.mark.parametrize('color', render.PALETTE)
def test_flat_color_changes_only_color_commands_preserving_alpha_and_metadata(color):
    registers, stages = material()
    new_registers, new_stages = render.solid_material(registers, stages, color)
    assert new_registers[:10] == registers[:10]
    assert new_registers[20:] == registers[20:]
    assert new_stages[:32] == stages[:32]
    assert new_stages[37:] == stages[37:]
    assert new_stages[34:37] == bytes.fromhex('08fffe')
    red, green, blue = render.PALETTE[color]
    assert int.from_bytes(new_registers[12:15], 'big') == 0x800000 | red
    assert int.from_bytes(new_registers[17:20], 'big') == 0x800000 | green << 12 | blue


@pytest.mark.parametrize('color', ('purple', 'blue', 'light_blue'))
def test_shaded_material_keeps_color_math_and_alpha_inputs(color):
    registers, _ = material()
    stages = bytearray(512)
    stages[12] = 6
    commands = bytes.fromhex(
        '61fe00000f61fc00000a61fe00000f61fd00000e'
        '61fefffff061f8e338f0'
        '61c008afee61c200f00f61c40824b061c600f80f61c808fe0f61ca08f8a0'
        '61c108fff061c308ff8061c508fff061c708fff061c908ff8061cb08ff80')
    stages[32:32+len(commands)] = commands
    new_registers, result = render.shaded_material(registers, bytes(stages), color)
    assert new_registers == render.solid_material(registers, bytes(stages), color)[0]
    assert result[:32] == stages[:32]
    expected = {0xFC: 0, 0xFD: 12, 0xF8: 0xE338C0, 0xC7: 0x08FFFC, 0xCB: 0x08FF8C}
    for offset in range(32, 32+len(commands), 5):
        reg = stages[offset+1]
        old = int.from_bytes(stages[offset+2:offset+5], 'big')
        value = int.from_bytes(result[offset+2:offset+5], 'big')
        assert value == expected.get(reg, old)
    assert result[32+len(commands):] == stages[32+len(commands):]


def test_shaded_material_rejects_other_stage_layouts():
    registers, stages = material()
    with pytest.raises(ValueError, match='six-stage'):
        render.shaded_material(registers, stages, 'purple')


def setup(monkeypatch):
    backend = FakeBackend()
    memory = SonicMemory(backend)
    memory.verify_revision = lambda: None
    memory.verify_for_write = lambda operation: None
    actor, manager, node = 0x90003000, 0x90002000, 0x90002100
    wrapper, record, descriptor, vector = 0x90004000, 0x90004100, 0x90004200, 0x90004300
    graphics, model, resource = 0x90005000, 0x90010000, 0x90100000
    group, mat, dl, shader = 0x90101000, 0x90102000, 0x90103000, 0x90104000
    def word(address, value):
        backend.put(address, (value & 0xFFFFFFFF).to_bytes(4, 'big'))
    word(render.ALLOCATION_SITE, int.from_bytes(render.BUFFERED, 'big'))
    word(render.FORWARD_SITE, int.from_bytes(render.FORWARD_BUFFERED, 'big'))
    stage = dict(context=0x90001000, scene='gameplay', mission='stg110')
    monkeypatch.setattr(render, 'read_stage_objects', lambda *args, **kw: [stage])
    word(stage['context']+0x18, manager)
    word(manager+0x14, 1)
    word(manager+0x18, node)
    word(manager+0x1C, node)
    backend.put(node, struct.pack('>3I', manager+0x18, manager+0x18, actor))
    for address, value in (
            (actor, render.ACTOR_VTABLE), (actor+0x34, manager), (actor+0x64, wrapper),
            (wrapper+4, actor), (wrapper+8, record), (wrapper+12, descriptor),
            (descriptor, 0x80770FA0), (descriptor+0x10, record), (descriptor+0x1C, wrapper),
            (record, 69), (record+0x1C, 1), (record+0x18, vector),
            (actor+0xB4, graphics), (graphics, graphics), (graphics+8, 0x8079F6C0),
            (graphics+0x1C, model), (model, render.MODEL_VTABLE), (model+0xE8, resource),
            (resource+8, 11), (resource+0x48, 0x500), (resource+0x30, group-resource),
            (group+4, 1), (group+36, mat-group), (mat+0x3C, dl-mat),
            (mat+0x28, shader-mat), (model+0x140, model+0x200),
            (model+0x168, model+0x300), (model+0x174, model+0x400)):
        word(address, value)
    backend.put(vector, struct.pack('>3f', -12884., 1220.05, 11371.6))
    backend.put(resource, b'MDL0')
    backend.put(resource+0x500, b'cmn_obj_starring_SD\0')
    registers, stages = material()
    backend.put(dl+32, registers)
    backend.put(shader, stages)
    backend.put(model+0x300, registers)
    backend.put(model+0x400, stages)
    snapshot = SimpleNamespace(session='S', stage_epoch='A')
    guard = SimpleNamespace(check_stats=lambda s: None)
    memory.write_guard = WritePolicy(memory, guard, lambda m: snapshot)
    return memory, backend, word


def test_one_ring_tint_and_restore_only_write_owned_copies(monkeypatch):
    memory, backend, word = setup(monkeypatch)
    row, = render.inspect(memory)
    original_registers = memory.read_bytes(row['registers'], 128)
    original_stages = memory.read_bytes(row['stages'], 512)
    render.apply(memory, row, 'purple')
    assert {address for address, data in backend.writes} == {row[k] for k in ('registers', 'stages')}
    assert memory.read_bytes(row['original_registers'], 128) == original_registers
    assert memory.read_bytes(row['original_stages'], 512) == original_stages
    render.apply(memory, row, 'red')
    assert memory.read_bytes(row['registers'], 128) == original_registers
    assert memory.read_bytes(row['stages'], 512) == original_stages
    assert memory.read_u32(row['dirty']) == 0


def test_automatic_material_requires_authenticated_scout_color(monkeypatch):
    memory, backend, word = setup(monkeypatch)
    # Use the real PAL six-stage command layout for the production path.
    stages = bytearray(512)
    stages[12] = 6
    commands = bytes.fromhex('61fe00000f61fc00000a61fe00000f61fd00000e'
                             '61fefffff061f8e338f061c708fff061cb08ff80'
                             '61c008afee61c200f00f61c40824b061c600f80f61c808fe0f61ca08f8a0')
    stages[32:32+len(commands)] = commands
    row, = render.inspect(memory)
    backend.put(row['original_stages'], stages)
    backend.put(row['stages'], stages)
    identity = {'seed':'seed','team':0,'slot':1}
    memory.write_guard.guard.journal = SimpleNamespace(identity=identity)
    memory.write_guard.guard.check_visual = lambda snapshot: None
    import hashlib
    memory.native_patch = {'seed_digest':hashlib.sha256(b'seed').digest()[:16].hex()}
    snapshot = memory.write_guard.snapshot_reader(memory)
    snapshot.actual_mission = 'stg110'
    snapshot.evidence = {'native_data':{'stage_objects':[{'scene':'gameplay','mission':'stg110',
                                                         'context':row['context']}]}}
    source = SimpleNamespace(enabled=True,identity=('seed',0,1),
                             stage_colors=lambda mission: ('purple',)*5)
    with pytest.raises(MemoryUnavailable,match='unauthenticated'):
        render.apply(memory,row,'purple_shaded',operation='red_ring_material')
    assert not backend.writes
    memory._red_ring_color_source = source
    with pytest.raises(MemoryUnavailable,match='differs from scouted'):
        render.apply(memory,row,'blue_shaded',operation='red_ring_material')
    assert not backend.writes
    render.apply(memory,row,'purple_shaded',operation='red_ring_material')
    assert backend.writes
    backend.writes.clear()
    backend.put(row['registers'], memory.read_bytes(row['original_registers'],128))
    memory.native_patch = {'seed_digest':'0'*32}
    with pytest.raises(MemoryUnavailable,match='another native seed'):
        render.apply(memory,row,'purple_shaded',operation='red_ring_material')
    assert not backend.writes
    source.identity = ('other seed',0,1)
    with pytest.raises(MemoryUnavailable,match='unauthenticated'):
        render.apply(memory,row,'blue_shaded',operation='red_ring_material')
    assert not backend.writes


@pytest.mark.parametrize('failure', ['plain_iso', 'shared_resource', 'owner', 'scene'])
def test_unverified_materials_do_not_write(monkeypatch, failure):
    memory, backend, word = setup(monkeypatch)
    row, = render.inspect(memory)
    if failure == 'plain_iso':
        backend.put(render.ALLOCATION_SITE, render.ORIGINAL)
    elif failure == 'shared_resource':
        word(row['model']+0x168, row['original_registers'])
        row, = render.inspect(memory)
    elif failure == 'owner':
        word(row['actor']+0xB4, 0)
    else:
        monkeypatch.setattr(render, 'read_stage_objects', lambda *a, **k: [dict(scene='world_map')])
    with pytest.raises(MemoryUnavailable):
        render.apply(memory, row, 'purple')
    assert not backend.writes


def test_only_exact_experimental_allocation_instruction_normalizes():
    assert render.normalize(render.BUFFERED, render.ALLOCATION_SITE) == render.ORIGINAL
    assert render.normalize(b'\xff'*4, render.ALLOCATION_SITE) == b'\xff'*4
    assert render.normalize(render.FORWARD_BUFFERED, render.FORWARD_SITE) == render.FORWARD_ORIGINAL


def test_original_pal_allocation_and_model_vtable(pal_dol_bytes):
    from ..client.native_dol import Dol
    image = Dol(pal_dol_bytes)
    assert image.read(render.ALLOCATION_SITE, 4) == render.ORIGINAL
    assert image.read(render.FORWARD_SITE, 4) == render.FORWARD_ORIGINAL
    assert image.read(0x805BB8EC, 16).hex() == '3c80807b800100b03884a95090900000'


def test_pal_forwards_explicit_buffer_bits_and_preserves_other_model_flags():
    from capstone import Cs, CS_ARCH_PPC, CS_MODE_32, CS_MODE_BIG_ENDIAN
    decoder = Cs(CS_ARCH_PPC, CS_MODE_32 | CS_MODE_BIG_ENDIAN)
    instruction, = decoder.disasm(render.FORWARD_BUFFERED, render.FORWARD_SITE)
    assert instruction.mnemonic == 'andi.' and instruction.op_str == 'r6, r7, 0x900'
    for flags in range(32):
        assert flags & 0x900 == 0
    assert 0x900 & 0x900 == 0x900
