"""Offline emitted-PPC tests; native UI/GPU behavior requires Dolphin."""
import struct
from pathlib import Path
from types import SimpleNamespace

import pytest

from ..client import map_refresh
from ..client.memory import SonicMemory, MemoryUnavailable
from .test_memory import FakeBackend


def execute(zone=1, phase=9, profile=1, actor_matches=True, lock=True):
    words, offset = map_refresh.payload()
    base, actor, owner = 0x80002000, 0x90010000, 0x90020000
    r = list(range(32)); r[1] = 0x90050000; r[27] = actor
    stack = r[1]; lr = 0; ctr = 0; cmp = 0; pc = 0
    lock_address = actor+0xb0+zone*8
    mem = {base+offset: actor if actor_matches else actor+4, base+offset+4:zone,
           base+offset+8:owner, base+offset+12:1, owner:profile,
           actor+0x10f0:phase, lock_address+4:0x90060000 if lock else 0,
           actor+0x90:0x90070000, actor+0x110c:2, actor+0x18c:0x90080000,
           0x90080010:0x90090000, 0x90090008:0x900a0000, 0x900a00c0:0x80301000}
    calls = []; names = {}
    def native(target):
        calls.append((target, r[3], r[4], r[5]))
        result = 0
        if target == 0x805E7EE4:
            assert r[3] == mem[actor+0x90] and r[4] == lock_address
        elif target == 0x805E9D80:
            assert r[3] == lock_address and r[4] == 0
            mem[lock_address+4] = 0
        elif target == 0x80301000: result = 0x900b0000
        elif target == 0x80379820:
            assert r[5] == zone+1
            names[r[3]] = f'chain{r[5]:02d}_'+('on' if r[4] == 0x80722ACE else 'off')
        elif target == 0x8026399C:
            assert mem[r[3]] == 0x900b0000
            assert names[r[4]] == f'chain{zone+1:02d}_'+('on' if r[5] == 0 else 'off')
        else: raise AssertionError(hex(target))
        # Exercise the ABI: these calls may clobber every volatile GPR.
        for i in (0,3,4,5,6,7,8,9,10,11,12): r[i] = 0xfeed0000+i
        r[3] = result
    for _ in range(300):
        w = words[pc]; pc += 1
        if not w: break
        op = w>>26; rt = w>>21&31; ra=w>>16&31; rb=w>>11&31
        imm=w&0xffff; imm=imm if imm<0x8000 else imm-0x10000
        if op in (14,15): r[rt] = ((r[ra] if ra else 0)+(imm if op==14 else imm<<16))&0xffffffff
        elif op == 24: r[ra] = r[rt]|(w&0xffff)
        elif op in (32,34): r[rt]=mem.get((r[ra]+imm)&0xffffffff,0)
        elif op in (36,37):
            address=(r[ra]+imm)&0xffffffff;mem[address]=r[rt]
            if op==37:r[ra]=address
        elif op==11:cmp=(r[ra]>imm)-(r[ra]<imm)
        elif op==16:
            take={0x40820000:cmp!=0,0x41820000:cmp==0,0x41800000:cmp<0,0x41810000:cmp>0}[w&0xffff0000]
            if take:pc=pc-1+imm//4
        elif op==18:
            delta=w&0x3fffffc
            if delta&0x2000000:delta-=0x4000000
            if w&1:lr=base+pc*4
            pc=pc-1+delta//4
        elif op==21:r[ra]=(r[rt]<<rb)&0xffffffff  # emitted slwi only
        elif w==0x7fa802a6:r[29]=lr
        elif w==0x7d8903a6:ctr=r[12]
        elif w==0x4e800421:native(ctr)
        elif w==0x4cc63182 or w==0x60000000:pass
        elif op==31 and w&0x7ff==0:cmp=(r[ra]>r[rb])-(r[ra]<r[rb])
        elif op==31 and w&0x7ff==0x378:r[ra]=r[rt]|r[rb]
        elif op==31 and w&0x7ff==0x214:r[rt]=(r[ra]+r[rb])&0xffffffff
        elif op==31 and w&0x7ff==0x2e:r[rt]=mem[r[ra]+r[rb]]
        else:raise AssertionError(hex(w))
    else:raise AssertionError('PPC loop')
    assert r[1]==stack and r[11]==stack+0x2e0 and r[27]==actor
    return calls, mem[base+offset], mem[lock_address+4]


@pytest.mark.parametrize('zone',range(1,7))
def test_only_requested_lock_and_chain_are_refreshed(zone):
    calls, request, lock = execute(zone)
    assert [c[0] for c in calls][:2]==[0x805E7EE4,0x805E9D80]
    assert not request and not lock
    assert len(calls)==(2 if zone==6 else 7)


@pytest.mark.parametrize('args',[{'phase':8},{'phase':10},{'profile':2},{'actor_matches':False},{'zone':0},{'zone':7}])
def test_scene_transition_wrong_owner_and_invalid_zone_never_call_native(args):
    assert execute(**args)[0]==[]


def test_already_released_lock_deduplicates():
    assert execute(lock=False)==([],0,0)


def install(backend):
    words, offset = map_refresh.payload(); target=0x80002000
    words[-1]=0x48000000|((map_refresh.HOOK+4-(target+len(words)*4-4))&0x3fffffc)
    backend.put(target,struct.pack('>'+'I'*len(words),*words))
    backend.put(map_refresh.HOOK,(0x48000000|((target-map_refresh.HOOK)&0x3fffffc)).to_bytes(4,'big'))
    return target+offset


def test_host_only_arms_owned_lock_and_preserves_actor_save_bytes(monkeypatch):
    from ..client import native_read
    b=FakeBackend(); m=SonicMemory(b); data=install(b);actor=0x90010000
    chain=(0x90020000,0x90030000,1,0x90040000,0x9004001c)
    m.resolve_flags_ptr=lambda:chain
    b.put(actor,(0x80777000).to_bytes(4,'big'))
    b.put(actor+0x10f0,(9).to_bytes(4,'big'))
    for zone in range(1,7):b.put(actor+0xb4+zone*8,(0x90050000+zone*16).to_bytes(4,'big'))
    monkeypatch.setattr(native_read,'read_actors',lambda memory,context:[actor])
    snapshot=SimpleNamespace(scene='global_map',evidence={'native_data':{'stage_objects':[{'context':0x90060000}]}})
    m.write_guard=lambda *args:('bound',data,(actor,),chain)
    before=m.read_bytes(actor,0x1374)
    assert map_refresh.configure(m,snapshot,{20:True})=={'available':True}
    assert not b.writes
    b.put(chain[-1]+0x10,(1<<23).to_bytes(4,'big'))
    status=map_refresh.configure(m,snapshot,{23:True})
    assert status['requested_zone']==3 and m.read_u32(data)==actor
    assert m.read_bytes(actor,0x1374)==before
    assert {address for address,_ in b.writes} <= set(range(data,data+16,4))


def test_write_rejects_other_world_and_bad_owner():
    b=FakeBackend();m=SonicMemory(b);data=install(b);actor=0x90010000
    chain=(0x90020000,0x90030000,1,0x90040000,0x9004001c)
    m.write_guard=lambda *args:('bound',data,(actor,),chain)
    b.put(data+4,(3).to_bytes(4,'big'));b.put(data+8,chain[1].to_bytes(4,'big'));b.put(data+12,(1).to_bytes(4,'big'))
    with pytest.raises(MemoryUnavailable,match='unauthorized'):
        m.write_u32(data,actor,expected=0,operation='global_map_refresh')
    with pytest.raises(MemoryUnavailable,match='unauthorized'):
        m.write_u32(data+8,actor,expected=chain[1],operation='global_map_refresh')
    assert not b.writes


def test_original_pal_epilogue_and_chain_formats():
    elf=Path(__file__).parents[1]/'notes/Sonic_Colours_PAL_Static_RE_v2/sonic_pal_disassembly.elf'
    if not elf.exists():pytest.skip('private executable absent')
    from ..tools.ppc import Executable
    e=Executable(elf)
    assert e.read(map_refresh.HOOK,4)==map_refresh.ORIGINAL.to_bytes(4,'big')
    assert e.read(0x80722ACE,13)==b'chain%02d_on\0'
    assert e.read(0x80722ADB,14)==b'chain%02d_off\0'
    assert e.read(0x802671B4,4)==(0x48380D31).to_bytes(4,'big')  # native lock animation call


def test_new_thunk_exact_text_verification_with_original_capture():
    from .test_native_originals import PAIRS
    from .test_pickup_integration import Overlay
    if not PAIRS:pytest.skip('private captures absent')
    b=Overlay(PAIRS[0]);m=SonicMemory(b)
    words,offset=map_refresh.payload();target=0x80002000
    words[-1]=0x48000000|((map_refresh.HOOK+4-(target+len(words)*4-4))&0x3fffffc)
    b.write_bytes(target,struct.pack('>'+'I'*len(words),*words))
    b.write_bytes(map_refresh.HOOK,(0x48000000|((target-map_refresh.HOOK)&0x3fffffc)).to_bytes(4,'big'))
    m.verify_revision()
    b.write_bytes(target+4,bytes(4))
    with pytest.raises(MemoryUnavailable,match='unknown_revision'):m.verify_revision()


def test_policy_rejects_transition_and_wrong_address(monkeypatch):
    from ..client.state import WritePolicy
    from ..client import native_read
    b=FakeBackend();m=SonicMemory(b);data=install(b);actor=0x90010000
    chain=(0x90020000,0x90030000,1,0x90040000,0x9004001c)
    m.verify_revision=lambda:None;m.resolve_flags_ptr=lambda:chain
    b.put(actor,(0x80777000).to_bytes(4,'big'))
    monkeypatch.setattr(native_read,'read_actors',lambda memory,context:[actor])
    s=SimpleNamespace(scene='global_map',save_identity='fixture',evidence={'chain':chain,'native_data':{'stage_objects':[{'context':0x90060000}]}})
    guard=SimpleNamespace(check=lambda snapshot:'explicit test-bound save')
    policy=WritePolicy(m,guard,lambda memory:s)
    assert policy('global_map_refresh',data+4,4)[2]==(actor,)
    with pytest.raises(MemoryUnavailable,match='address changed'):policy('global_map_refresh',actor+0xbc,4)
    s.scene='world_map'
    with pytest.raises(MemoryUnavailable,match='Grand World Map'):policy('global_map_refresh',data+4,4)
