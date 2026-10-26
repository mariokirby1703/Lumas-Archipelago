from argparse import Namespace

import pytest
from BaseClasses import MultiWorld,CollectionState
from Fill import distribute_items_restrictive
from Options import ItemLinks
from worlds.AutoWorld import call_all
from . import SonicColoursWorld


def linked_world(seed,replacement,rings='singles'):
    multi=MultiWorld(2);multi.set_seed(seed)
    multi.game={1:SonicColoursWorld.game,2:SonicColoursWorld.game}
    multi.player_name={1:'Linker 1',2:'Linker 2'}
    args=Namespace()
    for name,option in SonicColoursWorld.options_dataclass.type_hints.items():
        setattr(args,name,{p:option.from_any(rings if name=='red_ring_checks' else option.default)
                           for p in (1,2)})
    group=[{'name':'ItemLinkTest','item_pool':['Everything'],
            'link_replacement':replacement,'replacement_item':None}]
    args.item_links={p:ItemLinks.from_any(group) for p in (1,2)}
    multi.set_options(args);multi.set_item_links();multi.state=CollectionState(multi)
    for step in ('generate_early','create_regions','create_items','set_rules',
                 'connect_entrances','generate_basic'):
        call_all(multi,step)
    multi.link_items();call_all(multi,'pre_fill')
    return multi


@pytest.mark.parametrize('seed',(0,1,2,9))
@pytest.mark.parametrize('replacement',[False,True])
@pytest.mark.parametrize('rings',['singles','per_level'])
def test_everything_linked_fills_without_start_items(seed,replacement,rings):
    multi=linked_world(seed,replacement,rings)
    distribute_items_restrictive(multi)
    assert multi.can_beat_game(CollectionState(multi))
    assert not multi.get_unfilled_locations()
    assert all(not items for items in multi.precollected_items.values())
    assert all(loc.item.location is loc for loc in multi.get_filled_locations())
