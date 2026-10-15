"""Session-local AP ability overrides for logic/gameplay testing.

These are *not* ReceivedItems, AP receipts, or a change to the seed. The
immutable server-owned inventory is always the base; signed deltas can even
mask an item genuinely received. The entire override is discarded when the
Runtime is released. Only repeatable progression permissions are eligible.
"""
from collections import Counter
import re
import shlex

from ..Items import (MOVEMENT_ITEMS, ALL_WISP_ITEMS as WISP_ITEMS,
                     WORLD_ITEMS, EMERALDS, GAME_LAND_SPEED, RANDOM_CAPSULES,
                     RING_VALUES)

# Tropical Resort is the always-open starter world in native progression.
# A client-side Shuttle override cannot deny that world's access.
WORLD_UNLOCK_ITEMS = tuple(WORLD_ITEMS[1:])
TESTABLE = tuple(dict.fromkeys((*MOVEMENT_ITEMS, 'Breath', *WISP_ITEMS,
                                GAME_LAND_SPEED, RANDOM_CAPSULES,
                                *WORLD_UNLOCK_ITEMS, *EMERALDS)))
ABILITY_SET = tuple(dict.fromkeys((*MOVEMENT_ITEMS, 'Breath', *WISP_ITEMS)))
# The current progressive oxygen item is included; retired one-off Breath is
# NOT given by the movement group (it would override the 60-second tier).
ABILITY_GROUPS = {'wisps': tuple(WISP_ITEMS),
                  'movements': tuple(MOVEMENT_ITEMS),
                  'worlds': WORLD_UNLOCK_ITEMS}


def resolve_ability_group(raw):
    """Return a known batch target, or None so normal item parsing proceeds."""
    key = _key(raw)
    groups = {'wisps': 'wisps', 'wisp': 'wisps',
              'allwisps': 'wisps', 'allwisp': 'wisps',
              'movement': 'movements', 'movements': 'movements',
              'moves': 'movements', 'allmoves': 'movements',
              'allmovement': 'movements', 'allmovements': 'movements',
              'movementabilities': 'movements',
              'allmovementabilities': 'movements',
              'world': 'worlds', 'worlds': 'worlds',
              'allworld': 'worlds', 'allworlds': 'worlds',
              'worldaccess': 'worlds', 'allworldaccess': 'worlds',
              'shuttles': 'worlds', 'allshuttles': 'worlds'}
    return groups.get(key)
MAXIMUM = {'Progressive Pink Spikes Wisp':2, 'Progressive Green Hover Wisp':2, 'Progressive Yellow Drill Wisp':2, 'Progressive Skydiving':2, 'Progressive Rail':2, 'Progressive Stunts':5, 'Progressive Crouch': 2, 'Progressive Breathing': 5,
           GAME_LAND_SPEED: 4}


def _key(text):
    return re.sub(r'[^a-z0-9]+', '', text.casefold())


# Short capability names are more useful for logic testing than the colour.
# `breath` means the progressive item. The retired one-off `Breath` item
# remains available explicitly as `legacy breath` for old seed research.
_ALIAS = {'skydiving':'Progressive Skydiving', 'dive':'Progressive Skydiving', 'rail':'Progressive Rail', 'drift':'Drifting', 'stunts':'Progressive Stunts', 'stunt':'Progressive Stunts', 'crouch': 'Progressive Crouch', 'slide': 'Progressive Crouch',
          'breath': 'Progressive Breathing',
          'breathing': 'Progressive Breathing', 'oxygen': 'Progressive Breathing',
          'air': 'Progressive Breathing', 'legacy breath': 'Breath',
          'speed': GAME_LAND_SPEED,
          'capsules': RANDOM_CAPSULES, 'white': 'White Boost Wisp'}
# World access is represented by the five unlockable Shuttle items.  Accept
# natural zone names and convenient shortcuts without inventing an AP item.
# For example: /give sweet, /give world sweet, /remove aquarium.
for item in WORLD_UNLOCK_ITEMS:
    world = item.removesuffix(' Shuttle')
    short = world.split()[0]
    for alias in (world, short, 'world ' + world, 'world ' + short,
                  world + ' access', 'access ' + world, 'shuttle ' + world):
        _ALIAS.setdefault(_key(alias), item)

for item in TESTABLE:
    if item.endswith(' Wisp'):
        short = item[:-5].removeprefix('Progressive ')
        _ALIAS.setdefault(_key(short), item)
        _ALIAS.setdefault(_key(short+' Wisp'),item)
        parts = short.split()
        if len(parts) > 1:
            # Both /give cyan and /give laser should work.
            _ALIAS.setdefault(_key(parts[0]), item)
            _ALIAS.setdefault(_key(parts[-1]), item)


def resolve_item(raw):
    """Case-insensitive full name or unambiguous shorthand, no arbitrary IDs."""
    key = _key(raw)
    if key in ('tropical', 'tropicalresort', 'tropicalresortshuttle',
               'worldtropical', 'worldtropicalresort'):
        raise ValueError('Tropical Resort is always available as the starting world; its access cannot be removed.')
    if key in ('terminal', 'terminalvelocity', 'terminalvelocityshuttle',
               'worldterminal', 'worldterminalvelocity'):
        raise ValueError('Terminal Velocity has no Shuttle item; its access requires all eight Wisps. Use /give wisps or /remove wisps.')
    lookup = {_key(item): item for item in TESTABLE}
    # Explicit aliases intentionally override full item names: `breath`
    # refers to Progressive Breathing rather than the legacy one-off Breath.
    lookup.update({_key(alias): name for alias, name in _ALIAS.items()})
    if key in lookup:
        return lookup[key]
    matches = [item for item in TESTABLE if _key(item).startswith(key)] if key else []
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise ValueError('Ambiguous item; use one of: ' + ', '.join(matches))
    raise ValueError('Unknown or non-testable item: ' + repr(raw) + '. Use /testitems list.')


def parse_item_request(raw):
    """Accept `Double Jump`, `\"White Boost Wisp\"`, and a trailing count/all."""
    try:
        tokens = shlex.split(raw)
    except ValueError as exc:
        raise ValueError('Invalid quoting; example: /give "White Boost Wisp"') from exc
    if not tokens:
        raise ValueError('Missing item name; try /testitems list.')
    quantity = 1
    if len(tokens) > 1 and (tokens[-1].isdecimal() or tokens[-1].lower() == 'all'):
        token = tokens.pop()
        quantity = 'all' if token.lower() == 'all' else int(token)
        if quantity != 'all' and not 1 <= quantity <= 99:
            raise ValueError('Quantity must be from 1 to 99')
    return resolve_item(' '.join(tokens)), quantity


class LocalInventoryOverrides:
    """Signed differences from genuine AP item counts, never persisted."""

    def __init__(self):
        self.deltas = {}

    def reset(self):
        self.deltas.clear()

    def change(self, action, name, quantity, genuine):
        if name not in TESTABLE:
            raise ValueError('Not a testable ability/progression item: ' + name)
        if action not in ('give', 'remove'):
            raise ValueError('Unknown override action')
        base = int(genuine['counts'][name])
        prior = max(0, base + self.deltas.get(name, 0))
        cap = MAXIMUM.get(name, 1)
        if quantity == 'all':
            after = cap if action == 'give' else 0
        elif action == 'give':
            # For progressive unlocks, the number is an ABSOLUTE target tier.
            # `/give breath 2` => level 2 (10s), even if AP already gave level 4.
            # `/remove breath 2` still deducts two levels.
            after = min(cap, quantity) if name in MAXIMUM else min(cap, prior + quantity)
        else:
            after = max(0, prior - quantity)
        delta = after - base
        if delta:
            self.deltas[name] = delta
        else:
            self.deltas.pop(name, None)
        if name == 'Progressive Breathing' and genuine['counts']['Breath']:
            # Old seeds may genuinely own the retired 30-second Breath item.
            # The native oxygen logic prioritises that item, so locally mask
            # it while an explicit progressive breathing tier is being tested.
            self.deltas['Breath'] = -int(genuine['counts']['Breath'])
        return {'item': name, 'server_owned': base, 'before': prior,
                'effective': after, 'override_delta': delta, 'limit': cap,
                'quantity_mode': 'target_level' if action == 'give' and name in MAXIMUM else 'delta'}

    def change_all_abilities(self, action, genuine):
        return [self.change(action, name, 'all', genuine) for name in ABILITY_SET]

    def change_ability_group(self, action, group, genuine):
        """Apply a batch of local permissions without forging AP receipts."""
        if group not in ABILITY_GROUPS:
            raise ValueError('Unknown ability group: ' + repr(group))
        results = [self.change(action, name, 'all', genuine)
                   for name in ABILITY_GROUPS[group]]
        if group == 'movements':
            # Even an AP-owned or earlier manually given retired Breath must
            # not win over maximum Progressive Breathing (nor survive remove).
            results.append(self.change('remove', 'Breath', 'all', genuine))
        return results

    def apply(self, genuine):
        if not self.deltas:
            return genuine
        counts = Counter(genuine['counts'])
        for name, delta in self.deltas.items():
            counts[name] = max(0, counts[name] + delta)
        return {
            'counts': counts,
            'red_rings': sum(counts[name] * value for name, value in RING_VALUES.items()),
            'emeralds': [name for name in EMERALDS if counts[name]],
            'wisps': [name for name in WISP_ITEMS if counts[name]],
            'super_sonic_allowed': all(counts[name] for name in EMERALDS),
        }

    def describe(self, genuine):
        owned = self.apply(genuine)
        return {
            'mode': 'LOCAL SESSION TEST ONLY',
            'active': bool(self.deltas),
            'changes': {name: {'ap': genuine['counts'][name],
                               'effective': owned['counts'][name],
                               'delta': delta}
                        for name, delta in sorted(self.deltas.items())},
            'note': ('Not AP ReceivedItems; not sent as fake items; not journalled. '
                     'Actual pickups/checks made while testing can still reach the AP server. '
                     '/testitems reset restores original AP ownership. '
                     'Use a disposable test seed/save for logic testing.'),
        }
