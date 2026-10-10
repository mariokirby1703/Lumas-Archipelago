"""Seed cue redirects in the PAL mission table, before native stage loading."""
from .memory import MemoryUnavailable
from .native_read import STAGE_TABLE_GLOBAL
from .audio import plan_music
from ..world_constants import NORMAL


def mapping_for(slot):
    return plan_music(slot['seed_name'], ('off', 'per_world', 'anywhere')[slot['options']['music_randomization']],
                      {s['bgm'] for s in NORMAL})


def cue_records(memory):
    table = memory.read_ptr_checked(STAGE_TABLE_GLOBAL, 0x3c)
    if memory.read_u32(table) != 0x8075DB5C:
        raise MemoryUnavailable('music: mission table type mismatch')
    vector = memory.read_ptr_checked(table + 0x30, 0x118)
    count, capacity = memory.read_u32(table + 0x34), memory.read_u32(table + 0x38)
    if not 0 < count <= capacity <= 128:
        raise MemoryUnavailable('music: invalid mission table bounds')
    records = memory.read_bytes(vector, count * 0x118)
    result = {}
    expected = {s['mission_id'] for s in NORMAL}
    cues = {s['bgm'] for s in NORMAL}
    for i in range(count):
        row = records[i*0x118:(i+1)*0x118]
        mission = row[:16].split(b'\0',1)[0].decode('ascii', errors='replace')
        if mission not in expected:
            continue
        cue = row[0xac:0xcc].split(b'\0',1)[0].decode('ascii', errors='replace')
        if mission in result or cue not in cues:
            raise MemoryUnavailable('music: unknown or duplicate native cue')
        result[mission] = vector + i*0x118 + 0xac
    if set(result) != expected:
        raise MemoryUnavailable('music: incomplete native mission catalog')
    if (memory.read_u32(STAGE_TABLE_GLOBAL) != table or memory.read_u32(table+0x30) != vector
            or memory.read_u32(table+0x34) != count):
        raise MemoryUnavailable('music: mission table changed')
    return table, vector, count, result


def apply_music(memory, slot, resource=False):
    # A seed-specific bank already redirects every supported original alias.
    # Restore vanilla mission aliases to avoid composing two different shuffles.
    mapping = {s['mission_id']: s['bgm'] for s in NORMAL} if resource else mapping_for(slot)
    _, _, _, records = cue_records(memory)
    changed = 0
    for mission, address in records.items():
        target = mapping[mission].encode('ascii').ljust(32,b'\0')
        before = memory.read_bytes(address,32)
        if target != before:
            memory.write_bytes_verified(address,target,expected=before,operation='music_cues')
            changed += 1
    return {'status':('original mission aliases verified for selected resource bank' if resource else
                     'native cue table verified; takes effect on the next stage load'),
            'seed':slot['seed_name'],'changed_cues':changed,'audible_verified':False}
