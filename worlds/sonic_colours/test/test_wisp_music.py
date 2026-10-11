"""Actual PAL transformation graph/loop evidence and resident-bank regression.

These tests do not claim audible Dolphin playback or native transition timing.
"""
import json
from pathlib import Path
import struct
import pytest
from ..client import music_bank as mb, live_music
from ..client.memory import SonicMemory, MemoryUnavailable
from .test_memory import FakeBackend
from .test_native_assets import SOURCE
from .test_music_bank import bank

WISPS = ('bgm_pha_spn', 'bgm_pha_spn_wtr', 'bgm_pha_spk', 'bgm_pha_ast',
         'bgm_pha_rod', 'bgm_pha_lsr', 'bgm_pha_rkt', 'bgm_pha_pzl',
         'bgm_pha_multi_common', 'bgm_pha_multi_united')
DESTINATIONS = ('bgm_stg120_rso', 'bgm_stg530_qua', 'bgm_zmap_rso',
                'bgm_mlt_a', 'bgm_boss_Jellyboss', 'bgm_sys_title')


def test_every_original_transformation_is_in_the_global_source_destination_pool():
    assert set(WISPS) == mb.WISP_CUES
    assert not mb.WISP_CUES & mb.PROTECTED
    assert 'bgm_jingle_super_sonic' in mb.PROTECTED
    for seed in range(100):
        mapping = mb.plan(str(seed), 'anywhere')
        assert set(mapping.values()) == set(mapping)
        assert all(mapping[n] != n for n in WISPS)
        assert any(mapping[n] not in mb.WISP_CUES for n in WISPS)
        assert any(n not in mb.WISP_CUES and d in mb.WISP_CUES for n, d in mapping.items())


@pytest.mark.skipif(not SOURCE.exists(), reason='original PAL CPK absent')
def test_original_pal_metadata_is_reproducible_and_not_guessed_from_names():
    from ..tools.analyze_wisp_music import analyze
    root = Path(__file__).parents[1]
    elf = root / 'notes/Sonic_Colours_PAL_Static_RE_v2/sonic_pal_disassembly.elf'
    if not elf.exists(): pytest.skip('original PAL ELF absent')
    assert analyze(root) == json.loads((root / 'data/bgm_transformations.json').read_text())
    assert mb.TRANSFORMATIONS['cues']['bgm_pha_pzl']['transformation'] == 'Blue Cube'
    assert mb.TRANSFORMATIONS['cues']['bgm_pha_ast']['transformation'] == 'Green Hover'
    assert mb.TRANSFORMATIONS['cues']['bgm_pha_spn_wtr']['selection'].endswith('actor+DD nonzero')
    assert mb.TRANSFORMATIONS['cues']['bgm_pha_multi_united']['selection'].endswith('variant 1')
    assert mb.TRANSFORMATIONS['cues']['bgm_pha_rkt']['aax_loop_segments'] == [0]


@pytest.mark.skipif(not SOURCE.exists(), reason='original PAL CPK absent')
@pytest.mark.parametrize('wisp', WISPS)
@pytest.mark.parametrize('destination', DESTINATIONS)
def test_bidirectional_wisp_cross_category_audio_preserves_every_control(wisp, destination):
    original = bank()
    mapping = mb.plan('wisp-pair', 'off')
    mapping[wisp], mapping[destination] = destination, wisp
    patched = mb.rewrite_bank(original, mapping)
    assert live_music.recover_original(patched) == original
    mb.validate_resource_bank(patched, mapping)
    allowed = set()
    for target, donor in ((wisp, destination), (destination, wisp)):
        leaves = mb.GRAPHS['graphs'][target]; audio = mb.GRAPHS['graphs'][donor]
        for k, leaf in enumerate(leaves):
            assert struct.unpack_from('>I', patched, leaf['cell'])[0] == audio[min(k, len(audio)-1)]['original_ref']
            allowed.update(range(leaf['cell'], leaf['cell']+4))
    # Includes CUE flags, Wisp gain, ISAAC filters, SOUND_ELEMENT format,
    # sample counts, native cue identities and destination boost/sleep graphs.
    assert all(a == b or i in allowed for i, (a, b) in enumerate(zip(original, patched)))
    assert mb.rewrite_bank(live_music.recover_original(patched), mb.plan('off', 'off')) == original


@pytest.mark.skipif(not SOURCE.exists(), reason='original PAL CPK absent')
def test_resident_writer_wisp_force_reload_off_and_integrity_guards():
    backend = FakeBackend(); base = live_music.CANDIDATE_HINTS[0]
    original = bank(); backend.put(base, original)
    writes = []
    def guard(operation, address, size):
        assert (operation, address, size) == ('music_bank', base, len(original))
        assert memory._music_bank_transaction[0] == base
        writes.append((operation, address, size)); return True
    memory = SonicMemory(backend, guard)
    slot = {'seed_name': 'resident-wisp', 'options': {'music_randomization': True}}
    pair = ('bgm_stg120_rso', 'bgm_pha_pzl')
    result = live_music.apply(memory, slot, pair)
    assert result['audible_verified'] is False and set(result['transformation_cues']) == set(WISPS)
    leaf = mb.GRAPHS['graphs'][pair[0]][0]; donor = mb.GRAPHS['graphs'][pair[1]][0]
    assert memory.read_u32(base+leaf['cell']) == donor['original_ref']
    assert live_music.recover_original(memory.read_bytes(base, len(original))) == original
    live_music.apply(memory, {**slot, 'options': {'music_randomization': False}})
    assert memory.read_bytes(base, len(original)) == original
    assert len(backend.writes) == 2
    checked = len(writes)
    with pytest.raises(MemoryUnavailable):
        live_music.apply(memory, slot, ('bgm_pha_lsr', 'bgm_jingle_super_sonic'))
    damaged = bytearray(original); damaged[-1] ^= 1; backend.put(base, damaged)
    with pytest.raises(MemoryUnavailable): live_music.apply(memory, slot, pair)
    assert len(backend.writes) == 2 and len(writes) == checked
