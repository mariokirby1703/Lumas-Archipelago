"""Read-only tracker scene bridge for Sonic Colours Wii AP.

Optional drop-in: copy this module into worlds/sonic_colours/client and wire
publish_scene() after a successful native runtime poll in client.py.
It adds no Dolphin reads, no writes, and no extra polling.
"""

from __future__ import annotations

_ALLOWED = frozenset(("global_map", "world_map", "game_land_select", "gameplay", "results"))


def _payload(snapshot, seed):
    """Only report scenes proved by the already-authenticated native poll."""
    if snapshot is None or not snapshot.scene_verified:
        return None
    scene = snapshot.scene
    if scene not in _ALLOWED:
        return None
    mission = None
    zone = None
    if scene in ("gameplay", "results"):
        mission = snapshot.actual_mission
        if not isinstance(mission, str) or not mission:
            return None
    if scene == "world_map":
        stage_objects = snapshot.evidence.get("native_data", {}).get("stage_objects", ())
        # PAL map actor 0x807773F8 and zone are verified by native_read,
        # not inferred from the previous gameplay mission.
        for stage in stage_objects:
            data = stage.get("world_map_access")
            if not data:
                continue
            maybe_zone = data.get("zone")
            if type(maybe_zone) is int and 0 <= maybe_zone <= 6:
                zone = maybe_zone
                break
        # When zone cannot be proven, don't erroneously switch to a stale area.
        if zone is None:
            return None
    return {"seed": seed, "verified": True, "scene": scene,
            "mission": mission, "zone": zone}


async def publish_scene(ctx, snapshot):
    """Send one AP Set update per *change* in the verified native scene."""
    runtime = getattr(ctx, "runtime", None)
    identity = getattr(ctx, "authenticated_identity", None)
    if not runtime or not identity or getattr(ctx, "server", None) is None:
        return
    team, slot, seed = identity
    if (team, slot, seed) != (getattr(ctx, "team", None), getattr(ctx, "slot", None),
                               getattr(ctx, "server_seed", None)):
        return
    data = _payload(snapshot, seed)
    if data is None:
        return
    if getattr(ctx, "_tracker_scene_last", None) == (team, slot, data):
        return
    key = f"Sonic_Colours_Scene_{team}_{slot}"
    await ctx.send_msgs([{"cmd": "Set", "key": key, "default": None,
                          "want_reply": False, "operations": [
                              {"operation": "replace", "value": data}
                          ]}])
    ctx._tracker_scene_last = (team, slot, data)
