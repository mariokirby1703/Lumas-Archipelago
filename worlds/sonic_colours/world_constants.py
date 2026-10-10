"""Stable public identifiers. Never derive IDs from enabled option subsets."""
import json
from importlib.resources import files

GAME = "Sonic Colours (Wii)"
BASE_ID = 847000000
SCHEMA_VERSION = 5


def load_data(name):
    return json.loads(files(__package__).joinpath('data', name).read_text(encoding='utf-8'))


STAGES = load_data('stage_map.json')
BY_MISSION = {s['mission_id']: s for s in STAGES}
NORMAL = tuple(s for s in STAGES if s['normal'])
# Keep the original 36 explicit Choice values stable, then append bosses/TV.
STARTING_STAGES = NORMAL + tuple(s for s in STAGES if s['zone_index'] < 6
                                and not s['normal'] and s['mission_id'] != 'stg790')
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


def pack_rings(target, capacity):
    """Exact value, maximizing singles; prefer fives when singles tie."""
    if target < 0 or capacity < 0:
        raise ValueError('Invalid Red Ring budget/capacity')
    best = None
    for tens in range(target // 10 + 1):
        for fives in range((target - tens * 10) // 5 + 1):
            singles = target - tens * 10 - fives * 5
            if singles + fives + tens <= capacity:
                score = (singles, -tens, fives)
                if best is None or score > best[0]:
                    best = score, singles, fives, tens
    if best is None:
        raise ValueError('Too few non-excluded checks for mandatory progression; enable more checks.')
    return (1,) * best[1] + (5,) * best[2] + (10,) * best[3]
