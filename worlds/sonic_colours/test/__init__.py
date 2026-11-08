from argparse import Namespace
from BaseClasses import MultiWorld, CollectionState
from Fill import distribute_items_restrictive
from test.general import gen_steps
from worlds.AutoWorld import call_all
from ..world import SonicColoursWorld


def generate(options=None, seed=0, fill=False, player_name='SonicPlayer'):
    multiworld = MultiWorld(1)
    multiworld.set_seed(seed)
    multiworld.seed_name = f'SonicTest{seed}'
    multiworld.game[1] = SonicColoursWorld.game
    multiworld.player_name = {1: player_name}
    args = Namespace()
    for name, option in SonicColoursWorld.options_dataclass.type_hints.items():
        # Native replay fixtures use the original starting world. Random Choice
        # behavior is tested separately against the actual option default.
        default = option.default
        setattr(args, name, {1: option.from_any((options or {}).get(name, default))})
    multiworld.set_options(args)
    multiworld.state = CollectionState(multiworld)
    for step in gen_steps:
        call_all(multiworld, step)
    if fill:
        distribute_items_restrictive(multiworld)
    return multiworld


def legacy_rank_slot(data):
    """Restore the integer rank choice in fixtures for pre-selection seeds."""
    options=data.get('options',{})
    value=options.get('rank_checks')
    if data.get('options_revision',0)<15 and isinstance(value,list):
        choices={frozenset():0,frozenset({'S'}):1,frozenset({'A'}):2,
                 frozenset({'B'}):3,frozenset({'C'}):4,frozenset({'S','A','B','C'}):6}
        data['options']={**options,'rank_checks':choices[frozenset(value)]}
    return data
