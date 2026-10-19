from ..tools.private_assets import reference_root
from collections import Counter
from types import SimpleNamespace
import pytest
from ..client import stunts as s


@pytest.mark.parametrize('level',range(6))
@pytest.mark.parametrize('performed',range(6))
def test_progressive_native_counter_gate_preserves_launch_arguments(level,performed):
    words,offset=s.payload();base=0x80002000;stack=0x90003000
    regs=[0]*32;regs[1]=stack;regs[3]=0x90010000;regs[4]=0x90020000;regs[5]=1
    before=regs[:];lr=0x80012340;cmp=0;pc=0;returned=False
    for _ in range(24):
        w=words[pc];pc+=1
        if w==0:break
        if w==0x7c0802a6:regs[0]=lr
        elif w==0x48000005:lr=base+pc*4
        elif w==0x7d8802a6:regs[12]=lr
        elif w==0x818c0028:
            assert regs[12]+0x28==base+offset;regs[12]=level
        elif w==0x7c0803a6:lr=regs[0]
        elif w==0x8003022c:regs[0]=performed
        elif w==0x7c006040:cmp=(regs[0]>regs[12])-(regs[0]<regs[12])
        elif w==0x4180000c:
            if cmp<0:pc+=2
        elif w==0x38600000:regs[3]=0
        elif w==0x4e800020:returned=True;break
        elif w==s.ORIGINAL:regs[1]-=0xa0
        elif w==0x48000008:pc+=1
        else:raise AssertionError(hex(w))
    allowed=performed<level
    assert lr==0x80012340 and regs[4:6]==before[4:6]
    assert returned==(not allowed)
    assert regs[3]==(before[3] if allowed else 0)
    assert regs[1]==(stack-0xa0 if allowed else stack)


@pytest.mark.parametrize('count,movement',[(i,True) for i in range(8)]+[(0,False)])
def test_stunts_inventory_and_off_mode(monkeypatch,count,movement):
    monkeypatch.setattr(s,'installed_data',lambda m:0x80002800)
    expected=min(5,count) if movement else 5
    class Memory:
        def read_u32(self,a):return 0
        def write_u32(self,a,v,**kw):
            assert a==0x80002800 and v==expected
            assert kw=={'expected':0,'operation':'stunts'}
    result=s.configure(Memory(),None,{'counts':Counter({'Progressive Stunts':count})},{'options':{'movement_unlocks':movement}})
    assert result['level']==expected and result['allowed']==bool(expected)
    assert result['maximum_quality']==(s.LABELS[expected-1] if expected else None)


def test_stunts_append_only_progression_and_native_counter():
    from pathlib import Path
    from ..Items import ITEM_TABLE,MOVEMENT_POOL,classification
    from ..world_constants import BASE_ID
    from BaseClasses import ItemClassification
    assert ITEM_TABLE['Progressive Stunts']==BASE_ID+48
    assert MOVEMENT_POOL.count('Progressive Stunts')==5
    assert classification('Progressive Stunts')==ItemClassification.progression
    from ..tools.ppc import Executable
    path=reference_root()/'Sonic_Colours_PAL_Static_RE_v2/sonic_pal_disassembly.elf'
    if path.exists():
        e=Executable(path)
        assert e.read(s.HOOK,4)==s.ORIGINAL.to_bytes(4,'big')
        assert e.read(0x80148484,4)==bytes.fromhex('807C022C')


@pytest.mark.parametrize('authorized',[True,False])
def test_prologue_stunts_write_requires_verified_native_actor(monkeypatch,authorized):
    from ..client.state import WritePolicy
    from ..client.memory import MemoryUnavailable
    from ..client import movement_gate
    memory=SimpleNamespace(verify_revision=lambda:None)
    snap=SimpleNamespace(scene='gameplay',scene_verified=True,death_state='alive',stable_polls=1,
                         session='native-session',stage_epoch='intro-act1',
                         evidence={'native_data':{'stage_objects':[{'player':{'actor':0x90001000}}]}})
    def persistent_check(s):raise MemoryUnavailable('save_not_bound_or_session_changed')
    guard=SimpleNamespace(can_record_pickups=lambda s:authorized,check=persistent_check)
    monkeypatch.setattr(s,'installed_data',lambda m:0x80002800)
    def observed(m,player):
        assert m is memory and player==0x90001000
        return {'request_machine':0x90002000}
    monkeypatch.setattr(movement_gate,'observed',observed)
    policy=WritePolicy(memory,guard,lambda m:snap)
    if authorized:
        assert policy('stunts',0x80002800,4)[-2:]==(0x90002000,0x80002800)
    else:
        with pytest.raises(MemoryUnavailable):policy('stunts',0x80002800,4)
    with pytest.raises(MemoryUnavailable):policy('stunts',0x80002804,4)
