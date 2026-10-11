"""Native movement schema 7 invariants. Live Dolphin execution NOT asserted."""
from collections import Counter
from ..Items import MOVEMENT_ITEMS, MOVEMENT_POOL, ITEM_TABLE
from ..world_constants import BASE_ID, SCHEMA_VERSION
from ..client import direct_hooks, movement_gate
from . import generate


def test_movement_ids_are_append_only_and_progressive_crouch_has_two_copies():
    assert SCHEMA_VERSION == 7
    assert tuple(ITEM_TABLE[x] for x in MOVEMENT_ITEMS) == tuple(range(BASE_ID+37,BASE_ID+45))
    assert MOVEMENT_POOL.count('Progressive Crouch') == 2
    assert len(MOVEMENT_POOL) == 9
    w = generate({'movement_unlocks':True}).worlds[1]
    from collections import Counter
    c = Counter(item.name for item in w.multiworld.itempool)
    assert all(c[name] == (2 if name=='Progressive Crouch' else 1) for name in MOVEMENT_ITEMS)
    assert w.fill_slot_data()['options']['movement_unlocks'] == 1
    default = generate().worlds[1]
    assert not any(i.name in MOVEMENT_ITEMS for i in default.multiworld.itempool)


def test_progressive_permissions_and_independent_jumpdash():
    mask=movement_gate.permissions
    assert mask(Counter())==0
    assert mask(Counter({'Progressive Crouch':1})) & (1<<5)
    assert not mask(Counter({'Progressive Crouch':1})) & (1<<4)
    assert mask(Counter({'Progressive Crouch':2})) & (1<<4)
    assert mask(Counter({'Mid-Air Boost':1})) == 1<<1
    assert mask(Counter({'Wall Jump':1})) == 1<<3
    assert not mask(Counter({'White Boost Wisp':1}))
    assert set(movement_gate.STATE_PERMISSION) == {8,9,13,39,40,41,43,44}


def test_experimental_native_movement_hook_respects_memory_scratch_limit():
    baseline=direct_hooks.plan()
    optional=direct_hooks.plan(include_movement=True)
    assert len(baseline)==10 and len(optional)==11
    assert sum(len(row[3]) for row in optional) <= direct_hooks.ARENA_END-direct_hooks.ARENA_START
    row=next(r for r in optional if r[4]=='movement')
    words,deny,offset=movement_gate.payload()
    assert row[0]==movement_gate.HOOK and row[1]==movement_gate.ORIGINAL
    assert int.from_bytes(row[3][deny*4:deny*4+4],'big') == direct_hooks._branch(row[2]+deny*4,movement_gate.DENIED_CONTINUATION)
    assert int.from_bytes(row[3][-4:],'big') == direct_hooks._branch(row[2]+len(row[3])-4,movement_gate.HOOK+4)
    assert row[3][offset:offset+8] == bytes(8)
