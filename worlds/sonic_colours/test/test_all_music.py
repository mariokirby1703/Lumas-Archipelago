"""All 87x87 PAL donor/destination pairs, without category restrictions.

Original data and native control-byte verification are offline; audible
playback, finite-track repetition and callback timing require Dolphin.
"""
import struct
import json
from pathlib import Path
import pytest
from ..client import music_bank as mb, live_music
from .test_native_assets import SOURCE
from .test_music_bank import bank


@pytest.mark.skipif(not SOURCE.exists(), reason='original PAL CPK absent')
def test_all_playback_evidence_matches_original_audio_resources():
    from ..tools.analyze_music_playback import analyze
    root = Path(__file__).parents[1]
    assert analyze(root) == json.loads((root / 'data/bgm_playback.json').read_text())
    assert len(mb.PLAYBACK['cues']) == 87
    assert len(mb.FINITE_CUES) == 9
    assert 'bgm_pha_rkt' in mb.FINITE_CUES
    for name, evidence in mb.PLAYBACK['cues'].items():
        assert evidence['cue_flags'] == mb.CUES[name]['flags']
        for audio in evidence['leaf_audio']:
            descriptor = mb.PLAYBACK['audio'][audio]
            assert {k:descriptor[k] for k in ('fmt','stmflg','sfreq')} == {
                'fmt':0, 'stmflg':1, 'sfreq':48000}
            assert descriptor['nch'] in (1, 2)  # original jingle resources include mono


def test_no_category_mode_or_fixed_music_cues_remain():
    with pytest.raises(ValueError): mb.plan('all-music', 'per_world')
    for seed in range(100):
        mapping = mb.plan(str(seed), 'anywhere')
        assert mapping == mb.plan(str(seed), 'anywhere')
        assert len(mapping) == 87 and set(mapping) == set(mapping.values()) == set(mb.CUES)
        assert all(n != d for n, d in mapping.items())
        assert all(mb.AUDIO['cues'][n] != mb.AUDIO['cues'][d] for n,d in mapping.items())
        for n in mb.LEGACY_PROTECTED:
            assert mapping[n] != n  # historical read format is not a shuffle pool


@pytest.mark.skipif(not SOURCE.exists(), reason='original PAL CPK absent')
def test_every_catalog_source_can_replace_every_destination_with_exact_control_preservation():
    original = bank(); names = sorted(mb.CUES)
    cells = {p for leaves in mb.GRAPHS['graphs'].values() for leaf in leaves
             for p in range(leaf['cell'], leaf['cell']+4)}
    observed = set()
    # Each cyclic permutation is bijective. Together these cover all 7,569
    # pairs while exercising the real production rewrite and reconstruction.
    for shift in range(len(names)):
        mapping = dict(zip(names, names[shift:] + names[:shift]))
        patched = mb.rewrite_bank(original, mapping)
        assert live_music.recover_original(patched) == original
        assert all(a == b or i in cells for i,(a,b) in enumerate(zip(original,patched)))
        for destination, donor in mapping.items():
            source = mb.GRAPHS['graphs'][donor]
            for k, leaf in enumerate(mb.GRAPHS['graphs'][destination]):
                assert struct.unpack_from('>I', patched, leaf['cell'])[0] == source[min(k,len(source)-1)]['original_ref']
            observed.add((destination, donor))
    assert observed == {(n,d) for n in names for d in names}
    assert mb.rewrite_bank(live_music.recover_original(patched), mb.plan('vanilla','off')) == original


@pytest.mark.skipif(not SOURCE.exists(), reason='original PAL CPK absent')
def test_no_bypass_of_integrity_for_jingle_cutscene_and_final_boss_sources():
    original = bank(); mapping = mb.plan('all-music-integrity', 'anywhere')
    patched = mb.rewrite_bank(original,mapping)
    damaged = bytearray(patched)
    damaged[mb.GRAPHS['graphs']['bgm_jingle_drown'][0]['cell']+4] ^= 1
    with pytest.raises(ValueError): mb.recover_bank(bytes(damaged))
    bad = mapping.copy(); bad['bgm_sys_op'] = bad['bgm_sys_end']
    with pytest.raises(ValueError,match='permutation'): mb.rewrite_bank(original,bad)
