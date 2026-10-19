"""Stable public identifiers. Never derive IDs from enabled option subsets."""
import json
from importlib.resources import files

GAME = "Sonic Colours (Wii)"
BASE_ID = 847000000
SCHEMA_VERSION = 7


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
# PAL native colour/permission indices, distinct from the stable AP item order.
# 80765390's indexed sound table: 1 laser, 2 spike, 3 rocket, 4 rodeo,
# 5 puzzle, 6 astronautes; capsule ORC colour is native index + 1.
NATIVE_COLOURS = ('Yellow Drill', 'Cyan Laser', 'Pink Spikes', 'Orange Rocket',
                  'Purple Frenzy', 'Blue Cube', 'Green Hover')
GAME_LAND_EMERALD_COLOURS = ('Green','Yellow','White','Red','Purple','Blue','Cyan')
def wisp_item(colour, movement_unlocks=True):
    prefix = 'Progressive ' if movement_unlocks and colour in ('Yellow Drill','Green Hover','Pink Spikes') else ''
    return prefix + colour + ' Wisp'


RANKS = ('S', 'A', 'B', 'C')


def game_land_reduction_points(percentage):
    """Map the new 0..99 percent slider onto the original 0..179 point scale.

    Use integer ceiling of 180 * percentage / 100: 50% -> 90 and 99% -> 179.
    Leave game_land_gates() in its historical units so all stage thresholds,
    including those in old seeds, are calculated exactly as before.
    """
    if type(percentage) is not int or not 0 <= percentage <= 99:
        raise ValueError('Game Land reduction percentage must be an integer in 0..99')
    return (180 * percentage + 99) // 100


def game_land_gates(reduction):
    if type(reduction) is not int or not 0 <= reduction <= 179:
        raise ValueError('Game Land reduction must be an integer in 0..179')
    # One integer step across all 21 gates; never flatten early thresholds.
    # The highest requirement stays below the remaining 180-ring budget.
    step = max(1, (180 - reduction - 1) // 20)
    return {f'{world}-{act}': 0 if (world,act)==(1,1) else 1 + ((act-1)*7 + world-1)*step
            for act in (1,2,3) for world in range(1,8)}


def legacy_game_land_gates(reduction):
    """Read-only compatibility for previously generated schema-7 servers."""
    adjusted = []
    for vanilla in range(50,181,10):
        adjusted.append(max(1,vanilla-reduction,adjusted[-1]+1 if adjusted else 1))
    return {f'{i+1}-{act}':0 if act==1 else adjusted[i+(7 if act==3 else 0)]
            for i in range(7) for act in (1,2,3)}



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
