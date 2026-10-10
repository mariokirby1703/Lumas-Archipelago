import json
import logging
from pathlib import Path

from worlds.AutoWorld import World
from . import Items, Locations, Regions, Rules
from .Options import SonicColoursOptions, OPTION_NAMES
from .web_world import SonicColoursWeb
from .world_constants import GAME, SCHEMA_VERSION, STARTING_STAGES, STAGES, WORLDS, load_data, game_land_gates, pack_rings

logger = logging.getLogger(__name__)


class SonicColoursWorld(World):
    """Sonic Colours Wii PAL Archipelago integration."""
    game = GAME
    web = SonicColoursWeb()
    options_dataclass = SonicColoursOptions
    options: SonicColoursOptions
    required_client_version = (0, 6, 7)
    item_name_to_id = Items.ITEM_TABLE
    location_name_to_id = {n: d.code for n, d in Locations.LOCATION_TABLE.items()}
    item_name_groups = {'Wisps': set(Items.WISP_ITEMS), 'World Access': set(Items.WORLD_ITEMS),
                        'Chaos Emeralds': set(Items.EMERALDS), 'Red Rings': set(Items.RING_VALUES),
                        'Traps': set(Items.TRAPS)}

    def generate_early(self):
        for option, capability in [('level_randomization', 'stage_shuffle'),
                                   ('death_link', 'native_death'),
                                   ('swim_trap_weight', 'swimming')]:
            if getattr(self.options, option).value:
                raise ValueError(f'Sonic Colours: {option} requires_verified_hook: {capability}. '
                                 'Use off until PAL live validation; see docs/development.md.')
        self.starting_stage = STARTING_STAGES[self.options.starting_act.value]
        self.starting_world = self.starting_stage['zone_index']
        self.gates = game_land_gates(self.options.game_land_requirement_reduction.value)
        self.active_locations = tuple(n for n, d in Locations.LOCATION_TABLE.items() if Locations.enabled(d, self.options))
        self.logic = load_data('logic_requirements.json')
        Rules.validate_logic(self.logic)
        self.unknown_logic = tuple(k for k, v in self.logic.items() if v['logic_status'] == 'unknown')
        logger.warning('Sonic Colours: provisional clear accessibility; %d unknown logic entries; '
                       'eight Wisps remain shuffled progression; native feature evidence is separate.',
                       len(self.unknown_logic))
        if self.options.wisp_capsules.value and not any(
                Locations.LOCATION_TABLE[n].kind == 'capsule' for n in self.active_locations):
            raise ValueError('wisp_capsules: no validated accessible capsule instances yet; '
                             'requires native opening/identity proof; use off.')
        self.stage_mapping = {s['stage_slot_id']: s['mission_id'] for s in STAGES}

    def create_regions(self):
        Regions.create_regions(self)

    def set_rules(self):
        Rules.set_rules(self)

    def create_items(self):
        names = []
        names += [n for i, n in enumerate(Items.WORLD_ITEMS) if i != self.starting_world]
        names += list(Items.WISP_ITEMS) + list(Items.EMERALDS)
        precollected = self.multiworld.precollected_items[self.player]
        for item in precollected:
            if item.name in names:
                names.remove(item.name)
        access = [n for n in Items.WORLD_ITEMS[:6] if n in names]
        if access:
            # One ordinary world expands the initial check pool. The remaining
            # access items and every Wisp use ordinary randomized fill.
            early = self.multiworld.local_early_items[self.player]
            early.setdefault(self.random.choice(access), 1)
        needs_land = bool(self.options.game_land_checks or self.options.chaos_emerald_checks
                          or self.options.goal.value == 3 or self.options.wisp_capsules or self.options.egg_medal_sanity)
        self.game_land_speed_items = needs_land
        speed_count = max(0, 4 - sum(i.name == Items.GAME_LAND_SPEED for i in precollected)) if needs_land else 0
        self.ring_required = max(self.gates.values()) if needs_land else 0
        self.ring_target = (4 * self.ring_required + 2) // 3
        remaining = max(0, self.ring_target - sum(Items.RING_VALUES.get(i.name, 0) for i in precollected))
        capacity = len(self.active_locations) - len(self.options.exclude_locations.value & set(self.active_locations)) - len(names)
        capacity = min(capacity, len(self.active_locations) - len(names) - speed_count)
        ring_items = [Items.ring_name(n) for n in pack_rings(remaining, capacity)]
        names += ring_items
        from worlds.generic.Rules import add_item_rule
        for location in self.multiworld.get_locations(self.player):
            data = Locations.LOCATION_TABLE.get(location.name)
            if data and any(s['mission_id'] == data.mission and s['zone_index'] >= 7
                            and s['slot'] > 1 for s in STAGES):
                add_item_rule(location, lambda item: item.player != self.player
                              or item.name not in Items.WISP_ITEMS + Items.WORLD_ITEMS)
        # With Singles, the ring pool can otherwise exhaust every Clear before
        # access items can be placed. Reserve completion routes only when the
        # remaining check capacity can hold the entire AP Ring pool. No early
        # item, world, sphere or location is forced by this constraint.
        nonclear_capacity = sum(Locations.LOCATION_TABLE[n].kind != 'clear'
                                and n not in self.options.exclude_locations.value
                                for n in self.active_locations)
        if len(ring_items) > 100 and nonclear_capacity >= len(ring_items):
            from worlds.generic.Rules import add_item_rule
            for location in self.multiworld.get_locations(self.player):
                data = Locations.LOCATION_TABLE.get(location.name)
                if data and data.kind == 'clear':
                    add_item_rule(location, lambda item: item.player != self.player
                                  or item.name not in Items.RING_VALUES)
        names += [Items.GAME_LAND_SPEED] * speed_count
        filler_count = len(self.active_locations) - len(names)
        if filler_count < 0:
            raise ValueError('Sonic Colours: enable more checks for mandatory progression.')
        weights = (0, 1, 3, 6)
        trap_weights = [weights[self.options.ring_loss_trap_weight.value], weights[self.options.swim_trap_weight.value]]
        if self.options.trap_percentage.value and not any(trap_weights):
            logger.warning('Sonic Colours: all trap weights off; keeping ordinary filler.')
        trap_count = (filler_count * self.options.trap_percentage.value + 50) // 100 if any(trap_weights) else 0
        if trap_count:
            names += self.random.choices(Items.TRAPS, weights=trap_weights, k=trap_count)
        names += [self.get_filler_item_name() for _ in range(filler_count - trap_count)]
        self.multiworld.itempool += [self.create_item(n) for n in names]

    def create_item(self, name):
        return Items.SonicColoursItem(name, Items.classification(name), Items.ITEM_TABLE[name], self.player)

    def get_filler_item_name(self):
        return self.random.choice(Items.FILLER)

    def fill_slot_data(self):
        return {'schema_version': SCHEMA_VERSION, 'game': GAME, 'seed_name': self.multiworld.seed_name,
                'starting_slot': self.starting_stage['stage_slot_id'],
                'starting_world': self.starting_world, 'game_land_gates': self.gates,
                'game_land_speed_items': self.game_land_speed_items,
                'stage_mapping': self.stage_mapping, 'unknown_logic': list(self.unknown_logic),
                'logic_policy': 'provisional_clears_conservative_pickups',
                'mandatory_prologue': ['stg110', 'stg130'],
                'locations': {n: Locations.LOCATION_TABLE[n].code for n in self.active_locations},
                'options': self.options.as_dict(*OPTION_NAMES)}

    def generate_output(self, output_directory):
        path = Path(output_directory) / f'{self.multiworld.get_out_file_name_base(self.player)}.apsonic'
        path.write_text(json.dumps({'game': GAME, 'player_name': self.multiworld.get_player_name(self.player),
                                    'slot_data': self.fill_slot_data()}, indent=2), encoding='utf-8')

    def write_spoiler_header(self, spoiler_handle):
        spoiler_handle.write(f'\nSonic Colours (Wii) PAL\n'
                             f'Starting slot: {self.starting_stage["name"]}\n'
                             f'Unknown logic entries: {len(self.unknown_logic)}\n'
                             'Wisps: shuffled; unknown clear routes provisional, optional pickups conservative.\n')
