"""Story map permission policy shared by the AP player and native projection."""
from .world_constants import STAGES


def available_story_stages(zone: int, cleared: set[str], mode: int) -> frozenset[str]:
    """Only world-owned progress grants entry; caller must separately gate World Access.

    The two forced Tropical Resort intro Acts are handled by native bootstrap,
    independent of this post-save policy.
    """
    if not 0 <= zone < 6 or mode not in (0, 1):
        raise ValueError('invalid story zone or world progression mode')
    acts = [s for s in STAGES if s['zone_index'] == zone and 1 <= s['slot'] <= 6]
    if len(acts) != 6:
        raise ValueError('incomplete original PAL world act catalog')
    boss = next(s for s in STAGES if s['zone_index'] == zone and s['slot'] == 7)
    available = {acts[0]['mission_id']}
    if mode == 0:
        for index in range(1, 6):
            if all(previous['mission_id'] in cleared for previous in acts[:index]):
                available.add(acts[index]['mission_id'])
            else:
                break
        if all(previous['mission_id'] in cleared for previous in acts):
            available.add(boss['mission_id'])
    else:
        available.update(s['mission_id'] for s in acts)
        if all(s['mission_id'] in cleared for s in acts):
            available.add(boss['mission_id'])
    return frozenset(available)


def verified_result_clear(snapshot):
    """Native final-result ownership; no save state or cached AP checks."""
    result = snapshot.current_result
    if (snapshot.scene_verified and snapshot.scene == 'results'
            and result.get('final') is True
            and result.get('mission') == snapshot.actual_mission
            and type(result.get('grade')) is int and 0 <= result['grade'] <= 4
            and result.get('provenance') == 'stage9C_native_UI_state7_grade124'
            and snapshot.actual_mission in {s['mission_id'] for s in STAGES}):
        return snapshot.actual_mission
    return None


def progression_clears(snapshot):
    """Include the attributed final result before native save/map construction.

    This is a permission input only: never manufacture a persisted clear or
    retain a result from a different scene, mission or playthrough.
    """
    cleared = set(snapshot.persisted_clears)
    mission = verified_result_clear(snapshot)
    if mission is not None:
        cleared.add(mission)
    return frozenset(cleared)
