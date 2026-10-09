"""Only validated asset catalogs may be used to plan music changes."""
import hashlib
import random
from ..world_constants import NORMAL
from .memory import MemoryUnavailable


def plan_music(seed, mode, validated_assets):
    if mode not in ('off', 'per_world', 'anywhere'):
        raise ValueError('invalid music mode')
    result = {s['mission_id']: s['bgm'] for s in NORMAL}
    if mode == 'off':
        return result
    if not set(result.values()) <= set(validated_assets):
        raise MemoryUnavailable('music_asset_index_missing')
    rng = random.Random(int.from_bytes(hashlib.sha256(f'{seed}:sonic-music-v1'.encode()).digest(), 'big'))
    groups = [NORMAL] if mode == 'anywhere' else [tuple(s for s in NORMAL if s['zone_index'] == z) for z in range(6)]
    for group in groups:
        tracks = [s['bgm'] for s in group]
        rng.shuffle(tracks)
        result.update((s['mission_id'], track) for s, track in zip(group, tracks))
    return result
