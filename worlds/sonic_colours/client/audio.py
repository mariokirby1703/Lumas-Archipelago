"""Canonical Act cue identities; all shuffling belongs to music_bank.plan."""
from ..world_constants import NORMAL
from .memory import MemoryUnavailable


def canonical_act_cues(validated_assets):
    result = {s['mission_id']: s['bgm'] for s in NORMAL}
    if not set(result.values()) <= set(validated_assets):
        raise MemoryUnavailable('music_asset_index_missing')
    return result
