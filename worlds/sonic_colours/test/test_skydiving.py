from collections import Counter
from pathlib import Path
import pytest
from ..client import skydiving as s


@pytest.mark.parametrize('locked',[0,1])
def test_native_update_tail_calls_fall_or_preserves_diving(locked):
    words,offset=s.payload();base=0x80002000;stack=0x90003000
    regs=list(range(32));regs[1]=stack;regs[3]=0x90010000;regs[4]=0x90020000
    initial=regs[:];lr=0x80012340;pc=0;cmp=0;ctr=0;tail=False
    for _ in range(25):
        w=words[pc];pc+=1
        if not w:break
        op=w>>26;rt=w>>21&31;ra=w>>16&31;u=w&65535;imm=u-65536 if u&32768 else u
        if w==0x7c0802a6:regs[0]=lr
        elif w==0x48000005:lr=base+pc*4
        elif w==0x7d8802a6:regs[12]=lr
        elif op==32:
            assert regs[ra]+imm==base+offset;regs[rt]=locked
        elif w==0x7c0803a6:lr=regs[0]
        elif op==11:cmp=(regs[ra]>imm)-(regs[ra]<imm)
        elif op==16:
            if cmp!=0:pc=pc-1+imm//4
        elif w==0x7c832378:regs[3]=regs[4]
        elif op==14:regs[rt]=((regs[ra] if ra else 0)+imm)&0xffffffff
        elif op==15:regs[rt]=(imm<<16)&0xffffffff
        elif op==24:regs[ra]=regs[rt]|u
        elif w==0x7d8903a6:ctr=regs[12]
        elif w==0x4e800420:tail=True;break
        elif w==s.ORIGINAL:regs[1]-=16
        elif op==18:pc=pc-1+(w&0x3fffffc)//4
        elif w==0x60000000:pass
        else:raise AssertionError(hex(w))
    assert lr==0x80012340
    assert regs[13:]==initial[13:]
    assert tail==bool(locked)
    if locked:
        assert ctr==0x80033878 and regs[3]==initial[4] and regs[4]==15
        assert regs[1]==stack  # tail call has no unfinished native frame
    else:
        assert regs[3:6]==initial[3:6] and regs[1]==stack-16


@pytest.mark.parametrize('count',[0,1,2])
def test_item_permission_updates_existing_menu_independent_lock(monkeypatch,count):
    monkeypatch.setattr(s,'installed_data',lambda m:0x80002800)
    writes=[]
    class Memory:
        def read_u32(self,a):return 1
        def write_u32(self,a,v,**kw):writes.append((a,v,kw))
    result=s.configure(Memory(),None,{'counts':Counter({'Skydiving':count})})
    assert result['locked']==(count==0)
    assert len(writes)==int(count>0)
    if writes:assert writes[0]==(0x80002800,0,{'expected':1,'operation':'skydiving'})


def test_item_and_native_callback_evidence():
    from ..Items import ITEM_TABLE,MOVEMENT_POOL,classification
    from ..world_constants import BASE_ID
    from BaseClasses import ItemClassification
    assert ITEM_TABLE['Skydiving']==BASE_ID+51
    assert MOVEMENT_POOL.count('Skydiving')==1
    assert classification('Skydiving')==ItemClassification.progression
    from ..tools.ppc import Executable
    path=Path(__file__).parents[1]/'notes/Sonic_Colours_PAL_Static_RE_v2/sonic_pal_disassembly.elf'
    if not path.exists():pytest.skip('original executable absent')
    e=Executable(path)
    assert e.read(s.HOOK,4)==s.ORIGINAL.to_bytes(4,'big')
    assert e.read(0x807767d8+0x34,4)==s.HOOK.to_bytes(4,'big')
    assert e.read(0x80072B18,16)==bytes.fromhex('80630064 2C030000 4D820020 38800002')


@pytest.mark.parametrize('authorized',[True,False])
@pytest.mark.parametrize('address',[0x80002800,0x80002804])
def test_permission_word_requires_attributed_living_actor(monkeypatch,authorized,address):
    from types import SimpleNamespace
    from ..client.state import WritePolicy
    from ..client.memory import MemoryUnavailable
    from ..client import movement_gate
    memory=SimpleNamespace(verify_revision=lambda:None)
    snap=SimpleNamespace(scene='gameplay',scene_verified=True,death_state='alive',stable_polls=1,
        progress_verified=False,evidence={'native_data':{'stage_objects':[{'player':{'actor':0x90001000}}]}})
    guard=SimpleNamespace(can_record_pickups=lambda snap:authorized)
    monkeypatch.setattr(s,'installed_data',lambda m:0x80002800)
    monkeypatch.setattr(movement_gate,'observed',lambda m,p:{'request_machine':0x90002000})
    policy=WritePolicy(memory,guard,lambda m:snap)
    if authorized and address==0x80002800:
        assert policy('skydiving',address,4)[1]==0x90002000
    else:
        with pytest.raises(MemoryUnavailable,match='WRITE_BLOCKED'):
            policy('skydiving',address,4)
