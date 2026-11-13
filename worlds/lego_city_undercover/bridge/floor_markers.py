"""Reproduce the marker branch ordering in RVA 0x800a0, without engine calls.

This predicts the marker resource, not visibility, occupancy or full usability.
Class availability uses existing owned/pending observations, not a native call.
"""
import struct

CLASS_NAMES = ('Polizist', 'Räuber', 'Minenarbeiter', 'Astronaut', 'Farmer', 'Feuerwehr', 'Bauarbeiter')
DEFAULT_MODELS = (227, 228, 237, 234, 233, 232, 230)
ICON_NAMES = dict(enumerate((
    'Cop', 'Astro', 'Farmer', 'Constr', 'Trans', 'Torch', 'Gong', 'Feather', 'JCan',
    'Keycard', 'Pig', 'Jet', 'Orange_Fish', 'Robber_Crowbar', 'Robber_EnergyGun',
    'Robber_Stethoscope', 'Constr_Cup', 'Constr_Drill', 'Constr_Hammer', 'Fireman_Axe',
    'Fireman_Fish', 'fire_extinguisher', 'Robber_Locked', 'Fireman_Locked', 'Cop_Locked',
    'Astro_Locked', 'Farmer_Locked', 'Constr_Locked', 'Trans_Locked', 'Glide'), 632))


def read_class_availability(read, base, inventory):
    raw = read(base + 0x17EBE70, 0x70)
    ids = tuple(struct.unpack_from('<h', raw, i*16)[0] for i in range(7))
    enabled = bool(read(base + 0x17EBE2C, 1)[0])
    if ids != DEFAULT_MODELS:
        return None
    rows = inventory['characters'] + inventory['auxiliary_states']
    granted = {r['model_id'] for r in rows if r['unlock_candidate']}
    return {i: bool(enabled and model in granted) for i, model in enumerate(ids)}


def predict_floor_marker(flags, classes=None, abilities=None, custom_icon=None):
    # Native precedence matters when several flags are set.
    required = ability = None
    active = locked = None
    if flags & 0x10004010: required, active, locked = 0, 632, 656
    elif flags & 0x200: required, active, locked = 5, 651, 655
    elif flags & 0x20: required, active, locked = 5, 652, 655
    elif flags & 0x180: required, active, locked = 1, 645, 654
    elif flags & 2: required, active, locked = 1, 647, 654
    elif flags & 0x80000: required, active, locked, ability = 1, 646, 654, 'EnergyGun'
    elif flags & 0x40000001: required, active, locked = 4, 634, 658
    elif flags & 4: required, active, locked = 3, 633, 657
    elif flags & 0x2000: required, active, locked = 6, 648, 659
    elif flags & 0x1000: required, active, locked = 6, 649, 659
    elif flags & 0x400: required, active, locked = 6, 650, 659
    elif flags & 0x40000: required, active, locked = 2, 636, 660
    elif flags & 0x4000000: active = 637
    elif flags & 0x8000000: active = 638
    elif flags & 0x20000000: active = 640
    elif flags & 0x80000000: active = custom_icon
    elif flags & 0x1000000: required, active, locked = 4, 661, 658
    elif flags & 0x2000000: required, active, locked, ability = 3, 643, 657, 'Jetpack'
    elif flags & 0x20000: required, active, locked = 4, 642, 658
    # The native fallback also contains a special global-object comparison.
    # Its result is unknown here instead of treating every switch as generic.
    class_ready = classes.get(required) if classes is not None and required is not None else None
    ability_ready = (abilities or {}).get(ability) if ability else True
    if required is None:
        lock_candidate = False if active is not None else None
    elif class_ready is False or ability_ready is False:
        lock_candidate = True
    elif class_ready is True and ability_ready is True:
        lock_candidate = False
    else:
        lock_candidate = None
    predicted = locked if lock_candidate is True else active if lock_candidate is False else None
    return dict(required_class=CLASS_NAMES[required] if required is not None else None,
                required_ability=ability,
                available_marker='Hotspot_Ability_Floor_' + ICON_NAMES[active] if active in ICON_NAMES else None,
                locked_marker='Hotspot_Ability_Floor_' + ICON_NAMES[locked] if locked in ICON_NAMES else None,
                predicted_marker='Hotspot_Ability_Floor_' + ICON_NAMES[predicted] if predicted in ICON_NAMES else None,
                class_lock_candidate=lock_candidate, rendered_state_verified=False,
                evidence='RVA 0x800a0 branches plus owned/pending class observations; not a complete interaction gate')
