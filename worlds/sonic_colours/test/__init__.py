from argparse import Namespace
from BaseClasses import MultiWorld, CollectionState
from Fill import distribute_items_restrictive
from test.general import gen_steps
from worlds.AutoWorld import call_all
from ..world import SonicColoursWorld


def generate(options=None, seed=0, fill=False):
    multiworld = MultiWorld(1)
    multiworld.set_seed(seed)
    multiworld.seed_name = f'SonicTest{seed}'
    multiworld.game[1] = SonicColoursWorld.game
    multiworld.player_name = {1: 'SonicPlayer'}
    args = Namespace()
    for name, option in SonicColoursWorld.options_dataclass.type_hints.items():
        # Native replay fixtures use the original starting world. Random Choice
        # behavior is tested separately against the actual option default.
        default = 0 if name == 'starting_act' else option.default
        setattr(args, name, {1: option.from_any((options or {}).get(name, default))})
    multiworld.set_options(args)
    multiworld.state = CollectionState(multiworld)
    for step in gen_steps:
        call_all(multiworld, step)
    if fill:
        distribute_items_restrictive(multiworld)
    return multiworld
