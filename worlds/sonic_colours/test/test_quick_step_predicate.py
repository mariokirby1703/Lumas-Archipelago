from ..tools.private_assets import reference_root
from collections import Counter
import pytest
from ..client import quick_step as q

@pytest.mark.parametrize('owned',[0,1])
@pytest.mark.parametrize('enabled',[False,True])
def test_ownership_and_disabled_option(monkeypatch,owned,enabled):
    monkeypatch.setattr(q,'installed_data',lambda m:0x80002a00)
    writes=[]
    class Memory:
        def read_u32(self,a):return 0
        def write_u32(self,a,v,**kw):writes.append((a,v,kw))
    result=q.configure(Memory(),None,{'counts':Counter({q.ITEM:owned})},enabled)
    allowed=not enabled or bool(owned)
    assert result['allowed']==allowed
    assert writes==([(0x80002a00,1,{'expected':0,'operation':'quick_step'})] if allowed else [])

def test_gate_precedes_flags_and_forced_entry():
    from pathlib import Path
    from ..tools.ppc import Executable
    from ..client.drill_turbo import payload
    from ..client.native_hook_table import hook_rows
    assert q.payload()==payload()
    e=Executable(reference_root()/'Sonic_Colours_PAL_Static_RE_v2/sonic_pal_disassembly.elf')
    assert int.from_bytes(e.read(q.HOOK,4),'big')==q.ORIGINAL
    assert list(e.disassemble(q.HOOK-4,4))[0].op_str=='0x8020d554'
    assert int.from_bytes(e.read(q.HOOK+4,4),'big')==0x41820038
    assert q.HOOK<0x80091c84<0x80091c90
    assert hook_rows().count((0xC2091C60,4))==1


def test_quick_step_write_capability_is_enabled():
    from ..client.versions import VERSION
    assert VERSION['capabilities']['quick_step'] is True


def test_unbound_verified_actor_can_receive_quick_step(monkeypatch):
    from types import SimpleNamespace
    from ..client.state import WritePolicy
    from ..client import movement_gate
    from ..client.memory import MemoryUnavailable
    monkeypatch.setattr(q,'installed_data',lambda m:0x80002a00)
    monkeypatch.setattr(movement_gate,'observed',lambda m,p:{'request_machine':0x80b50080})
    snapshot=SimpleNamespace(scene='gameplay',death_state='alive',scene_verified=True,
        stable_polls=1,progress_verified=True,evidence={'native_data':{'stage_objects':[{'player':{'actor':0x90b50000}}]}})
    class Guard:
        def can_record_pickups(self,s):return False
        def check(self,s):raise AssertionError('persistent save binding is not required for actor permission')
    memory=SimpleNamespace(verify_revision=lambda:None)
    policy=WritePolicy(memory,Guard(),lambda m:snapshot)
    assert policy('quick_step',0x80002a00,4)[1:]==(0x80b50080,0x80002a00)
    with pytest.raises(MemoryUnavailable):policy('quick_step',0x80002a04,4)
    snapshot.progress_verified=False
    with pytest.raises(MemoryUnavailable):policy('quick_step',0x80002a00,4)
