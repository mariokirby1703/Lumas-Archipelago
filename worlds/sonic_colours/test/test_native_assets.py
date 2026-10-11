from pathlib import Path

import pytest

from ..client.asset_patch import replace_music, NAME, BGM
from ..client.audio import canonical_act_cues
from ..client.cpk import CPK, UTF
from ..client.runtime import validate_slot
from ..world_constants import NORMAL
from . import generate


SOURCE = Path(__file__).parents[1] / 'notes/memdumps_and_more/sonic2010_0.cpk'


@pytest.mark.skipif(not SOURCE.exists(), reason='private original PAL CPK not installed')
def test_original_archive_canonical_cues_and_byte_restoration():
    archive = CPK(SOURCE)
    script = archive.read(next(row for row in archive.toc.rows if row['FileName'] == 'actstgmission.lua'))
    bank = UTF(archive.read(next(row for row in archive.toc.rows if row['FileName'] == 'bgm.strm.csb')))
    offset, size = next(row['utf'] for row in bank.rows if row['name'] == 'CUE')
    cues = UTF(bank.data[bank.binary + offset:bank.binary + offset + size])
    available = {row['name'] for row in cues.rows}
    mapping = canonical_act_cues(available)
    patched = replace_music(script, mapping)
    entries = list(NAME.finditer(patched))
    for index, entry in enumerate(entries):
        mission = entry[1].decode('ascii')
        if mission in mapping:
            end = entries[index + 1].start() if index + 1 < len(entries) else len(patched)
            assert BGM.search(patched, entry.end(), end)[1].decode('ascii') == mapping[mission]
    # Replace the redirects with the original names: EVERY original byte,
    # including all spawn, path, camera, event, score and result data, matches.
    original_mapping = {stage['mission_id']: stage['bgm'] for stage in NORMAL}
    restored = patched
    for entry in reversed(entries):
        mission = entry[1].decode('ascii')
        if mission not in mapping:
            continue
        end = next((other.start() for other in entries if other.start() > entry.start()), len(patched))
        match = BGM.search(patched, entry.end(), end)
        restored = restored[:match.start(1)] + original_mapping[mission].encode('ascii') + restored[match.end(1):]
    assert restored == script
    with pytest.raises(ValueError, match='original mission/BGM layout mismatch'):
        replace_music(script.replace(b'bgm_stg110_rso', b'bgm_corrupted'), mapping)


@pytest.mark.parametrize('rank', ['off', 's', 'a', 'b', 'c', 'all'])
@pytest.mark.parametrize('music', [False, True])
def test_rank_music_option_fill_matrix(rank, music):
    for seed in range(100):
        world = generate({'rank_checks': rank, 'music_randomization': music},
                         seed, fill=True)
        validate_slot(world.worlds[1].fill_slot_data())
        assert world.can_beat_game() and not world.get_unfilled_locations()
