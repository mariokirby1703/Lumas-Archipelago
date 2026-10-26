"""Actual request-hook instruction execution; no claim of Dolphin input validation."""

from ..tools.private_assets import reference_root
import pytest
from ..client import movement_gate as g
from ..client.memory import SonicMemory, MemoryUnavailable
from .test_memory import FakeBackend


@pytest.mark.parametrize('separation', [0x40, 0x10000, -0x10000])
def test_actor_owned_machine_ignores_allocation_adjacency(separation):
    m = SonicMemory(FakeBackend()); player=0x90050000; controller=0x90020000
    state_owner=0x90030000; machine=controller+separation
    for address,value in ((player,g.PLAYER_VTABLE),(player+0x90,controller),
                          (controller,g.CONTROLLER_VTABLE),(controller+4,player),
                          (player+0x70,state_owner),(state_owner+8,machine),
                          (machine,g.STATE_MACHINE_VTABLE),(machine+0x28,player),
                          (machine+0x1c,2),(machine+0x20,2)):
        m.backend.write_bytes(address,value.to_bytes(4,'big'))
    assert g.observed(m,player)['request_machine']==machine
    assert g.observed(m,player)['requested_id']==2
    m.backend.write_bytes(machine+0x28,(player+4).to_bytes(4,'big'))
    with pytest.raises(MemoryUnavailable,match='state-machine ownership'):g.observed(m,player)


@pytest.mark.parametrize('requested', list(g.STATE_PERMISSION)+[2,3,31,60,128,0xffffffff])
@pytest.mark.parametrize('mask', [0,1,127,128,256,511,512,1023,1024,2047])
@pytest.mark.parametrize('rail_side',[True,False])
@pytest.mark.parametrize('underwater', [True,False])
@pytest.mark.parametrize('previous', [2,38,41,0xffffffff,0x90010000])
@pytest.mark.parametrize('same_owner', [True,False])
@pytest.mark.parametrize('host_machine_matches',[True,False])
def test_encoded_gate_preserves_original_request_flow(requested,mask,previous,same_owner,underwater,host_machine_matches,rail_side):
    words,_,off=g.payload(gecko=True); base=0x80002000; machine=0x90010000; player=0x90020000
    regs=list(range(32));regs[1]=0x90030000;regs[3]=machine+0x14;regs[31]=0x90040000;regs[4]=requested
    saved=regs[:]; lr=0x80012340;cr=0x12345678;pc=0;cmp=0;mem={}
    def store(a,v):
        for i,b in enumerate((v&0xffffffff).to_bytes(4,'big')):mem[a+i]=b
    def load(a):return int.from_bytes(bytes(mem.get(a+i,0) for i in range(4)),'big')
    for i,w in enumerate(words):store(base+i*4,w)
    for a,v in ((machine,g.STATE_MACHINE_VTABLE),(machine+0x28,player if same_owner else player+4),
                (machine+0x20,previous),(base+off,machine if host_machine_matches else machine+0x1000),(base+off+4,mask)):
        store(a,v)
    if host_machine_matches is None:store(base+off,g.MENU_POLICY_ARMED)
    store(player+0x88,player+0x300);store(player+0x34c,8 if rail_side else 0)
    store(player+0x8c,player+0x100);store(player+0x110,0x800 if underwater else 0)
    store(player,g.PLAYER_VTABLE);store(player+0x70,player+0x200);store(player+0x208,machine)
    for _ in range(300):
        w=words[pc];pc+=1
        if not w:break
        op=w>>26;rt=w>>21&31;ra=w>>16&31;rb=w>>11&31;u=w&65535;imm=u if u<32768 else u-65536
        if op==14:regs[rt]=((regs[ra] if ra else 0)+imm)&0xffffffff
        elif op==15:regs[rt]=((regs[ra] if ra else 0)+(imm<<16))&0xffffffff
        elif op==24:regs[ra]=regs[rt]|u
        elif op==27:regs[ra]=regs[rt]^(u<<16)
        elif op==21:
            shift=(w>>11)&31;mb=(w>>6)&31;me=(w>>1)&31
            mask_bits=sum(1<<(31-i) for i in range(32) if (mb<=i<=me if mb<=me else i>=mb or i<=me))
            regs[ra]=((regs[rt]<<shift)|(regs[rt]>>(32-shift)))&mask_bits&0xffffffff
        elif op==28:
            regs[ra]=regs[rt]&u;cmp=int(regs[ra]>0)
        elif op==32:regs[rt]=load((regs[ra]+imm)&0xffffffff)
        elif op in (36,37):
            address=(regs[ra]+imm)&0xffffffff;store(address,regs[rt])
            if op==37:regs[ra]=address
        elif op in (46,47):
            address=regs[ra]+imm
            for r in range(rt,32):
                if op==47:store(address+(r-rt)*4,regs[r])
                else:regs[r]=load(address+(r-rt)*4)
        elif op in (10,11):
            lhs=regs[ra];rhs=u if op==10 else imm
            if op==11 and lhs&0x80000000:lhs-=0x100000000
            cmp=(lhs>rhs)-(lhs<rhs)
        elif op==16:
            take={0x41820000:cmp==0,0x40820000:cmp!=0,0x41810000:cmp>0,0x40810000:cmp<=0}[w&0xffff0000]
            if take:pc=pc-1+imm//4
        elif op==18:
            delta=w&0x3fffffc
            if delta&0x2000000:delta-=0x4000000
            if w&1:lr=base+pc*4
            pc=pc-1+delta//4
        elif w==0x7fa802a6:regs[29]=lr
        elif w==0x7fa803a6:lr=regs[29]
        elif w==0x7d600026:regs[11]=cr
        elif w==0x7d6802a6:regs[11]=lr
        elif w==0x7d8802a6:regs[12]=lr
        elif w==0x7d6ff120:cr=regs[11]
        elif w==0x7d6803a6:lr=regs[11]
        elif op==31 and w&0x7ff==48:regs[ra]=(regs[rt] << (regs[rb]&31))&0xffffffff
        elif op==31 and ((w>>1)&1023)==0:cmp=(regs[ra]>regs[rb])-(regs[ra]<regs[rb])
        elif op==31 and ((w>>1)&1023)==444:regs[ra]=regs[rt]|regs[rb]
        elif op==31 and ((w>>1)&1023)==87:regs[rt]=mem.get(regs[ra]+regs[rb],0)
        elif op==31 and ((w>>1)&1023)==28:
            regs[ra]=regs[rt]&regs[rb];cmp=(regs[ra]>0)-(regs[ra]<0)
        elif w==0x4c421182:cmp=1
        elif w==0x4d820020:
            if cmp==0:break
        elif w==0x60000000:pass
        else:raise AssertionError(hex(w))
    else:raise AssertionError('instruction loop')
    bit=8 if requested==8 and underwater else g.STATE_PERMISSION.get(requested,0)
    required=1536 if requested==29 and rail_side else 1<<bit
    deny=same_owner and requested in g.STATE_PERMISSION and (mask & required)!=required
    native_entry=not deny or requested in (38,41,48)
    assert regs[1]==saved[1]-(0xc0 if native_entry else 0)
    assert regs[4]==(3 if deny else requested)
    assert load(machine+0x20)==previous  # no direct state-field edits
    assert lr==0x80012340 and cr==0x12345678
    assert all(regs[i]==saved[i] for i in range(32) if i not in (1,4))



@pytest.mark.parametrize('mask',[0,1,512,1024])
def test_menu_activation_applies_on_first_native_request(mask):
    test_encoded_gate_preserves_original_request_flow(8,mask,2,True,False,None,False)


@pytest.mark.parametrize('mask',[0,2048,4095])
@pytest.mark.parametrize('previous',[3,48])
def test_quick_step_permission_and_native_run_exit(mask,previous):
    test_encoded_gate_preserves_original_request_flow(48,mask,previous,True,False,None,False)


def test_quick_step_append_only_progression_item():
    from ..Items import ITEM_TABLE,MOVEMENT_POOL,classification
    from ..world_constants import BASE_ID
    from BaseClasses import ItemClassification
    from collections import Counter
    assert ITEM_TABLE['Quick Step']==BASE_ID+52
    assert MOVEMENT_POOL.count('Quick Step')==1
    assert classification('Quick Step')==ItemClassification.progression
    assert g.permissions(Counter({'Quick Step':1}))==2048


def test_map_preloads_new_items_without_a_living_actor(monkeypatch):
    from collections import Counter
    from ..client.state import Snapshot
    from ..client import skydiving
    m=SonicMemory(FakeBackend());data=0x80002000;sky=0x80002800
    monkeypatch.setattr(g,'installed_data',lambda *args:(data,'fixture C2'))
    monkeypatch.setattr(skydiving,'installed_data',lambda *args:sky)
    m.write_guard=lambda *args:'bound fixture save'
    m.backend.write_bytes(sky,(1).to_bytes(4,'big'))  # previous stage locked
    snap=Snapshot('session','save',1,'world_map',None,scene_verified=True,stable_polls=1)
    owned={'counts':Counter({'Progressive Skydiving':1,'Double Jump':1})}
    result=g.configure(m,snap,owned)
    assert result['menu_policy_preloaded'] and result['request_machine'] is None
    assert m.read_u32(sky)==0  # item takes effect before entering Aquarium Park
    assert m.read_u32(data)==g.MENU_POLICY_ARMED and m.read_u32(data+4)==1
    owned['counts']['Double Jump']=0
    g.configure(m,snap,owned)
    assert m.read_u32(data+4)==0 and m.read_u32(data)==g.MENU_POLICY_ARMED


def test_complete_v11_profile_recovers_exact_pal_text_and_rejects_corruption():
    from pathlib import Path
    from ..tools.ppc import Executable
    from ..client.versions import VERSION, verify_revision
    from ..client.native_hook_table import hook_rows
    from ..client import capsule_refresh, map_refresh
    p=reference_root()/'Sonic_Colours_PAL_Static_RE_v2/sonic_pal_disassembly.elf'
    if not p.exists():pytest.skip('original PAL executable absent')
    e=Executable(p);regions={0x80000000:bytearray(b'SNCP8P\0\0'),0x80001000:bytearray(0x3000)}
    for section in VERSION['text_sections']:
        regions[section['address']]=bytearray(e.read(section['address'],section['size']))
    class Backend:
        def read_bytes(self,a,n):
            for base,raw in regions.items():
                if base<=a and a+n<=base+len(raw):return bytes(raw[a-base:a-base+n])
            return bytes(n)
        def write_bytes(self,a,value):
            for base,raw in regions.items():
                if base<=a and a+len(value)<=base+len(raw):
                    raw[a-base:a-base+len(value)]=value;return
            raise AssertionError(hex(a))
    b=Backend();rows=hook_rows();i=0;cursor=0x80001800;targets={}
    while i<len(rows):
        first,count=rows[i];i+=1
        if first>>24!=0xc2:continue
        hook=0x80000000+(first&0xffffff);target=cursor+8
        words=[w for pair in rows[i:i+count] for w in pair];i+=count
        words[-1]=0x48000000|((hook+4-(target+len(words)*4-4))&0x3fffffc)
        b.write_bytes(cursor,first.to_bytes(4,'big')+count.to_bytes(4,'big'))
        b.write_bytes(target,b''.join(w.to_bytes(4,'big') for w in words))
        b.write_bytes(hook,(0x48000000|((target-hook)&0x3fffffc)).to_bytes(4,'big'))
        cursor=target+len(words)*4;targets[hook]=target
    m=SonicMemory(b)
    assert map_refresh.HOOK in targets
    assert verify_revision(m)==VERSION['dol_sha256']
    assert capsule_refresh.inspect_installed(m)['variant']=='current_compact_white_collision_refresh'
    target=targets[g.HOOK]
    b.write_bytes(target+4,(int.from_bytes(b.read_bytes(target+4,4),'big')^1).to_bytes(4,'big'))
    with pytest.raises(MemoryUnavailable):verify_revision(m)


def test_same_controller_new_machine_rearms_per_stage(monkeypatch):
    from collections import Counter
    from ..client.state import Snapshot
    backend=FakeBackend();m=SonicMemory(backend);data=0x80002000
    player=0x90010000;ctrl=0x90020000;owner=0x90030000
    def setup(machine):
        for a,v in ((player,g.PLAYER_VTABLE),(player+0x90,ctrl),
                    (ctrl,g.CONTROLLER_VTABLE),(ctrl+4,player),(player+0x70,owner),
                    (owner+8,machine),(machine,g.STATE_MACHINE_VTABLE),
                    (machine+0x28,player),(machine+0x1c,2),(machine+0x20,2)):
            backend.write_bytes(a,v.to_bytes(4,'big'))
    monkeypatch.setattr(g,'installed_data',lambda *args:(data,'fixture C2'))
    m.write_guard=lambda *args:True
    from ..client.skydiving import HOOK,ORIGINAL
    m.backend.write_bytes(HOOK,ORIGINAL.to_bytes(4,'big'))
    def scene(epoch):return Snapshot('session','save',1,'gameplay','stg110',
        stage_epoch=epoch,scene_verified=True,stable_polls=3,death_state='alive',
        evidence={'native_data':{'stage_objects':[{'player':{'actor':player}}]}})
    setup(0x90040000)
    for _ in range(3):g.configure(m,scene('act1'),{'counts':Counter()})
    assert m.read_u32(data)==0x90040000
    setup(0x90050000)
    g.configure(m,scene('act2'),{'counts':Counter()})
    assert m.read_u32(data)==0x90050000  # exact newly verified owner armed on first poll
    for _ in range(2):g.configure(m,scene('act2'),{'counts':Counter()})
    assert m.read_u32(data)==0x90050000
    assert m.read_u32(data)!=ctrl


def test_confirmed_gate_survives_transient_reads_without_new_write_authority(monkeypatch):
    from collections import Counter
    from dataclasses import replace
    from ..client.state import Snapshot
    m=SonicMemory(FakeBackend());data=0x80003000;player=0x90050000;ctrl=0x90020000
    state_owner=0x90030000;machine=0x90040000
    for a,v in ((player,g.PLAYER_VTABLE),(player+0x90,ctrl),(ctrl,g.CONTROLLER_VTABLE),
                (ctrl+4,player),(player+0x70,state_owner),(state_owner+8,machine),
                (machine,g.STATE_MACHINE_VTABLE),(machine+0x28,player),
                (machine+0x1c,2),(machine+0x20,2)):
        m.backend.write_bytes(a,v.to_bytes(4,'big'))
    monkeypatch.setattr(g,'installed_data',lambda *args:(data,'fixture C2'))
    writes=[]
    from ..client.skydiving import HOOK,ORIGINAL
    m.backend.write_bytes(HOOK,ORIGINAL.to_bytes(4,'big'))
    def check(*args):writes.append(args);return True
    m.write_guard=check
    s=Snapshot('session','save',1,'gameplay','stg130',stage_epoch='same-stage',
        scene_verified=True,stable_polls=3,death_state='alive',
        evidence={'native_data':{'stage_objects':[{'player':{'actor':player}}]}})
    owned={'counts':Counter()}
    for _ in range(3):g.configure(m,s,owned)
    assert m.read_u32(data)==machine
    writes.clear()
    missing=replace(s,death_state='unknown',stable_polls=1,
        evidence={'native_data':{'stage_objects':[{}]}})
    assert g.configure(m,missing,owned)['host_writes_deferred']
    assert m.read_u32(data)==machine and not writes
    # Native transition sentinels cannot revoke this independently owned machine.
    m.backend.write_bytes(machine+0x1c,(0xffffffff).to_bytes(4,'big'))
    m.backend.write_bytes(machine+0x20,(0xffffffff).to_bytes(4,'big'))
    result=g.configure(m,replace(s,stable_polls=1),owned)
    assert result['same_stage_authorization_retained']
    assert m.read_u32(data)==machine and not writes
    # A different stage is independently revalidated on its first sample.
    g.configure(m,replace(s,stage_epoch='next-stage',stable_polls=1),owned)
    assert m.read_u32(data)==machine
    m.backend.write_bytes(machine+0x28,(player+4).to_bytes(4,'big'))
    with pytest.raises(MemoryUnavailable,match='ownership'):
        g.configure(m,replace(s,stage_epoch='wrong-owner',stable_polls=1),owned)


@pytest.mark.parametrize('mask',[0,4096])
def test_fast_dive_native_request(mask):
    test_encoded_gate_preserves_original_request_flow(110,mask,109,True,False,None,False)


@pytest.mark.parametrize('mask',[0,8192])
def test_spikes_charge_cancelled_before_state_entry(mask):
    test_encoded_gate_preserves_original_request_flow(82,mask,79,True,False,None,False)


@pytest.mark.parametrize('requested',[29,30,48])
@pytest.mark.parametrize('previous',[0xffffffff,29,30,48])
def test_spammed_requests_cannot_use_pending_minus_one_as_a_bypass(requested,previous):
    test_encoded_gate_preserves_original_request_flow(requested,0,previous,True,False,None,False)


def test_direction_held_without_press_still_needs_rail_switch():
    test_encoded_gate_preserves_original_request_flow(29,512,28,True,False,None,True)
    test_encoded_gate_preserves_original_request_flow(29,1536,28,True,False,None,True)


def test_funded_air_boost_uses_same_permission_as_jump_dash():
    from pathlib import Path
    from ..tools.ppc import Executable
    assert g.STATE_PERMISSION[9]==g.STATE_PERMISSION[10]==1
    e=Executable(reference_root()/'Sonic_Colours_PAL_Static_RE_v2/sonic_pal_disassembly.elf')
    # Native constructor installs CStateAirBoost and registers it as ID 10.
    assert int.from_bytes(e.read(0x80033ff8,4),'big')==0x3863C960
    assert int.from_bytes(e.read(0x80034018,4),'big')==0x3880000A
    for request in (9,10):
        for owned in (0,2):
            test_encoded_gate_preserves_original_request_flow(request,owned,3,True,False,True,False)
