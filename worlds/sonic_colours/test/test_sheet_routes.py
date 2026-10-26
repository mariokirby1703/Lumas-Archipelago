"""Sheet logic synchronization and physical (not AP-currency) goal regressions."""
from collections import Counter
from types import SimpleNamespace
import pytest

from .. import logic
from ..world_constants import STAGES,load_data
from ..client.runtime import victory
from .test_runtime import snapshot
from . import generate


class State:
    def __init__(self,items=()):self.items=Counter(items)
    def has(self,name,player,count=1):return self.items[name]>=count
    def count(self,name,player):return self.items[name]


def world(movement):
    return SimpleNamespace(player=1,options=SimpleNamespace(
        movement_unlocks=movement,boost_lock=True,game_land_checks=True))


def test_movement_routes_replace_not_and_normal_and_missing_inherit_normal():
    data=load_data('logic_from_sheet_v3.json')
    # Tropical Resort Red Ring 5: free in NL; Rail Jump needed in ML.
    key='stg110:ring:5'
    assert logic.check(world(False),State(),data,key)
    assert not logic.check(world(True),State(),data,key)
    assert logic.check(world(True),State(['Progressive Rail']),data,key)
    # Act 1 Starlight requires Cube in NL and Cube+Homing in ML.
    key=next(s['mission_id'] for s in STAGES if s['zone_index']==2 and s['slot']==1)
    assert logic.check(world(False),State(['Blue Cube Wisp']),data,key)
    assert not logic.check(world(True),State(['Blue Cube Wisp']),data,key)
    assert logic.check(world(True),State(['Blue Cube Wisp','Homing Attack']),data,key)
    # The underwater route needs both Breathing and Drill.
    key=next(s['mission_id'] for s in STAGES if s['zone_index']==4 and s['slot']==1)+':ring:3'
    assert not logic.check(world(True),State(),data,key)
    assert logic.check(world(True),State(['Progressive Breathing','Progressive Yellow Drill Wisp']),data,key)


def test_seven_bosses_and_all_180_physical_rings_are_required():
    bosses=[s['mission_id'] for s in STAGES if s['kind']=='Boss']
    stages=[s['mission_id'] for s in STAGES if s['normal']]
    assert len(bosses)==7 and len(stages)==36
    boss_slot=generate({'goal':'all_bosses'}).worlds[1].fill_slot_data()
    assert not victory(boss_slot,snapshot(persisted_clears=frozenset(bosses[:-1])))
    assert victory(boss_slot,snapshot(persisted_clears=frozenset(bosses)))
    for ring_checks in ('off','singles','per_level'):
        ring_slot=generate({'goal':'all_red_rings','red_ring_checks':ring_checks}).worlds[1].fill_slot_data()
        native={stage:frozenset(range(1,6)) for stage in stages}
        assert not victory(ring_slot,snapshot(persisted_rings=native),verified_save=False)
        assert victory(ring_slot,snapshot(persisted_rings=native),verified_save=True)
        partial={**native,stages[-1]:frozenset(range(1,5))}
        assert not victory(ring_slot,snapshot(persisted_rings=partial),verified_save=True)
        # AP currency or individual AP location checks never contribute to goal.
        assert not victory(ring_slot,snapshot(),{},owned={'red_rings':9999},verified_save=True)
        journal={stage:31 for stage in stages}
        assert victory(ring_slot,snapshot(),journal)
        del journal[stages[-1]]
        assert not victory(ring_slot,snapshot(),journal)


@pytest.mark.parametrize('progression',(0,1))
def test_vanilla_sequential_and_all_open_boss_gate_rules(progression):
    # All 6 acts and the boss exist in each vanilla world, even when stage
    # IDs are shuffled relative to their on-map slot numbers.
    data=load_data('logic_from_sheet_v3.json')
    for zone in range(6):
        stages=sorted((s for s in STAGES if s['zone_index']==zone),key=lambda s:s['slot'])
        assert [s['slot'] for s in stages]==list(range(1,8))
        assert all(s['mission_id'] in data['locations'] for s in stages)
    mw=generate({'world_progression':progression},fill=True)
    assert mw.can_beat_game()


def test_entrance_rules_sequential_or_all_six(monkeypatch):
    from .. import Rules
    from BaseClasses import CollectionState
    for mode in (0,1):
        mw=generate({'world_progression':mode})
        w=mw.worlds[1]
        state=CollectionState(mw)
        zone=1
        stages=sorted((s for s in STAGES if s['zone_index']==zone),key=lambda s:s['slot'])
        stage2_entrance=w.get_region('Map Slot '+stages[1]['stage_slot_id']).entrances[0]
        boss_entrance=w.get_region('Map Slot '+stages[6]['stage_slot_id']).entrances[0]
        permitted=set()
        monkeypatch.setattr(Rules,'can_complete',lambda w,s,mission:mission in permitted)
        if mode==0:
            assert not stage2_entrance.access_rule(state)
            permitted.add(stages[0]['mission_id'])
            assert stage2_entrance.access_rule(state)
            permitted.clear()
            assert not boss_entrance.access_rule(state)
            permitted.add(stages[5]['mission_id'])
            assert not boss_entrance.access_rule(state)
            permitted.update(s['mission_id'] for s in stages[:6])
            assert boss_entrance.access_rule(state)
        else:
            assert stage2_entrance.access_rule(state)
            permitted.update(s['mission_id'] for s in stages[:5])
            assert not boss_entrance.access_rule(state)
            permitted.add(stages[5]['mission_id'])
            assert boss_entrance.access_rule(state)


def test_chaos_emerald_rule_checks_each_of_three_stage_clears(monkeypatch):
    from .. import Rules
    from BaseClasses import CollectionState
    mw=generate({'game_land_checks':1,'chaos_emerald_checks':1})
    w=mw.worlds[1]
    state=CollectionState(mw)
    stages=sorted((s for s in STAGES if s['zone_index']==7),key=lambda s:s['slot'])
    name='Green Chaos Emerald'
    location=w.get_location(name)
    permitted=set(s['mission_id'] for s in stages)
    monkeypatch.setattr(Rules,'can_complete',lambda w,s,mission:mission in permitted)
    assert location.access_rule(state)
    for missing in stages:
        permitted.remove(missing['mission_id'])
        assert not location.access_rule(state),missing['mission_id']
        permitted.add(missing['mission_id'])
