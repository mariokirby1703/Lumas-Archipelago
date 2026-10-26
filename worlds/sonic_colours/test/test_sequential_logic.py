from copy import deepcopy
import pytest
from ..logic import check
from ..Rules import can_complete,requirements
from ..world_constants import BY_MISSION
from . import generate


def test_tropical_resort_3_and_later_acts_wait_for_stomp():
    multi=generate({'movement_unlocks':True,'world_progression':0})
    world=multi.worlds[1];state=multi.state
    for _ in range(2):state.collect(world.create_item('Progressive Crouch'),prevent_sweep=True)
    clear=world.get_location('Tropical Resort Act 3 - Clear')
    act4=next(stage for stage in BY_MISSION.values() if stage['zone_index']==0 and stage['slot']==4)
    following=world.get_region('Map Slot '+act4['stage_slot_id'])
    assert not clear.can_reach(state)
    assert not following.can_reach(state)
    state.collect(world.create_item('Stomp'),prevent_sweep=True)
    assert clear.can_reach(state)
    assert following.can_reach(state)


@pytest.mark.parametrize('mode',[0,1])
@pytest.mark.parametrize('movement',[False,True])
def test_asteroid_act_two_blocks_all_later_acts_and_boss(mode,movement):
    multi=generate({'starting_world':5,'world_progression':mode,'movement_unlocks':movement})
    world=multi.worlds[1];world.logic=deepcopy(world.logic);state=multi.state
    from ..Items import WORLD_ITEMS
    state.collect(world.create_item(WORLD_ITEMS[5]),prevent_sweep=True)
    # Isolate the unlock chain from individual sheet-route requirements.
    for key,row in world.logic['locations'].items():
        if key.startswith('stg6'):
            row['normal']=[[]];row['movement']=[[]]
    world.logic['locations']['stg630']['normal']=[['laser']]
    world.logic['locations']['stg630']['movement']=[['laser']]
    assert requirements(world,state,'stg610')
    assert not requirements(world,state,'stg630')
    for mission in ('stg640','stg650','stg660','stg620','stg690'):
        expected=mode==1 and mission!='stg690'
        assert check(world,state,world.logic,mission)==expected
        assert can_complete(world,state,mission)==expected
        region=world.get_region('Map Slot '+BY_MISSION[mission]['stage_slot_id'])
        assert region.can_reach(state)==expected
    # Pickup rules cannot bypass the predecessor clear, either.
    assert check(world,state,world.logic,'stg640:ring:5')==(mode==1)
    state.collect(world.create_item('Cyan Laser Wisp'),prevent_sweep=True)
    for mission in ('stg630','stg640','stg620','stg690'):
        assert can_complete(world,state,mission)
