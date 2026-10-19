"""Player-scoped music survives generation, patch download and HUD lookup."""
from argparse import Namespace
import hashlib
import json
from types import SimpleNamespace

import pytest
from BaseClasses import MultiWorld,CollectionState
from Fill import distribute_items_restrictive
from test.general import gen_steps
from worlds.AutoWorld import call_all
from ..world import SonicColoursWorld
from ..patch import SonicColoursPatch,load_patch
from ..client import music_bank as music,music_popup
from ..client.runtime import validate_slot


def multiplayer(seed):
    multi=MultiWorld(3);multi.set_seed(seed);multi.seed_name=f'MusicPlayers{seed}'
    for player in multi.player_ids:multi.game[player]=SonicColoursWorld.game
    multi.player_name={p:f'Sonic{p}' for p in multi.player_ids}
    args=Namespace()
    for name,cls in SonicColoursWorld.options_dataclass.type_hints.items():
        setattr(args,name,{p:cls.from_any(1 if name=='music_randomization' else cls.default) for p in multi.player_ids})
    multi.set_options(args);multi.state=CollectionState(multi)
    for step in gen_steps:call_all(multi,step)
    distribute_items_restrictive(multi)
    assert multi.can_beat_game()
    return multi


def test_multiplayer_music_is_distinct_stable_and_preserved_in_player_patch(tmp_path):
    multi=multiplayer(1810);mappings=[];seeds=[]
    for player,world in multi.worlds.items():
        slot=world.fill_slot_data();validate_slot(slot)
        assert world.fill_slot_data()['music_seed']==slot['music_seed']
        mapping=music.slot_plan(slot);mappings.append(mapping);seeds.append(slot['music_seed'])
        path=tmp_path/f'{player}.apsoniccolours'
        SonicColoursPatch(str(path),player,multi.player_name[player],slot_data=slot).write()
        assert music.slot_plan(load_patch(path).slot_data)==mapping
        runtime=SimpleNamespace(slot_data=slot,clock=lambda:100.,native_event_status={
            'music_sequence':2,'cue_name':'bgm_stg110_rso'})
        # Use an actual catalog cue instead of relying on a particular name.
        cue=next(n for n in music.SHUFFLE_CUES if not n.startswith('bgm_jingle_'))
        runtime.native_event_status['cue_name']=cue
        music_popup.update(runtime)
        assert runtime.music_popup.heard==mapping[cue]
    assert len(set(seeds))==3
    assert len({json.dumps(m,sort_keys=True) for m in mappings})==3
    repeat=multiplayer(1810)
    assert [w.fill_slot_data()['music_seed'] for w in repeat.worlds.values()]==seeds
    # Missing player seed is the exact historical shared-seed mapping.
    legacy={k:v for k,v in slot.items() if k!='music_seed'}
    assert music.slot_plan(legacy)==music.plan(slot['seed_name'],'anywhere',2)


@pytest.mark.parametrize('invalid',[None,True,0,'','a'*63,'G'*64])
def test_invalid_music_identity_rejected(invalid):
    from . import generate
    slot=generate().worlds[1].fill_slot_data()
    with pytest.raises(ValueError,match='player music seed'):validate_slot({**slot,'music_seed':invalid})


def test_randomization_off_is_unchanged_across_player_seeds():
    for player in range(1,5):
        slot={'seed_name':'same seed','music_seed':hashlib.sha256(str(player).encode()).hexdigest(),
              'music_mapping_version':2,'options':{'music_randomization':0}}
        assert all(name==donor for name,donor in music.slot_plan(slot).items())
