"""Offline permutation planning; never advertised as a native stage patch."""
from ..world_constants import NORMAL, STAGES


def plan_stage_mapping(rng, mode):
    if mode not in ('off', 'per_world', 'anywhere'):
        raise ValueError('invalid stage mapping mode')
    result = {s['stage_slot_id']: s['mission_id'] for s in STAGES}
    groups = [NORMAL] if mode == 'anywhere' else [tuple(s for s in NORMAL if s['zone_index'] == z) for z in range(6)]
    if mode != 'off':
        for group in groups:
            missions = [s['mission_id'] for s in group]
            rng.shuffle(missions)
            result.update((s['stage_slot_id'], m) for s, m in zip(group, missions))
    return result
