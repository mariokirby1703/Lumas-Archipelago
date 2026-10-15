from types import SimpleNamespace
from ..client.deathlink import DeathLink


def setup():
    j=SimpleNamespace(data={'remote_deaths':[],'remote_cycle':False},save=lambda:None)
    return DeathLink(j)


def poll(d,now,seq=0,**kw):
    return d.poll(safe=kw.pop('safe',True),native_state=kw.pop('native_state','alive'),now=now,
                  native_sequence=seq,kill=kw.pop('kill',lambda:7),**kw)


def test_short_native_death_survives_missed_dying_frame_and_deduplicates():
    d=setup()
    for i in range(3):assert not poll(d,i)
    assert poll(d,3,1)
    for i in range(4,8):assert not poll(d,i,1)
    assert poll(d,8,2)


def test_native_ack_cannot_end_echo_suppression_before_death_event():
    d=setup()
    for i in range(3):poll(d,i)
    assert d.receive({'source':'peer','time':1},3)
    assert not poll(d,3)
    for i in range(4,9):assert not poll(d,i,remote_ack=7)
    assert d.remote_cycle
    assert not poll(d,9,1,remote_ack=7)
    for i in range(10,13):assert not poll(d,i,1,remote_ack=7)
    assert not d.remote_cycle
    assert poll(d,13,2)


def test_remote_unsafe_event_waits_and_expires_without_kill():
    d=setup();calls=[];d.receive({'time':1},0)
    assert not poll(d,1,safe=False,kill=lambda:calls.append(1))
    assert not poll(d,2,kill_safe=False,kill=lambda:calls.append(1))
    assert not poll(d,31,kill=lambda:calls.append(1))
    assert not calls and d.pending is None


def test_duplicate_and_restart_do_not_replay_pending_event():
    d=setup();event={'source':'peer','time':1}
    assert d.receive(event,0) and not d.receive(event,1)
    restarted=DeathLink(d.journal)
    assert restarted.pending is None and not restarted.receive(event,2)
