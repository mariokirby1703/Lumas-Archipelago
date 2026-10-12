from dataclasses import replace
import pytest
from ..client.physical_rings import apply, targets, witnessed
from ..client.journal import Journal
from ..client.state import SaveGuard, WritePolicy
from ..client.memory import SonicMemory, MemoryUnavailable
from ..client.versions import VERSION
from ..Items import ITEM_TABLE, WORLD_ITEMS
from ..Locations import LOCATION_TABLE
from ..world_constants import BY_MISSION
from .test_runtime import IDENTITY, snapshot
from .test_memory import FakeBackend


def setup(tmp_path):
    j=Journal(tmp_path,IDENTITY)
    j.data.update(save_identity='save',bootstrap={'epoch':'epoch'},pickup_events=[
        {'kind':'red_ring','mission':'stg110','ring':1,'playthrough_epoch':'epoch'}])
    b=FakeBackend();m=SonicMemory(b)
    def word(a,v):b.put(a,v.to_bytes(4,'big'))
    word(VERSION['manager_global_candidate'],0x90000100)
    word(0x90000130,0x90001000);b.put(0x90001000,b'\x01')
    chain=m.resolve_flags_ptr()
    stage,actor=0x90030000,0x90040000
    word(stage+0x114,actor);word(actor,0x8075A228)
    b.put(actor+0x91,b'\x80')
    s=snapshot(actual_mission='stg110',stage_epoch='stage',scene_verified=True,
        pickup_verified=True,save_identity_verified=True,progress_verified=True,
        evidence={'chain':chain,'native_data':{'stage_objects':[
            {'stage':stage,'actor_state':actor,'mission':'stg110'}]}})
    g=SaveGuard(j);g.observe(s)
    m.verify_revision=lambda:None # Native executable checks tested separately.
    m.write_guard=WritePolicy(m,g,lambda memory:s)
    return j,m,b,s,g,chain,actor


def test_witness_updates_native_save_and_current_bitmap_idempotently(tmp_path):
    j,m,b,s,g,chain,actor=setup(tmp_path)
    with j:
        address=chain[-1]+0x10+40
        b.put(address,(1<<31).to_bytes(4,'big'))
        apply(m,s,g)
        assert m.read_u8(actor+0x91)==0x81
        assert m.read_u32(address)==(1<<31)|1
        count=len(b.writes);apply(m,s,g);assert len(b.writes)==count
        b.put(actor+0x91,b'\x80') # Native respawn reset.
        apply(m,s,g);assert m.read_u8(actor+0x91)==0x81


def test_old_playthrough_and_ap_counter_items_never_fill_physical_rings(tmp_path):
    j,m,b,s,g,chain,actor=setup(tmp_path)
    with j:
        j.data['bootstrap']['epoch']='new-epoch'
        j.data['receipts']=[ITEM_TABLE['10 Red Rings']]
        assert witnessed(j)=={}
        apply(m,s,g);assert not b.writes


def test_refuses_unwitnessed_bits_and_foreign_actor(tmp_path):
    j,m,b,s,g,chain,actor=setup(tmp_path)
    with j:
        with pytest.raises(MemoryUnavailable,match='witnessed collection bits'):
            m.write_bytes_verified(actor+0x91,b'\x83',expected=b'\x80',operation='physical_ring_collection')
        b.put(actor,b'\0'*4)
        assert actor+0x91 not in targets(m,s,g)[0]
        assert not b.writes


def test_journal_restart_and_level_exit_project_only_bound_save(tmp_path):
    j,m,b,s,g,chain,actor=setup(tmp_path)
    j.save();j.close()
    with Journal(tmp_path,IDENTITY) as resumed:
        g=SaveGuard(resumed)
        s=replace(s,scene='world_map',death_state='unknown')
        g.observe(s);m.write_guard=WritePolicy(m,g,lambda memory:s)
        apply(m,s,g)
        assert m.read_u32(chain[-1]+0x10+40)==1
        assert m.read_u8(actor+0x91)==0x80 # No stale stage actor write on map.
        s=replace(s,save_identity='other-save')
        g.observe(s)
        with pytest.raises(MemoryUnavailable):apply(m,s,g)


def test_unsaved_intro_restores_actor_but_never_writes_save(tmp_path):
    j,m,b,s,g,chain,actor=setup(tmp_path)
    with j:
        j.data['save_identity']=None
        j.data['bootstrap'].update(session=s.session,checks=[],observed_missions=[])
        from ..client.state import PlaythroughState
        g.state=PlaythroughState.MANDATORY_PROLOGUE
        s=replace(s,save_identity=None,save_identity_verified=False)
        m.write_guard=WritePolicy(m,g,lambda memory:s)
        apply(m,s,g)
        assert m.read_u8(actor+0x91)==0x81
        assert m.read_u32(chain[-1]+0x10+40)==0


def test_display_names_and_discovery_stage_assignment():
    assert WORLD_ITEMS[3]=='Planet Wisp Shuttle'
    assert ITEM_TABLE['Planet Wisp Shuttle']==847000003
    expected={'Cyan Laser':'Tropical Resort Act 3','Yellow Drill':'Sweet Mountain Act 1','Orange Rocket':'Sweet Mountain Act 3',
              'Blue Cube':'Starlight Carnival Act 1','Green Hover':'Starlight Carnival Act 5','Pink Spikes':'Planet Wisp Act 1','Purple Frenzy':'Asteroid Coaster Act 1'}
    for wisp,mission in expected.items():
        assert BY_MISSION[LOCATION_TABLE[wisp+' Discovery'].mission]['name']==mission
