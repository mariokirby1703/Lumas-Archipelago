"""Shield grouping policy; consumes verified part identities, never guesses save bits.

This does not read the game or register AP locations. Native persistence is pending.
"""
PARTS = ('TL', 'TR', 'BL', 'BR')
PICKUP_TYPES = {119: 'TL', 120: 'TR', 121: 'BL', 101: 'BR'}


def shield_locations(mission: str, mode: str) -> tuple[str, ...]:
    if not mission or mode not in ('whole', 'quarters'):
        raise ValueError('Mission and valid shield mode are required')
    if mode == 'whole':
        return (f'{mission}: Police Shield',)
    return tuple(f'{mission}: Police Shield {part}' for part in PARTS)


def completed_shield_locations(mission: str, mode: str, collected_parts) -> tuple[str, ...]:
    collected = set(collected_parts)
    if not collected.issubset(PARTS):
        raise ValueError('Unknown shield part identity')
    locations = shield_locations(mission, mode)
    if mode == 'whole':
        return locations if collected == set(PARTS) else ()
    return tuple(location for part, location in zip(PARTS, locations) if part in collected)
