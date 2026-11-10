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
    word(stage+0x4c,0x90050000);b.put(0x90050000,b'stg110\0')
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


@pytest.mark.parametrize('archive', ['prior_prologues','prior_playthroughs'])
def test_same_seed_archived_collections_restore_in_new_game(tmp_path,archive):
    j,m,b,s,g,chain,actor=setup(tmp_path)
    with j:
        old=dict(j.data['bootstrap'])
        j.data[archive]=[old if archive=='prior_prologues' else {'bootstrap':old}]
        j.data['bootstrap']['epoch']='new-epoch'
        j.data['receipts']=[ITEM_TABLE['10 Red Rings']]
        assert witnessed(j)=={'stg110':1}
        apply(m,s,g)
        assert m.read_u8(actor+0x91)==0x81
        assert m.read_u32(chain[-1]+0x10+40)==1
        # Unattributed event epochs do not become physical progress.
        j.data['pickup_events'].append({'kind':'red_ring','mission':'stg110','ring':2,'playthrough_epoch':'foreign'})
        assert witnessed(j)=={'stg110':1}


@pytest.mark.parametrize('disc',['SNCP8P','SNCE8P'])
@pytest.mark.parametrize('finish_scene',['gameplay','world_map'])
def test_retained_native_pickup_survives_restore_and_death_and_sends_new_check(tmp_path,monkeypatch,disc,finish_scene):
    import struct
    from ..client import native_events as n
    from ..client.physical_rings import observe_retained
    from ..client.runtime import Runtime
    from . import generate
    j,m,b,s,g,chain,actor=setup(tmp_path)
    with j:
        b.put(0x80000000,disc.encode()+bytes(2))
        m.native_patch={'physical_ring_restore':True}
        monkeypatch.setattr(n,'address',lambda memory:0x80002e00)
        base=0x80002e00-12
        row=s.evidence['native_data']['stage_objects'][0];row['player_actor_id']=123
        b.put(actor+0x38,(123).to_bytes(4,'big'))
        b.put(base,struct.pack('>3I',123,actor,0x31313003))
        # Native respawn already cleared the live byte after ring 2's pickup.
        b.put(actor+0x91,b'\x80')
        j.data['ever_collected_mask']={}  # old journal can retain events without its aggregate mask
        r=Runtime(generate({'red_ring_checks':'singles'}).worlds[1].fill_slot_data(),j,g,None)
        owner=(s.session,s.save_identity,s.stage_epoch,s.actual_mission,123,actor)
        if finish_scene=='world_map':
            s=replace(s,scene='world_map',actual_mission=None,stage_epoch=None,pickup_verified=False)
            g.observe(s);m.write_guard=WritePolicy(m,g,lambda memory:s)
        r.snapshot=s;r.pickup_started=True;r.pickup_masks[owner[2]]=0
        r._physical_ring_owner=owner
        observe_retained(r,m)
        expected=LOCATION_TABLE['Tropical Resort Act 1 - Red Ring 2'].code
        assert expected in j.data['checks'] and j.data['ever_collected_mask']['stg110']==3
        count=len(j.data['pickup_events']);observe_retained(r,m)
        assert len(j.data['pickup_events'])==count
        apply(m,s,g,r)
        if finish_scene=='gameplay':assert not b.writes
        else:assert m.read_u32(chain[-1]+0x10+40)&3==3
        assert m.read_u8(actor+0x91)==0x80
        assert m.read_u32(base+8)==0x31313003


def test_new_restore_padding_is_unreferenced_original_code(pal_dol_bytes):
    import struct
    from ..client.native_dol import Dol
    from ..world_constants import load_data
    im=Dol(pal_dol_bytes);refs=set()
    for idx,off,base,size in im.sections:
        for i in range(0,size-3,4):
            word=struct.unpack_from('>I',im.data,off+i)[0];refs.add(word)
            if idx<7 and word>>26 in (16,18):
                mask,sign=(0xfffc,0x8000) if word>>26==16 else (0x3fffffc,0x2000000)
                delta=word&mask
                if delta&sign:delta-=sign*2
                refs.add(delta if word&2 else base+i+delta)
    for row in load_data('physical_ring_restore_sites.json'):
        a=row['address']
        assert im.read(a-4,4).hex()==row['before']=='4e800020'
        assert im.read(a,8)==bytes(8)
        assert im.read(a+8,4).hex()==row['after']
        assert a not in refs and a+4 not in refs


def test_host_publishes_only_restore_mailbox_and_rejects_unwitnessed_mask(tmp_path,monkeypatch):
    from types import SimpleNamespace
    from ..client import native_events as n
    from ..client.physical_rings import publish_restore
    j,m,b,s,g,chain,actor=setup(tmp_path)
    with j:
        m.native_patch={'physical_ring_restore':True}
        monkeypatch.setattr(n,'address',lambda memory:0x80002e00)
        base=0x80002e00-12;b.put(base,bytes(12))
        s.evidence['native_data']['stage_objects'][0]['player_actor_id']=123
        b.put(actor+0x38,(123).to_bytes(4,'big'))
        runtime=SimpleNamespace(snapshot=s,guard=g,journal=j)
        publish_restore(runtime,m)
        assert m.read_u32(base)==123 and m.read_u32(base+4)==actor and m.read_u32(base+8)==0x31313001
        assert all(base<=a<base+12 for a,data in b.writes)
        assert m.read_u8(actor+0x91)==0x80
        with pytest.raises(MemoryUnavailable):
            m.write_u32(base+8,31,expected=1,operation='physical_ring_restore')
