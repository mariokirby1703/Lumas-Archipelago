"""Stable public identifiers. Never derive IDs from enabled option subsets."""
import json
from importlib.resources import files

GAME = "Sonic Colours (Wii)"
BASE_ID = 847000000
SCHEMA_VERSION = 2


def load_data(name):
    return json.loads(files(__package__).joinpath('data', name).read_text(encoding='utf-8'))


STAGES = load_data('stage_map.json')
BY_MISSION = {s['mission_id']: s for s in STAGES}
NORMAL = tuple(s for s in STAGES if s['normal'])
WORLDS = tuple(dict.fromkeys(s['world'] for s in STAGES if s['zone_index'] < 7))
WISPS = ('White Boost', 'Cyan Laser', 'Yellow Drill', 'Orange Rocket',
         'Blue Cube', 'Green Hover', 'Pink Spikes', 'Purple Frenzy')
RANKS = ('S', 'A', 'B', 'C')


def game_land_gates(reduction):
    if type(reduction) is not int or not 0 <= reduction <= 179:
        raise ValueError('Game Land reduction must be an integer in 0..179')
    adjusted = []
    for vanilla in range(50, 181, 10):
        adjusted.append(max(1, vanilla - reduction, adjusted[-1] + 1 if adjusted else 1))
    return {f'{i + 1}-{act}': 0 if act == 1 else adjusted[i + (7 if act == 3 else 0)]
            for i in range(7) for act in (1, 2, 3)}


def pack_rings(target, strategy, capacity):
    denominations = {'small': (1,), 'medium': (1, 5), 'large': (1, 5, 10),
                     'auto': (1, 5, 10)}[strategy]
    best = [()] + [None] * target
    for amount in range(1, target + 1):
        choices = [best[amount - n] + (n,) for n in denominations
                   if n <= amount and best[amount - n] is not None]
        best[amount] = min(choices, key=lambda seq: (len(seq), seq))
    result = best[target]
    if len(result) > capacity:
        if strategy != 'auto':
            raise ValueError('Too few checks for Red Ring bundles; use auto/large or enable more checks.')
        raise ValueError('Too few checks for mandatory progression; enable more checks.')
    return result
