import struct
import pytest
from ..client import oxygen_native as o,native_events as n
from ..client.native_dol import branch
from ..client.versions import VERSION
from .test_native_events import Machine


def fixture(monkeypatch,seconds=5):
    m=Machine('frame');m.control=0x80002f00;m.plugin=0x900b0000;m.start=0x80002000
    code,m.reset=o.payload(m.start,m.control)
    m.b.put(m.start,code)
    for name,hook,original,target in [('oxygen_update',o.UPDATE,o.ORIGINAL_UPDATE,m.start),('oxygen_reset',o.RESET,o.ORIGINAL_RESET,m.reset)]:
        monkeypatch.setitem(n.HOOKS,name,(hook,original));m.put(hook,branch(hook,target))
    m.b.put(m.control,bytes(o.SIZE));m.put(m.control,o.MAGIC);m.put(m.control+4,1)
    m.put(m.plugin,0x807710fc);m.put(m.plugin+8,0x8071f010)
    m.put(VERSION['manager_global_candidate'],0x900c0000);m.put(0x900c0030,0x900d0000)
    m.put(m.control+8,0x900d0000);m.put(m.control+12,0)
    m.b.put(m.control+16,struct.pack('>f',30.05 if seconds==0 else 30-seconds))
    return m


def run(m,reset=False):
    m.kind='oxygen_reset' if reset else 'oxygen_update'
    m.r[29]=m.plugin;m.r[30]=m.machine;m.r[3]=m.plugin;m.r[4]=m.machine
    m.f[0]=0.;before=m.r[:];floats=m.f[:];cr=m.cr
    m.run()
    assert m.r==before and m.cr==cr
    assert m.f[0]==floats[0] and m.f[2:]==floats[2:]
    if reset:assert m.f==floats
    return struct.unpack('>f',m.read(m.plugin+0x20,4))[0]


@pytest.mark.parametrize('seconds',[0,5,10,20,30,40,60])
def test_entry_bubble_reset_and_running_clock_without_host_poll(monkeypatch,seconds):
    m=fixture(monkeypatch,seconds);floor=30.05 if seconds==0 else 30-seconds
    m.b.put(m.plugin+0x20,struct.pack('>f',0.016))
    assert run(m)==pytest.approx(floor+.016,abs=.00001)
    # The original game advances dt after our displaced load; we never refill
    # the running clock on subsequent native updates.
    m.b.put(m.plugin+0x20,struct.pack('>f',floor+1.5))
    assert run(m)==pytest.approx(floor+1.5,abs=.00001)
    assert run(m,reset=True)==pytest.approx(floor,abs=.00001)
    assert run(m)==pytest.approx(floor,abs=.00001)


def test_receiving_level_preserves_elapsed_time_and_owner_replacement_restarts(monkeypatch):
    m=fixture(monkeypatch);run(m,reset=True)
    m.b.put(m.plugin+0x20,struct.pack('>f',27.));m.b.put(m.control+16,struct.pack('>f',20.))
    assert run(m)==22. # two seconds used out of the new ten-second supply
    m.put(m.player+12,456);m.b.put(m.plugin+0x20,struct.pack('>f',0.))
    assert run(m)==20.


@pytest.mark.parametrize('failure',['disabled','save','slot','plugin','machine','reverse'])
def test_unowned_or_changed_context_executes_vanilla_reset(monkeypatch,failure):
    m=fixture(monkeypatch)
    if failure=='disabled':m.put(m.control+4,0)
    if failure=='save':m.put(0x900c0030,0x900d1000)
    if failure=='slot':m.b.put(0x900d0000,b'\x01')
    if failure=='plugin':m.put(m.plugin,0x80771000)
    if failure=='machine':m.put(m.machine,0x8075a000)
    if failure=='reverse':m.put(0x90070008,m.machine+4)
    m.b.put(m.plugin+0x20,struct.pack('>f',12.))
    assert run(m)==12.
    assert run(m,reset=True)==0.


def test_host_publication_is_authenticated_bounded_and_not_repeated(tmp_path,monkeypatch):
    from .test_dead_weight import setup
    from ..client.memory import MemoryUnavailable
    runtime,m,b,_=setup(tmp_path,monkeypatch);base=0x80002d00
    monkeypatch.setattr(o,'address',lambda memory:base)
    monkeypatch.setattr(m,'resolve_selected_slot',lambda **kw:(0x90050000,0x90060000,0,0x90060008))
    b.put(base,struct.pack('>I',o.MAGIC)+bytes(o.SIZE-4))
    try:
        owned={'counts':{'Progressive Breathing':1}}
        o.configure(m,runtime.snapshot,runtime.guard,owned)
        assert m.read_u32(base+4)==1 and m.read_f32(base+16)==25.
        writes=len(b.writes)
        o.configure(m,runtime.snapshot,runtime.guard,owned)
        assert len(b.writes)==writes
        # Arbitrary elapsed clocks or unrelated words cannot be published under
        # the policy operation, even inside an otherwise valid transaction.
        m._oxygen_transaction=(base,o.context(m,runtime.snapshot,runtime.guard),{16:struct.pack('>f',25.)})
        with pytest.raises(MemoryUnavailable,match='outside transaction'):
            m.write_bytes_verified(base+16,struct.pack('>f',999.),expected=struct.pack('>f',25.),operation='oxygen_controls')
        m._oxygen_transaction=None
        from dataclasses import replace
        runtime.snapshot=replace(runtime.snapshot,save_identity='another-save')
        result=o.configure(m,runtime.snapshot,runtime.guard,owned)
        assert m.read_u32(base+4)==0 and 'disabled' in result['status']
    finally:runtime.journal.close()
