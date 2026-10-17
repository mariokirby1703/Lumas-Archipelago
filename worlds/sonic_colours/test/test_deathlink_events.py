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


def test_four_rapid_deaths_do_not_require_three_living_samples_between_them():
    d=setup()
    poll(d,0)
    for sequence in (2,4,6,8):  # native seqlock advances twice per death
        assert poll(d,sequence,sequence,native_state='dying')
        assert not poll(d,sequence+.01,sequence,native_state='dying')
        assert not poll(d,sequence+.02,sequence)  # only one alive observation


def test_new_native_death_is_not_lost_when_respawn_was_not_sampled():
    d=setup();poll(d,0)
    assert poll(d,1,2,native_state='dying')
    assert poll(d,2,4,native_state='dying')
    assert not poll(d,3,4,native_state='dying')


def test_dying_scene_and_later_native_callback_send_only_once():
    d=setup()
    for i in range(3):poll(d,i)
    assert not poll(d,3,0,native_state='dying')
    assert poll(d,4,2,native_state='dying')
    assert not poll(d,5,2,native_state='dying')


def test_unsafe_native_event_does_not_send_or_replay_on_return():
    d=setup();poll(d,0)
    assert not poll(d,1,2,safe=False,native_state='dying')
    assert not poll(d,2,2)


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
