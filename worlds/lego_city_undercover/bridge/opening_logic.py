"""Observed opening reachability; this is not complete game logic."""
import json
import pkgutil
from pathlib import Path

_data=pkgutil.get_data(__package__,'opening_no_police.json') if __package__ else Path(__file__).with_name('opening_no_police.json').read_bytes()
NO_POLICE_KEYS=frozenset(json.loads(_data)['no_police_location_keys'])
POLICE_ITEMS=('Ability: Police','Character: COP')


def has_police(state,player):
    return any(state.has(name,player) for name in POLICE_ITEMS)
