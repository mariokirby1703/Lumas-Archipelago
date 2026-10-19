"""Normal generated-seed integration, donor pool and old seed stability."""
import hashlib,json
from collections import Counter
import pytest
from . import generate
from ..client import music_bank as mb
from ..client.runtime import validate_slot
from ..client.music_popup import _seed_mapping
from .test_music_bank import bank
from .test_native_assets import SOURCE

@pytest.mark.parametrize('seed',range(100))
def test_new_pool_includes_both_replay_songs_and_protects_original_cues(seed):
    mapping=mb.plan(str(seed),'anywhere',2)
    assert mapping==mb.plan(str(seed),'anywhere',2)
    assert all(mapping[n]==n for n in mb.FINITE_CUES)
    selected=Counter(mapping[n] for n in mb.SHUFFLE_CUES)
    assert all(selected[n]==1 for n in mb.REPLAY_DONORS)
    assert max(selected.values())==1
    assert set(selected)<=mb.SHUFFLE_CUES|mb.REPLAY_DONORS
    assert all(mb.AUDIO['cues'][n]!=mb.AUDIO['cues'][mapping[n]] for n in mb.SHUFFLE_CUES)

@pytest.mark.parametrize('seed,digest',[
 ('legacy-music-v1','124a389a7c737a72de9be54f284356af869ebed6a6fb9a76cddaace34ff1c0f9'),
 ('09572034733709851556','cbfa8da6124960c7c8062fba7dbbff748e80e3250e372a68ac7ee2fea2fd06ee'),
 ('SonicTest20261016','afa9704b950a1de45b4a3d36312bd0fd200543e24c8616f11b723503b1c4dda7')])
def test_legacy_mapping_unchanged(seed,digest):
    assert hashlib.sha256(json.dumps(mb.plan(seed,'anywhere'),sort_keys=True).encode()).hexdigest()==digest
    slot={'seed_name':seed,'options':{'music_randomization':1}}
    assert mb.slot_plan(slot)==mb.plan(seed,'anywhere',1)

@pytest.mark.parametrize('enabled',[False,True])
def test_generated_slot_client_and_popup_use_same_version(enabled):
    multi=generate({'music_randomization':enabled},20261017,fill=True)
    assert multi.can_beat_game()
    slot=multi.worlds[1].fill_slot_data();validate_slot(slot)
    assert slot['music_mapping_version']==2
    mapping=mb.slot_plan(slot)
    assert mapping==_seed_mapping(slot['music_seed'],enabled,2)
    if not enabled:assert all(n==d for n,d in mapping.items())
    with pytest.raises(ValueError,match='music mapping version'):
        validate_slot({**slot,'music_mapping_version':3})

@pytest.mark.skipif(not SOURCE.exists(),reason='private original CPK absent')
def test_normal_v2_resource_roundtrip_and_cutscene_protection():
    original=bank();mapping=mb.plan('normal-pool-v2','anywhere',2)
    changed=mb.rewrite_bank(original,mapping,mapping_version=2)
    mb.validate_resource_bank(changed,mapping,2)
    assert mb.recover_bank(changed)==original
    for name in mb.FINITE_CUES:
        for leaf in mb.GRAPHS['graphs'][name]:
            i=leaf['cell'];assert changed[i:i+4]==original[i:i+4]
    with pytest.raises(ValueError):mb.rewrite_bank(original,mapping)


@pytest.mark.skipif(not SOURCE.exists(),reason='private original CPK absent')
def test_normal_resident_publication_and_popup_share_finite_donors():
    from types import SimpleNamespace
    from ..client import live_music,music_popup
    from ..client.memory import SonicMemory
    from .test_memory import FakeBackend
    original=bank();backend=FakeBackend();base=live_music.CANDIDATE_HINTS[0]
    backend.put(base,original)
    memory=SonicMemory(backend,lambda op,a,n: ('verified',op,a,n))
    slot={'seed_name':'normal-resident-v2','music_mapping_version':2,'options':{'music_randomization':1}}
    result=live_music.apply(memory,slot)
    mapping=mb.slot_plan(slot)
    mb.validate_resource_bank(memory.read_bytes(base,len(original)),mapping,2)
    assert result['pool_size']==80 and len(result['finite_audio_destinations'])==2
    for sequence,donor in enumerate(sorted(mb.REPLAY_DONORS),1):
        cue=next(n for n in mb.SHUFFLE_CUES if mapping[n]==donor)
        runtime=SimpleNamespace(slot_data=slot,native_event_status={'music_sequence':sequence,'cue_name':cue},clock=lambda:100.)
        music_popup.update(runtime)
        assert runtime.music_popup.heard==donor

    restored=live_music.apply(memory,{**slot,'options':{'music_randomization':0}})
    assert memory.read_bytes(base,len(original))==original
    assert restored['duration_validation'].startswith('vanilla bank restored')
