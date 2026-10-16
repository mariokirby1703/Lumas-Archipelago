import pytest
from ..client.music_popup import MusicPopup


def event(sequence=1,cue='bgm_wmap'):
    return {'music_sequence':sequence,'cue_name':cue}


@pytest.mark.parametrize('elapsed,alpha',[(0,255),(1,255),(5,255),(7.5,128),(10,0),(11,0)])
def test_visible_and_smooth_fade_periods(elapsed,alpha):
    p=MusicPopup({});p.observe(event(),100)
    assert p.display(100+elapsed)['alpha']==alpha


def test_same_cue_loop_is_ignored_but_scene_restart_is_shown():
    p=MusicPopup({});assert p.observe(event(),0)
    assert not p.observe(event(),6)
    assert p.display(6)['alpha']<255
    assert not p.observe(event(2),7)
    assert p.observe(event(3),8,restart_key='restarted act')
    assert p.display(8)['alpha']==255


@pytest.mark.parametrize('when',[1,7])
def test_new_song_replaces_without_queue_and_resets_alpha(when):
    p=MusicPopup({});p.observe(event(),0);p.observe(event(2,'bgm_sys_title'),when)
    assert p.display(when)['title']=='bgm sys title' and p.display(when)['alpha']==255


def test_mapping_and_editable_names_are_separate_from_native_detection():
    p=MusicPopup({'bgm_pha_lsr':{'title':'Laser Song'}})
    p.observe(event(),0,{'bgm_wmap':'bgm_pha_lsr'})
    assert p.display(0)['title']=='Laser Song'
    assert p.display(0)['cue']=='bgm_wmap'
    p.observe(event(2,'bgm_unknown'),1)
    assert p.display(1)['title']=='bgm unknown'


def test_no_event_or_sfx_cannot_invent_a_song_and_unavailable_hud_does_not_pause_time():
    p=MusicPopup({});assert not p.observe(event(0),0)
    assert not p.observe(event(1,'se_jump'),0)
    p.observe(event(2),1)
    # No renderer calls during a stage load; monotonic expiry still applies.
    assert p.display(12)['alpha']==0
    assert not p.observe(event(2),13)
    assert not p.observe(event(3,'bgm_jingle_drown'),14)


def test_first_visible_period_starts_at_guest_ack_and_text_survives_zero_alpha():
    p=MusicPopup({});p.observe(event(),0,defer_start=True)
    assert p.display(20)['alpha']==255
    p.published(p.generation,20)
    assert p.display(25)['alpha']==255
    assert p.display(27.5)['alpha']==128
    assert p.display(30)['alpha']==0
    assert p.display(30)['title']=='bgm wmap'


def test_result_music_is_supported_without_enabling_death_jingles():
    p=MusicPopup({})
    assert p.observe(event(1,'bgm_jingle_stg_clear'),0)
    assert p.display(0)['title']=='bgm jingle stg clear'
    assert not p.observe(event(2,'bgm_jingle_drown'),1)


def test_music_mapping_is_cached_per_seed_and_mode(monkeypatch):
    from ..client import music_bank,music_popup
    music_popup._seed_mapping.cache_clear()
    calls=[]
    original=music_bank.plan
    def traced(seed,mode):
        calls.append((seed,mode))
        return original(seed,mode)
    monkeypatch.setattr(music_bank,'plan',traced)
    assert music_popup._seed_mapping('cached-seed',True)==music_popup._seed_mapping('cached-seed',True)
    assert calls==[('cached-seed','anywhere')]
    music_popup._seed_mapping('cached-seed',False)
    assert calls[-1]==('cached-seed','off') and len(calls)==2
    music_popup._seed_mapping.cache_clear()
