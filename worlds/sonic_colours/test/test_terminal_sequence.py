import pytest
from ..world_progression import available_story_stages


@pytest.mark.parametrize('mode',[0,1])
def test_terminal_uses_vanilla_order_for_both_options(mode):
    assert available_story_stages(6,set(),mode)=={'stg710'}
    assert available_story_stages(6,{'stg710'},mode)=={'stg710','stg790'}
    assert available_story_stages(6,{'stg710','stg790'},mode)=={'stg710','stg790','stg720'}
    assert available_story_stages(6,{'stg790'},mode)=={'stg710'}
