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


def test_verified_death_after_pause_waits_for_scene_and_sends_once():
    d=setup();poll(d,0,native_context='game')
    assert not poll(d,1,safe=False,native_state='paused',native_context='game')
    assert not poll(d,2,2,safe=False,native_state='dying',native_trusted=True,native_context='game')
    assert d.pending_local_death
    assert poll(d,3,2,native_context='game')
    assert not poll(d,4,2,native_context='game')


def test_zero_ring_enemy_death_does_not_require_dying_or_respawn_samples():
    d=setup();poll(d,0,native_context='game')
    for seq in (2,4,6):
        assert not poll(d,seq,seq,safe=False,native_state='unknown',native_trusted=True,native_context='game')
        assert poll(d,seq+.01,seq,native_context='game')
        assert not poll(d,seq+.02,seq,native_context='game')


def test_deferred_event_cannot_cross_emulation_sessions():
    d=setup();poll(d,0,native_context='old')
    assert not poll(d,1,2,safe=False,native_trusted=True,native_context='old')
    assert not poll(d,2,0,native_context='new')
    assert not d.pending_local_death


def test_remote_death_during_unsafe_transition_is_never_queued_as_local():
    d=setup();poll(d,0);d.receive({'time':1,'source':'peer'},1)
    assert not poll(d,1)
    assert not poll(d,2,2,safe=False,native_trusted=True)
    assert not d.pending_local_death
    assert not poll(d,3,2)


def test_enemy_death_uses_attributed_native_stage_without_pickup_fields():
    from ..client.deathlink import native_death_trusted
    snap=SimpleNamespace(session='game',scene='dying',scene_verified=True,
        evidence={'native_data':{'stage_objects':[{'stage':0x90010000}]}})
    runtime=SimpleNamespace(snapshot=snap,guard=SimpleNamespace(can_record=lambda s:True))
    assert native_death_trusted(runtime,{'death_stage':0x90010000})
    assert not native_death_trusted(runtime,{'death_stage':0x90020000})
    runtime.guard.can_record=lambda s:False
    assert not native_death_trusted(runtime,{'death_stage':0x90010000})


def test_paused_context_can_retain_only_previously_verified_stage_in_same_session():
    from ..client.deathlink import native_death_trusted
    snap=SimpleNamespace(session='game',scene='paused',scene_verified=False,evidence={})
    runtime=SimpleNamespace(snapshot=snap,_death_stage_session='game',
        _death_allowed_stages={0x90010000},guard=SimpleNamespace(can_record=lambda s:False))
    assert native_death_trusted(runtime,{'death_stage':0x90010000})
    runtime._death_stage_session='previous-game'
    assert not native_death_trusted(runtime,{'death_stage':0x90010000})


def test_fast_abyss_death_survives_unclassified_transition_and_immediate_respawn():
    d=setup();poll(d,0,native_context='game',native_step=2)
    assert not poll(d,1,2,safe=False,native_state='unknown',native_trusted=True,
                    native_context='game',native_step=2)
    assert poll(d,2,2,native_state='alive',native_context='game',native_step=2)
    assert not poll(d,3,2,native_context='game',native_step=2)


def test_two_fast_abyss_deaths_between_host_polls_each_send_once():
    d=setup();poll(d,0,native_context='game',native_step=2)
    assert not poll(d,1,4,safe=False,native_state='unknown',native_trusted=True,
                    native_context='game',native_step=2)
    assert d.pending_local_death==2
    assert poll(d,2,4,native_context='game',native_step=2)
    assert poll(d,3,4,native_context='game',native_step=2)
    assert not poll(d,4,4,native_context='game',native_step=2)
