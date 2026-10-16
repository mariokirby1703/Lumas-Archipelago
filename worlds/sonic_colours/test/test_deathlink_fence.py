from types import SimpleNamespace
from ..client import native_events as n,event_controls as c
from ..client.deathlink import DeathLink
from .test_native_events import Machine


def test_native_frame_fence_advances_even_when_kills_disabled():
    m=Machine('frame');m.put(m.control+n.ENABLE,0);m.put(m.control+n.REQUEST,1)
    assert m.get(m.control+n.FRAME_FENCE)==0
    m.run()
    assert m.get(m.control+n.FRAME_FENCE)==1 and not m.calls
    m.run()
    assert m.get(m.control+n.FRAME_FENCE)==2 and not m.calls


def test_cancellation_requires_unconsumed_request_and_completed_guest_frame(monkeypatch):
    m=Machine('frame');base=m.control
    memory=SimpleNamespace(read_u32=m.get,read_bytes=m.read)
    monkeypatch.setattr(n,'address',lambda _:base)
    def write(memory,snapshot,guard,fields,**kw):
        for offset,raw in fields.items():m.b.put(base+offset,raw)
    monkeypatch.setattr(c,'write',write)
    snap=SimpleNamespace(session='session')
    m.put(base+n.REQUEST,7)
    assert not c.cancel_kill(memory,snap,None,7)
    assert not c.cancel_kill(memory,snap,None,7)  # host reads prove nothing
    m.run()
    assert c.cancel_kill(memory,snap,None,7)
    assert not m.calls
    m.put(base+n.ACK,7);m.run()
    assert not c.cancel_kill(memory,snap,None,7)  # already consumed


def test_verified_cancel_recovers_across_host_restart_without_echo():
    journal=SimpleNamespace(data={'remote_deaths':[],'remote_cycle':False},save=lambda:None)
    link=DeathLink(journal)
    for i in range(3):link.poll(safe=True,native_state='alive',now=i,kill=lambda:7)
    link.receive({'time':1,'source':'peer'},3)
    link.poll(safe=True,native_state='alive',now=3,kill=lambda:7)
    link=DeathLink(journal)
    assert link.remote_request==7
    for i in range(3):
        assert not link.poll(safe=True,native_state='alive',now=4+i,kill=lambda:7,cancel=lambda:True)
    assert not link.remote_cycle
    assert link.poll(safe=True,native_state='dying',now=10,kill=lambda:7)
