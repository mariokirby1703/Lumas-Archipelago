import struct
from dataclasses import replace
import pytest
from ..client.capsule_refresh import inspect_installed
from ..client.memory import SonicMemory, MemoryUnavailable
from ..client.hooks import NativeHooks
from ..world_constants import load_data
from .test_memory import FakeBackend
from .test_pickup_integration import Overlay
from .test_native_originals import PAIRS
from ..Items import ITEM_TABLE, LEGACY_FILLER
from ..world_constants import BASE_ID, WISPS
from ..client.runtime import rings_amount, victory
from ..client.journal import Journal
from .test_runtime import IDENTITY, snapshot
from .test_items_wisps_live import runtime_fixture, settle
from . import generate


def captured(b):
    f=load_data('capsule_hook_live_oct10.json')
    b.write_bytes(f['hook'],f['instruction'].to_bytes(4,'big'))
    b.write_bytes(f['target']-8,bytes.fromhex(f['header']))
    b.write_bytes(f['target'],bytes.fromhex(f['payload_hex']))
    return f


def test_actual_dolphin_c2_capture_is_exactly_recognized():
    b=FakeBackend();f=captured(b);m=SonicMemory(b)
    r=inspect_installed(m)
    assert r['variant']=='c9364ebe' and r['payload_length']==r['actual_header_length']==496
    assert r['return_target']==0x800d4828
    b.put(f['target']+40,bytes(4))
    with pytest.raises(MemoryUnavailable,match='first_differing_word'):inspect_installed(m)


@pytest.mark.skipif(not PAIRS,reason='original private RAM unavailable')
def test_real_c2_layout_keeps_native_core_intro_detection():
    b=Overlay(PAIRS[0]);captured(b);m=SonicMemory(b)
    m.verify_revision()
    s=NativeHooks().snapshot(m)
    assert s.scene=='gameplay' and s.new_game_verified and s.pickup_verified


def test_new_item_ids_do_not_alias_retired_or_legacy_ids():
    assert [ITEM_TABLE[n] for n in LEGACY_FILLER] == [BASE_ID+i for i in (26,27,28)]
    assert ITEM_TABLE['Rings'] == BASE_ID+32
    assert ITEM_TABLE['Half Boost Refill'] == BASE_ID+33
    assert len(set(ITEM_TABLE.values())) == len(ITEM_TABLE)
    m=generate()
    assert not any(i.name in LEGACY_FILLER for i in m.itempool)


def test_random_rings_roll_survives_results_restart_and_later_receipts(tmp_path):
    items=[ITEM_TABLE['Rings']]*3
    with Journal(tmp_path,IDENTITY) as j:
        r,b,m,tick=runtime_fixture(j);j.record_history(items)
        r.snapshot=replace(r.snapshot,scene='results')
        r.apply_effects(m,items)
        rolls=[rings_amount(j,i) for i in range(3)]
        assert all(1<=v<=100 for v in rolls) and not b.writes
    with Journal(tmp_path,IDENTITY) as j:
        r,b,m,tick=runtime_fixture(j)
        assert rolls==[rings_amount(j,i) for i in range(3)]
        r.snapshot=replace(r.snapshot,stage_epoch='act2')
        r.apply_effects(m,items)
        for _ in items:settle(r,m,items,tick)
        assert all(e['state']=='confirmed' for e in j.data['effects'].values())
        assert m.read_u32(r.snapshot.rings_address)==sum(rolls)
        writes=len(b.writes);r.apply_effects(m,items);assert len(b.writes)==writes


@pytest.mark.parametrize('maximum,current,expected',[(100.,10.,60.),(50.,10.,35.),(100.,90.,100.)])
def test_half_boost_uses_native_maximum_and_defers_results(tmp_path,maximum,current,expected):
    items=[ITEM_TABLE['Half Boost Refill']]
    with Journal(tmp_path,IDENTITY) as j:
        r,b,m,tick=runtime_fixture(j);j.record_history(items)
        r.snapshot=replace(r.snapshot,boost_address=0x90002008,boost_max_address=0x90002014,scene='results')
        b.put(r.snapshot.boost_address,struct.pack('>f',current))
        b.put(r.snapshot.boost_max_address,struct.pack('>f',maximum))
        r.apply_effects(m,items);assert not b.writes
        r.snapshot=replace(r.snapshot,scene='gameplay',stage_epoch='act2')
        r.apply_effects(m,items);settle(r,m,items,tick)
        assert m.read_f32(r.snapshot.boost_address)==expected
        assert j.data['effects']['0']['state']=='confirmed'


def test_final_goal_requires_escape_after_boss_and_survives_reload():
    slot=generate().worlds[1].fill_slot_data()
    assert not victory(slot,snapshot(persisted_clears=frozenset({'stg790'})))
    assert not victory(slot,snapshot(persisted_clears=frozenset({'stg720'})))
    assert victory(slot,snapshot(persisted_clears=frozenset({'stg720','stg790'})))
    assert victory(slot,snapshot(persisted_clears=frozenset({'stg720'})),observed_clears={'stg790'})


def test_terminal_velocity_requires_every_wisp_without_access_item():
    from BaseClasses import CollectionState
    from ..Items import WISP_ITEMS, WORLD_ITEMS
    from ..world_constants import STAGES
    multiworld = generate()
    world = multiworld.worlds[1]
    state = CollectionState(multiworld)
    for item in WISP_ITEMS[:-1]:
        state.collect(world.create_item(item), prevent_sweep=True)
    terminal = [s for s in STAGES if s['zone_index'] == 6]
    for stage in terminal:
        reachable = state.can_reach('Map Slot ' + stage['stage_slot_id'], 'Region', 1)
        assert not reachable
    state.collect(world.create_item(WISP_ITEMS[-1]), prevent_sweep=True)
    assert all(state.can_reach('Map Slot ' + s['stage_slot_id'], 'Region', 1) for s in terminal)


@pytest.mark.parametrize('locked', [False, True])
def test_white_capsule_logic_matches_optional_boost_lock(locked):
    from BaseClasses import CollectionState
    from ..capsules import CAPSULES
    multiworld = generate({'wisp_capsules': True, 'boost_lock': locked})
    world = multiworld.worlds[1]
    state = CollectionState(multiworld)
    capsule = next(c for c in CAPSULES.values() if c.eligible and c.mission == 'stg110'
                   and c.wisp_item == 'White Boost Wisp')
    assert multiworld.get_location(capsule.name, 1).access_rule(state) == (not locked)
    state.collect(world.create_item('White Boost Wisp'), prevent_sweep=True)
    assert multiworld.get_location(capsule.name, 1).access_rule(state)


@pytest.mark.parametrize('current, expected', [(0.,50.),(50.,100.),(90.,100.)])
def test_half_boost_without_white_ownership_stores_gauge_and_remains_durable(tmp_path,current,expected):
    items=[ITEM_TABLE['Half Boost Refill']]
    with Journal(tmp_path,IDENTITY) as j:
        r,b,m,tick=runtime_fixture(j);j.record_history(items)
        r.slot_data['options']['boost_lock']=1
        r.snapshot=replace(r.snapshot,boost_address=0x90002008,boost_max_address=0x90002014)
        b.put(r.snapshot.boost_address,struct.pack('>f',current))
        b.put(r.snapshot.boost_max_address,struct.pack('>f',100.))
        r.apply_effects(m,items);settle(r,m,items,tick)
        assert m.read_f32(r.snapshot.boost_address)==expected
        assert j.data['effects']['0']['state']=='confirmed'
        assert ITEM_TABLE['White Boost Wisp'] not in j.data['receipts']
        assert r.item_details()[0]['journal_state']=='confirmed'


@pytest.mark.parametrize('item_name,current,maximum,expected', [
    ('Full Boost Refill',10.,100.,100.),('Full Boost Refill',30.,50.,50.),
    ('Half Boost Refill',10.,50.,35.)])
def test_refill_temporary_permission_depletion_reconnect(tmp_path,item_name,current,maximum,expected):
    items=[ITEM_TABLE[item_name]]
    with Journal(tmp_path,IDENTITY) as j:
        r,b,m,tick=runtime_fixture(j);j.record_history(items)
        r.snapshot=replace(r.snapshot,boost_address=0x90002008,boost_max_address=0x90002014)
        b.put(r.snapshot.boost_address,struct.pack('>f',current))
        b.put(r.snapshot.boost_max_address,struct.pack('>f',maximum))
        assert not r.temporary_boost_allowed(m)
        r.apply_effects(m,items);settle(r,m,items,tick)
        assert m.read_f32(r.snapshot.boost_address)==expected
        assert r.temporary_boost_allowed(m)
        b.put(r.snapshot.boost_address,struct.pack('>f',0.))
        assert not r.temporary_boost_allowed(m)
        # A subsequent vanilla value cannot resurrect an exhausted AP grant.
        b.put(r.snapshot.boost_address,struct.pack('>f',25.))
        assert not r.temporary_boost_allowed(m)
        assert ITEM_TABLE['White Boost Wisp'] not in j.data['receipts']
        writes=len(b.writes);r.apply_effects(m,items);assert len(b.writes)==writes
