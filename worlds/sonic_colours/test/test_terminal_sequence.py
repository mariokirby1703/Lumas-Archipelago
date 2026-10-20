import pytest
from ..world_progression import available_story_stages


@pytest.mark.parametrize('mode',[0,1])
def test_terminal_uses_vanilla_order_for_both_options(mode):
    assert available_story_stages(6,set(),mode)=={'stg710'}
    assert available_story_stages(6,{'stg710'},mode)=={'stg710','stg790'}
    assert available_story_stages(6,{'stg710','stg790'},mode)=={'stg710','stg790','stg720'}
    assert available_story_stages(6,{'stg790'},mode)=={'stg710'}


@pytest.mark.parametrize('option,expected', [('off',0),('s',1),('a',1),('b',1),('c',1),('all',4)])
def test_terminal_boss_ranks_follow_rank_option(option,expected):
    from . import generate
    world=generate({'rank_checks':option})
    locations=[loc for loc in world.get_locations(1)
               if loc.name.startswith('Terminal Velocity Boss - ') and loc.name.endswith(' Rank')]
    assert len(locations)==expected


@pytest.mark.parametrize('grade,expected',[(0,4),(1,3),(2,2),(3,1),(4,0)])
def test_terminal_boss_reports_native_ranks(grade,expected):
    from ..Locations import LOCATION_TABLE
    from ..world_constants import BASE_ID,STAGES
    from ..client.runtime import detect_checks
    from .test_runtime import snapshot
    ranks={name:data.code for name,data in LOCATION_TABLE.items()
           if data.mission=='stg790' and data.kind=='rank'}
    index=next(i for i,s in enumerate(STAGES) if s['mission_id']=='stg790')
    assert set(ranks.values())=={BASE_ID+1000+index*32+8+i for i in range(4)}
    slot={'locations':ranks}
    assert len(detect_checks(slot,snapshot(awarded_ranks={'stg790':grade})))==expected
    assert not detect_checks(slot,snapshot(persisted_clears={'stg790'}))
