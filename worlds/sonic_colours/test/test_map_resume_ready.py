from dataclasses import replace
from types import SimpleNamespace
import pytest
from ..client.state import Snapshot,SaveGuard
from ..client.memory import MemoryUnavailable


def setup(scene='global_map'):
    journal=SimpleNamespace(data={'save_identity':'bound-save','native_monotonic_clears':[]},save=lambda:None)
    guard=SaveGuard(journal)
    snapshot=Snapshot('session','bound-save',1,scene,None,stable_polls=1,
                      save_identity_verified=True,scene_verified=True,progress_verified=True)
    return guard,snapshot


@pytest.mark.parametrize('scene',['global_map','world_map','game_land_select'])
def test_verified_bound_map_resumes_on_first_poll(scene):
    guard,snapshot=setup(scene);guard.observe(snapshot)
    assert guard.armed and guard.reason=='bound seed/save resumed'
    guard.check(snapshot)


@pytest.mark.parametrize('change',[{'save_identity':'different-save'},
    {'save_identity_verified':False},{'scene_verified':False},{'stable_polls':0}])
def test_first_poll_shortcut_does_not_bypass_identity_or_scene_proof(change):
    guard,snapshot=setup();snapshot=replace(snapshot,**change)
    guard.observe(snapshot)
    with pytest.raises(MemoryUnavailable):guard.check(snapshot)


def test_story_and_new_seed_keep_existing_proof_requirements():
    guard,snapshot=setup('gameplay');guard.observe(snapshot)
    assert not guard.armed
    guard.journal.data['save_identity']=None
    assert guard.required_polls(replace(snapshot,scene='global_map'))==3
