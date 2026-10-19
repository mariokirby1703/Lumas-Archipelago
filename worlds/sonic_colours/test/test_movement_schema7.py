"""Native movement schema 7 invariants. Live Dolphin execution NOT asserted."""

from ..tools.private_assets import reference_root
from collections import Counter
from ..Items import MOVEMENT_ITEMS, MOVEMENT_POOL, ITEM_TABLE
from ..world_constants import BASE_ID, SCHEMA_VERSION
from ..client import direct_hooks, movement_gate
from . import generate


def test_movement_ids_are_append_only_and_progressive_crouch_has_two_copies():
    assert SCHEMA_VERSION == 7
    assert tuple(ITEM_TABLE[x] for x in MOVEMENT_ITEMS) == tuple(range(BASE_ID+37,BASE_ID+44))+(BASE_ID+45,BASE_ID+46,BASE_ID+47,BASE_ID+48,BASE_ID+49,BASE_ID+51,BASE_ID+52)
    assert MOVEMENT_POOL.count('Progressive Crouch') == 2
    assert len(MOVEMENT_POOL) == 25
    w = generate({'movement_unlocks':True}).worlds[1]
    from collections import Counter
    c = Counter(item.name for item in w.multiworld.itempool)
    assert all(c[name] == (2 if name in ('Progressive Crouch','Progressive Rail','Progressive Skydiving') else 5 if name in ('Progressive Breathing','Progressive Stunts') else 1) for name in MOVEMENT_ITEMS)
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
    assert set(movement_gate.STATE_PERMISSION) == {8,9,10,13,29,30,38,39,40,41,43,44,82,110}


def test_experimental_native_movement_hook_respects_memory_scratch_limit():
    baseline=direct_hooks.plan()
    optional=direct_hooks.plan(include_movement=True)
    assert len(baseline)==10 and len(optional)==11
    assert sum(len(row[3]) for row in optional) <= direct_hooks.ARENA_END-direct_hooks.ARENA_START
    row=next(r for r in optional if r[4]=='movement')
    words,deny,offset=movement_gate.payload()
    assert row[0]==movement_gate.HOOK and row[1]==movement_gate.ORIGINAL
    assert 0x3BE3FFEC in words # resolve machine from common queue receiver
    assert 0x4D820020 in words # denied request returns before native callbacks
    assert int.from_bytes(row[3][-4:],'big') == direct_hooks._branch(row[2]+len(row[3])-4,movement_gate.HOOK+4)
    assert row[3][offset:offset+8] == bytes(8)


def test_drift_and_swim_have_independent_permissions():
    assert movement_gate.permissions(Counter({"Drifting":1})) == 128
    assert movement_gate.permissions(Counter({"Swim":1})) == 256


def test_rail_jump_and_switch_have_independent_wide_permissions():
    assert movement_gate.permissions(Counter({'Progressive Rail':1}))==512
    assert movement_gate.STATE_PERMISSION[29]==9
    assert movement_gate.STATE_PERMISSION[30]==10
    assert movement_gate.permissions(Counter({"Progressive Rail":2}))==1536
    from pathlib import Path
    from ..tools.ppc import Executable
    path=reference_root()/'Sonic_Colours_PAL_Static_RE_v2/sonic_pal_disassembly.elf'
    if path.exists():
        e=Executable(path)
        getter=int.from_bytes(e.read(0x807610F8+0xc,4),'big')
        assert getter==0x800D2330
        assert b'CStateGrindJumpShort\0'==e.read(0x80761200,21)


def test_progressive_rail_test_commands_and_retired_id():
    from ..Items import BY_ID
    from ..client.test_inventory import resolve_item, MAXIMUM
    assert resolve_item('rail') == 'Progressive Rail'
    assert resolve_item('drift') == 'Drifting'
    assert MAXIMUM['Progressive Rail'] == 2
    assert 'Rail Switch' not in ITEM_TABLE
    assert BY_ID[BASE_ID+50] == 'Rail Switch'
    assert movement_gate.permissions(Counter({'Rail Switch':1})) == 1024


def test_fast_dive_requires_second_skydiving_copy():
    assert not movement_gate.permissions(Counter({'Progressive Skydiving':1})) & 4096
    assert movement_gate.permissions(Counter({'Progressive Skydiving':2})) & 4096


def test_spikes_spin_dash_second_tier_permission():
    assert not movement_gate.permissions(Counter({'Progressive Pink Spikes Wisp':1})) & 8192
    assert movement_gate.permissions(Counter({'Progressive Pink Spikes Wisp':2})) & 8192
