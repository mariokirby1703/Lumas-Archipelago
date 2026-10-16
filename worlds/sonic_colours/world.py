import json
import logging
from pathlib import Path
from typing import ClassVar
from .settings import SonicColoursSettings

from worlds.AutoWorld import World
from . import Items, Locations, Regions, Rules
from .Options import SonicColoursOptions, OPTION_NAMES
from .web_world import SonicColoursWeb
from .world_constants import GAME, SCHEMA_VERSION, STAGES, WORLDS, load_data, game_land_gates, pack_rings

logger = logging.getLogger(__name__)


class SonicColoursWorld(World):
    """Sonic Colours Wii PAL Archipelago integration."""
    game = GAME
    web = SonicColoursWeb()
    options_dataclass = SonicColoursOptions
    options: SonicColoursOptions
    settings: ClassVar[SonicColoursSettings]
    required_client_version = (0, 6, 7)
    item_name_to_id = Items.ITEM_TABLE
    location_name_to_id = {n: d.code for n, d in Locations.LOCATION_TABLE.items()}
    item_name_groups = {'Wisps': set(Items.ALL_WISP_ITEMS), 'World Access': set(Items.WORLD_ITEMS),
                        'Chaos Emeralds': set(Items.EMERALDS), 'Red Rings': set(Items.RING_VALUES),
                        'Traps': set(Items.TRAPS), 'Movement': set(Items.MOVEMENT_ITEMS)}

    def generate_early(self):
        if not self.options.game_land_checks:
            self.options.eggman_heart_sanity.value=0
            self.options.chaos_emerald_checks.value=0
        validation=load_data('versions.json').get('live_validation',{})
        for option, capability in [('death_link', 'deathlink'),('dead_weight_trap_weight','dead_weight')]:
            if getattr(self.options, option).value and not validation.get(capability) and not self.options.native_feature_tests:
                raise ValueError(f'Sonic Colours: {option} requires_verified_hook: {capability}. '
                                 'Native implementation awaits the PAL live test matrix; use off until verified.')
        if self.options.native_feature_tests:
            logger.warning('Sonic Colours: unverified native feature TEST opt-in; PAL live matrix incomplete.')
        self.starting_stage = next(s for s in STAGES if s['mission_id'] == 'stg110')
        self.starting_world = 0
        self.gates = game_land_gates(self.options.game_land_requirement_reduction.value)
        self.active_locations = tuple(n for n, d in Locations.LOCATION_TABLE.items() if Locations.enabled(d, self.options))
        self.logic = load_data('logic_from_sheet_v2.json')
        from .logic_v2 import validate_manifest
        validate_manifest(self.logic)
        self.unknown_logic = tuple(k for k,v in self.logic['locations'].items() if v['normal']['status']=='not_documented')
        logger.info('Sonic Colours: Sheet Logic V2; %d undocumented Normal routes use conservative fallback.',
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
        from .wisps import required_wisp_items
        names += list(required_wisp_items(self.options))
        if self.options.movement_unlocks:
            names += ['Progressive Yellow Drill Wisp','Progressive Green Hover Wisp','Progressive Pink Spikes Wisp']
        if self.options.game_land_checks:names += [Items.RANDOM_CAPSULES]
        if self.options.super_sonic.value:
            names += list(Items.EMERALDS)
        if self.options.movement_unlocks.value:
            names += [name for name in Items.MOVEMENT_POOL
                      if name!='Assist Change' or self.options.game_land_checks.value]
        precollected = self.multiworld.precollected_items[self.player]
        for item in precollected:
            if item.name in names:
                names.remove(item.name)
        access = [n for n in Items.WORLD_ITEMS[:6] if n in names]
        if access:
            # One ordinary world expands the initial check pool. The remaining
            # access items and every Wisp use ordinary randomized fill.
            early = self.multiworld.local_early_items[self.player]
            from BaseClasses import CollectionState
            initial=CollectionState(self.multiworld)
            opening=[item for item in access if Rules.requirements(self,initial,next(
                stage['mission_id'] for stage in STAGES if stage['zone_index']==Items.WORLD_ITEMS.index(item) and stage['slot']==1))]
            if opening:access=opening
            early.setdefault(self.random.choice(access), 1)
        needs_land = bool(self.options.game_land_checks)
        self.game_land_speed_items = bool(self.options.game_land_checks.value)
        speed_count = max(0, 4 - sum(i.name == Items.GAME_LAND_SPEED for i in precollected)) if self.game_land_speed_items else 0
        self.ring_required = max(self.gates.values()) if needs_land else 0
        self.ring_target = (4 * self.ring_required + 2) // 3
        remaining = max(0, self.ring_target - sum(Items.RING_VALUES.get(i.name, 0) for i in precollected))
        capacity = len(self.active_locations) - len(self.options.exclude_locations.value & set(self.active_locations)) - len(names)
        capacity = min(capacity, len(self.active_locations) - len(names) - speed_count)
        # In small check sets, mostly-single currency can occupy almost every
        # ordinary route and leave the abilities needed by Game Land stranded.
        # Bundle currency while retaining the exact target value and reserve
        # ordinary check capacity for the mandatory non-currency progression.
        ordinary=sum(next(s for s in STAGES if s['mission_id']==Locations.LOCATION_TABLE[n].mission)['zone_index']<7
                     for n in self.active_locations if n not in self.options.exclude_locations.value)
        minimum_currency_items=remaining//10+(remaining%10)//5+remaining%5
        capacity=min(capacity,max(minimum_currency_items,ordinary-len(names)-speed_count))
        ring_items = [Items.ring_name(n) for n in pack_rings(remaining, capacity)]
        names += ring_items
        # The restrictive filler already prevents item self-locks. Blanket
        # Wisp/world bans in Game Land and Red Ring bans on Clears exhaust
        # reachable slots with Sheet V2's individual movement requirements.
        names += [Items.GAME_LAND_SPEED] * speed_count
        filler_count = len(self.active_locations) - len(names)
        if filler_count < 0:
            raise ValueError('Sonic Colours: enable more checks for mandatory progression.')
        weights = (0, 1, 3, 6)
        trap_weights = [weights[self.options.ring_loss_trap_weight.value], weights[self.options.score_reset_trap_weight.value],
                        weights[self.options.dead_weight_trap_weight.value]]
        if self.options.trap_percentage.value and not any(trap_weights):
            logger.warning('Sonic Colours: all trap weights off; keeping ordinary filler.')
        trap_count = (filler_count * self.options.trap_percentage.value + 50) // 100 if any(trap_weights) else 0
        if trap_count:
            names += self.random.choices(Items.TRAPS, weights=trap_weights, k=trap_count)
        names += [self.get_filler_item_name() for _ in range(filler_count - trap_count)]
        self.multiworld.itempool += [self.create_item(n) for n in names]

    def fill_hook(self, progitempool, usefulitempool, filleritempool, fill_locations):
        # Reverse restrictive fill must place the many interchangeable rings
        # while access/ability items are still in its maximum exploration state.
        # Otherwise removing one ability can strand hundreds of ring receipts.
        progitempool.sort(key=lambda item: item.player == self.player and item.name in Items.RING_VALUES)

    def create_item(self, name):
        from BaseClasses import ItemClassification
        kind=Items.classification(name)
        if name==Items.RANDOM_CAPSULES:
            kind=ItemClassification.progression if self.options.wisp_capsules else ItemClassification.useful
        return Items.SonicColoursItem(name,kind,Items.ITEM_TABLE[name],self.player)

    def get_filler_item_name(self):
        return self.random.choices(Items.FILLER, weights=tuple(Items.FILLER_WEIGHTS.values()), k=1)[0]

    def fill_slot_data(self):
        return {'schema_version': SCHEMA_VERSION, 'options_revision':7, 'music_mapping_version':2, 'game': GAME, 'seed_name': self.multiworld.seed_name,
                'starting_world': 0, 'game_land_gates': self.gates,
                'game_land_speed_items': self.game_land_speed_items,
                'stage_mapping': self.stage_mapping, 'unknown_logic': list(self.unknown_logic),
                'logic_policy': 'sheet_v2',
                'mandatory_prologue': ['stg110', 'stg130'],
                'locations': {n: Locations.LOCATION_TABLE[n].code for n in self.active_locations},
                'options': self.options.as_dict(*OPTION_NAMES)}

    def generate_output(self, output_directory):
        from .patch import SonicColoursPatch
        path=Path(output_directory)/f'{self.multiworld.get_out_file_name_base(self.player)}.apsoniccolours'
        patch=SonicColoursPatch(str(path),self.player,self.multiworld.get_player_name(self.player),
                               slot_data=self.fill_slot_data())
        patch.write()

    def write_spoiler_header(self, spoiler_handle):
        spoiler_handle.write(f'\nSonic Colours (Wii) PAL\n'
                             'Starting world: Tropical Resort (vanilla intro)\n'
                             f'Unknown logic entries: {len(self.unknown_logic)}\n'
                             'Logic: Sheet V2; undocumented Normal routes require all selected Wisps.\n')
