import json
import logging
from pathlib import Path

from worlds.AutoWorld import World
from . import Items, Locations, Regions, Rules
from .Options import SonicColoursOptions, OPTION_NAMES
from .web_world import SonicColoursWeb
from .world_constants import GAME, SCHEMA_VERSION, NORMAL, STAGES, WORLDS, load_data, game_land_gates, pack_rings

logger = logging.getLogger(__name__)


class SonicColoursWorld(World):
    """PAL Sonic Colours research integration. Native hooks await live validation."""
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
        for option, capability in [('level_randomization', 'stage_shuffle'), ('music_randomization', 'music'),
                                   ('rank_checks', 'ranks'), ('death_link', 'native_death'),
                                   ('swim_trap_weight', 'swimming'), ('wisp_discovery_checks', 'wisp_permissions')]:
            if getattr(self.options, option).value:
                raise ValueError(f'Sonic Colours: {option} requires_verified_hook: {capability}. '
                                 'Use off until PAL live validation; see docs/development.md.')
        if self.options.goal.value == 2 and not self.options.red_ring_checks:
            raise ValueError('all_red_rings requires singles or per_level Red Ring checks.')
        if self.options.goal.value == 3 and not self.options.game_land_checks:
            raise ValueError('all_game_land requires game_land_checks=true.')
        self.starting_stage = NORMAL[self.options.starting_act.value]
        self.starting_world = self.starting_stage['zone_index']
        self.gates = game_land_gates(self.options.game_land_requirement_reduction.value)
        self.active_locations = tuple(n for n, d in Locations.LOCATION_TABLE.items() if Locations.enabled(d, self.options))
        self.logic = load_data('logic_requirements.json')
        Rules.validate_logic(self.logic)
        self.unknown_logic = tuple(k for k, v in self.logic.items() if v['logic_status'] == 'unknown')
        logger.warning('Sonic Colours: provisional clear accessibility; %d unknown logic entries; '
                       'eight Wisps remain shuffled progression; native feature evidence is separate.',
                       len(self.unknown_logic))
        if self.options.wisp_capsule_sanity.value and not any(
                Locations.LOCATION_TABLE[n].kind == 'capsule' for n in self.active_locations):
            raise ValueError('wisp_capsule_sanity: no validated accessible capsule instances yet; '
                             'requires native opening/identity proof; use off.')
        self.stage_mapping = {s['stage_slot_id']: s['mission_id'] for s in STAGES}

    def create_regions(self):
        Regions.create_regions(self)

    def set_rules(self):
        Rules.set_rules(self)

    def create_items(self):
        names = []
        if self.options.world_unlocks.value:
            names += [n for i, n in enumerate(Items.WORLD_ITEMS) if i != self.starting_world]
        if self.options.wisp_unlocks.value:
            names += list(Items.WISP_ITEMS)
        if self.options.chaos_emerald_items:
            names += list(Items.EMERALDS)
        needs_land = bool(self.options.game_land_checks or self.options.chaos_emerald_checks or self.options.goal.value == 3)
        self.ring_target = max(self.gates.values()) if needs_land else 0
        names += [Items.ring_name(n) for n in pack_rings(self.ring_target,
                   self.options.red_ring_bundle_strategy.current_key, len(self.active_locations) - len(names))]
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
                'research_only': True, 'starting_slot': self.starting_stage['stage_slot_id'],
                'starting_world': self.starting_world, 'game_land_gates': self.gates,
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
        spoiler_handle.write(f'\nSonic Colours: RESEARCH ONLY; native hooks not live verified.\n'
                             f'Starting slot: {self.starting_stage["name"]}\n'
                             f'Unknown logic entries: {len(self.unknown_logic)}\n'
                             'Wisps: shuffled; unknown clear routes provisional, optional pickups conservative.\n')
