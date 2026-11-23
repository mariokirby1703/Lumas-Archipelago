import struct

from .capsule_refresh import PPC
from ..oneups import ONEUPS
from ..world_constants import load_data


def key(row):
    mission = row['mission_id']
    if (len(mission) != 6 or not mission.startswith('stg') or not mission[3:].isdigit()
            or row['instance'] != 0 or not 0 <= row['object_id'] <= 0xffff):
        raise ValueError('Unsupported native 1-Up identity')
    return int(mission[3:]) << 16 | row['object_id']


def program(control, table):
    from .oneup_hook import ORIGINAL
    a = PPC()
    def const(r, v):
        a.d(15, r, 0, v >> 16); a.d(24, r, r, v & 65535)
    def load(r, owner, offset):
        a.d(32, r, owner, offset); a.d(11, 0, r, 0); a.branch('done', 0x41820000)
    def equal(left, right):
        a.emit(0x7C000000 | left << 16 | right << 11); a.branch('done', 0x40820000)
    a.d(37, 1, 1, -144); a.d(36, 0, 1, 4)
    a.emit(0x7C000026); a.d(36, 0, 1, 8); a.d(47, 3, 1, 16)
    const(12, control); a.d(32, 3, 12, 0)
    a.d(11, 0, 3, 1); a.branch('done', 0x40820000)
    a.d(32, 3, 30, 0); const(4, 0x807727C8); equal(3, 4)
    load(5, 30, 0x64); load(6, 5, 8); load(7, 5, 12)
    a.d(32, 3, 7, 0x14); a.d(11, 0, 3, 0); a.branch('done', 0x40820000)
    a.d(32, 7, 6, 0); a.emit(0x54E7033E)  # clrlwi r7,r7,12
    a.d(10, 0, 7, 65535); a.branch('done', 0x41810000)
    const(3, 0x808F336C)
    for offset in (0, 4, 0x1C, 0x34): load(3, 3, offset)
    a.d(32, 4, 3, 0); const(5, 0x80759438); equal(4, 5)
    a.d(32, 4, 3, 0x18); a.d(32, 5, 30, 0x34); equal(4, 5)
    load(4, 3, 0x4C)
    a.d(34, 3, 4, 3); a.d(14, 3, 3, -48); a.d(7, 3, 3, 100)
    a.d(34, 5, 4, 4); a.d(14, 5, 5, -48); a.d(7, 5, 5, 10)
    a.emit(0x7C632A14)
    a.d(34, 5, 4, 5); a.d(14, 5, 5, -48); a.emit(0x7C632A14)
    a.emit(0x5463801E); a.emit(0x7CE71B78)  # slwi r3,16; or r7,r7,r3
    const(6, table); a.d(14, 8, 0, 0)
    a.label('find')
    for offset in (0, 4):
        a.d(32, 3, 6, offset); a.emit(0x7C033800); a.branch('found', 0x41820000)
        a.d(14, 8, 8, 1)
    a.d(32, 6, 6, 8); a.d(11, 0, 6, 0); a.branch('find', 0x40820000)
    a.branch('done')
    a.label('found'); a.d(14, 3, 0, 1); a.emit(0x7C634030)
    a.d(32, 4, 12, 12); a.emit(0x7C632378); a.d(36, 3, 12, 12)
    a.label('done'); a.d(46, 3, 1, 16)
    a.d(32, 0, 1, 8); a.emit(0x7C0FF120); a.d(32, 0, 1, 4)
    a.d(14, 1, 1, 144); a.emit(ORIGINAL); a.emit(0)
    return a.finish()


def patches(control, occupied):
    from .native_dol import branch
    from .native_events import scatter_mixed
    from .oneup_hook import HOOK, ORIGINAL
    sites = [s for s in (*load_data('native_event_sites.json'), *load_data('oneup_capture_sites.json'))
             if not any(p < s['address'] + 12 and s['address'] < p + len(new)
                        for p, _, new in occupied)]
    keys = [key(row) for row in ONEUPS.values()]
    if len(keys) > 31 or len(keys) != len(set(keys)):
        raise ValueError('1-Up latch requires unique identities and at most 31 locations')
    if len(keys) % 2: keys.append(0)
    count = len(keys) // 2
    table_sites, sites = sites[:count], sites[count:]
    if len(table_sites) != count: raise ValueError('1-Up table padding exhausted')
    result = []
    for i, site in enumerate(table_sites):
        following = table_sites[i + 1]['address'] if i + 1 < count else 0
        result.append((site['address'], bytes(12), struct.pack('>III', *keys[i*2:i*2+2], following)))
    code, _ = scatter_mixed(program(control, table_sites[0]['address']), sites, HOOK + 4)
    return result + code + [(HOOK, ORIGINAL.to_bytes(4, 'big'), branch(HOOK, code[0][0]).to_bytes(4, 'big'))]
