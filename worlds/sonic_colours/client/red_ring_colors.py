"""Scouted server rewards and per-location ring colors."""
import hashlib
import json

from ..Items import ITEM_TABLE, RING_VALUES
from ..Locations import LOCATION_TABLE


COLORS = {'purple': '#AF70FF', 'blue': '#305BD8', 'light_blue': '#64C8FF'}
RING_ITEM_IDS = frozenset(ITEM_TABLE[name] for name in RING_VALUES)
OPTION_DEFAULTS = {'red_ring_item_colors': 0, 'own_item_red_ring_colors': 0,
                   'trap_red_ring_colors': 0, 'colorblind_mode':0}


def trap_color(identity, location):
    """Rejection sampling keeps the three choices equiprobable without RNG state."""
    key = json.dumps([identity, location], ensure_ascii=True, separators=(',', ':'))
    ceiling = (1 << 256) // 3 * 3
    nonce = 0
    while True:
        value = int.from_bytes(hashlib.sha256(f'red-ring:{key}:{nonce}'.encode()).digest(), 'big')
        if value < ceiling:
            return tuple(COLORS)[value % 3]
        nonce += 1


def reward_color(item, receiver, flags, own_slot, options, identity, location):
    # AP's trap flag wins even when progression/useful flags are also present.
    if flags & 4:
        color=trap_color(identity, location) if options.get('trap_red_ring_colors', 0) else 'red'
        return accessible(color) if options.get('colorblind_mode',0) else color
    own_mode = options.get('own_item_red_ring_colors', 0)
    if receiver == own_slot and (own_mode == 0 or own_mode == 1 and item in RING_ITEM_IDS):
        return 'red'
    color='purple' if flags & 1 else 'blue' if flags & 2 else 'light_blue'
    return accessible(color) if options.get('colorblind_mode',0) else color


def accessible(color):
    return {'purple':'gold','blue':'accessible_blue','light_blue':'gray','red':'orange'}[color]


class RedRingColors:
    def __init__(self, slot_data, own_slot, team):
        self.options = slot_data['options']
        self.enabled = bool(self.options.get('red_ring_item_colors', 0))
        self.own_slot = own_slot
        self.identity = (slot_data['seed_name'], team, own_slot)
        self.locations = {}
        self.rewards = {}
        self.colors = {}
        self.stage_cache = {}
        from .red_ring_renderer import RingRenderer
        self.renderer = RingRenderer()
        if not self.enabled:
            return
        for name, code in slot_data['locations'].items():
            row = LOCATION_TABLE[name]
            if row.kind == 'ring':
                self.locations[row.mission, row.index] = code
            elif row.kind == 'rings':
                for ring in range(1, 6):
                    self.locations[row.mission, ring] = code
        self.scout_ids = frozenset(self.locations.values())

    def scout_message(self):
        if not self.enabled or not self.scout_ids:
            return None
        return {'cmd': 'LocationScouts', 'locations': sorted(self.scout_ids), 'create_as_hint': 0}

    def receive(self, rows):
        if not self.enabled or not isinstance(rows, (tuple, list)):
            return
        changed = False
        for row in rows:
            # LocationInfo contains NetworkItem tuples: item, location, player, flags.
            if not isinstance(row, (tuple, list)) or len(row) != 4:
                continue
            item, location, receiver, flags = row
            if (any(type(value) is not int for value in row) or location not in self.scout_ids
                    or item < 0 or receiver < 1 or not 0 <= flags <= 7):
                continue
            reward = (item, receiver, flags)
            if self.rewards.get(location) == reward:
                continue
            self.rewards[location] = reward
            self.colors[location] = reward_color(item, receiver, flags, self.own_slot,
                                                  self.options, self.identity, location)
            changed = True
        if changed:
            self.stage_cache.clear()

    def stage_colors(self, mission):
        if not self.enabled:
            return ('red',) * 5
        if mission not in self.stage_cache:
            self.stage_cache[mission] = tuple(
                self.colors.get(self.locations.get((mission, ring)), 'red') for ring in range(1, 6))
        return self.stage_cache[mission]

    def status(self, mission=None):
        return {'enabled': self.enabled, 'scouted': len(self.rewards),
                'locations': len(getattr(self, 'scout_ids', ())),
                'prepared_colors': self.stage_colors(mission) if self.enabled and mission else None,
                **self.renderer.status}
