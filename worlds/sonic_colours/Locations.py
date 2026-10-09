from dataclasses import dataclass
from BaseClasses import Location
from .world_constants import BASE_ID, GAME, STAGES, WISPS, RANKS, BY_MISSION
from .capsules import CAPSULES


class SonicColoursLocation(Location):
    game = GAME


@dataclass(frozen=True)
class LocationData:
    code: int
    mission: str
    kind: str
    index: int = 0
    instance_key: str = ''


LOCATION_TABLE = {}
for stage_index, stage in enumerate(STAGES):
    mission, name = stage['mission_id'], stage['name']
    base = BASE_ID + 1000 + stage_index * 32
    LOCATION_TABLE[f'{name} - Clear'] = LocationData(base, mission, 'clear')
    if stage['normal']:
        for ring in range(1, 6):
            LOCATION_TABLE[f'{name} - Red Ring {ring}'] = LocationData(base + ring, mission, 'ring', ring)
        LOCATION_TABLE[f'{name} - All 5 Red Rings'] = LocationData(base + 6, mission, 'rings')
    if stage['rank_candidate']:
        for rank, label in enumerate(RANKS):
            LOCATION_TABLE[f'{name} - {label} Rank'] = LocationData(base + 8 + rank, mission, 'rank', rank)
    if stage['zone_index'] >= 7 and stage['slot'] == 3:
        land = stage['zone_index'] - 6
        LOCATION_TABLE[f'Game Land {land} - Chaos Emerald Obtained'] = LocationData(base + 16, mission, 'emerald', land)
# Native discovery table at PAL 80720B98, queried by 80228B30.
DISCOVERY_STAGES = {1:(0,3), 2:(1,1), 3:(2,1), 4:(3,1), 5:(1,3), 6:(2,5), 7:(5,1)}
for i, wisp in enumerate(WISPS):
    mission = next((s['mission_id'] for s in STAGES if (s['zone_index'],s['slot']) == DISCOVERY_STAGES.get(i)), '')
    LOCATION_TABLE[f'{wisp} - First Discovery'] = LocationData(BASE_ID + 4000 + i, mission, 'wisp', i)
for capsule in CAPSULES.values():
    if capsule.name:
        if capsule.name in LOCATION_TABLE:
            raise ValueError('capsule display identity collision: ' + capsule.name)
        LOCATION_TABLE[capsule.name] = LocationData(capsule.code, capsule.mission, 'capsule', instance_key=capsule.key)


def enabled(data, options):
    if data.kind == 'clear':
        return BY_MISSION[data.mission]['zone_index'] < 7 or bool(options.game_land_checks)
    if data.kind == 'ring':
        return options.red_ring_checks.value == 1
    if data.kind == 'rings':
        return options.red_ring_checks.value == 2
    if data.kind == 'rank':
        value = options.rank_checks.value
        return value == 6 or value == data.index + 1
    if data.kind == 'emerald':
        return bool(options.chaos_emerald_checks)
    if data.kind == 'capsule':
        capsule = CAPSULES[data.instance_key]
        return capsule.eligible and bool(options.wisp_capsules)
    # White Boost has no native colour-unlock flag/event in the PAL accessor.
    # Keep its stable catalog ID, but don't generate an unreportable location.
    return data.index != 0 and bool(options.wisp_discovery_checks)
