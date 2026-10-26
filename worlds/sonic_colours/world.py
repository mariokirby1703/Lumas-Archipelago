import json
import hashlib
import logging
from pathlib import Path
from typing import ClassVar
from .settings import SonicColoursSettings

from worlds.AutoWorld import World
from . import Items, Locations, Regions, Rules
from .Options import SonicColoursOptions, OPTION_NAMES
from .web_world import SonicColoursWeb
from .world_constants import GAME, SCHEMA_VERSION, STAGES, WORLDS, load_data, game_land_gates, game_land_reduction_points, pack_rings

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
        if self.options.red_ring_checks.value==0:
            self.options.red_ring_checks.value=1
        if not self.options.game_land_checks:
            self.options.eggman_heart_sanity.value=0
            self.options.chaos_emerald_checks.value=0
        # Both experimental effects are normal, selectable options. Never
        # represent their lack of Dolphin live-verification as success.
        validation=load_data('versions.json').get('live_validation',{})
        for option, capability in [('death_link', 'deathlink'),('dead_weight_trap_weight','dead_weight')]:
            if getattr(self.options, option).value and not validation.get(capability):
                logger.warning('Sonic Colours: %s enabled, but PAL %s live-validation remains incomplete.',
                               option, capability)
        if self.options.native_feature_tests:
            logger.warning('Sonic Colours: unverified native feature TEST opt-in; PAL live matrix incomplete.')
        self.starting_stage = next(s for s in STAGES if s['mission_id'] == 'stg110')
        self.starting_world = 0
        self.gates = game_land_gates(game_land_reduction_points(self.options.game_land_requirement_reduction.value))
        self.active_locations = tuple(n for n, d in Locations.LOCATION_TABLE.items() if Locations.enabled(d, self.options))
        self.logic = load_data('logic_from_sheet_v3.json')
        from .logic import validate_manifest
        validate_manifest(self.logic)
        self.unknown_logic = ()
        logger.info('Sonic Colours: Completed Sheet V3 NL/ML routes (%d), A/S rank Wisps included.',
                    len(self.logic['locations']))
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
        if self.options.movement_unlocks:
            early=self.multiworld.local_early_items[self.player]
            if self.options.red_ring_checks.value==2:
                # Drill and Rail open both intro Acts' five-ring sets.
                for name in ('Progressive Yellow Drill Wisp','Progressive Rail'):
                    if name in names:
                        early[name]=max(early.get(name,0),1)
            elif names.count('Progressive Crouch'):
                early['Progressive Crouch']=max(early.get('Progressive Crouch',0),names.count('Progressive Crouch'))
        needs_land = bool(self.options.game_land_checks)
        self.game_land_speed_items = bool(self.options.game_land_checks.value and self.options.movement_unlocks.value)
        speed_count = max(0, 4 - sum(i.name == Items.GAME_LAND_SPEED for i in precollected)) if self.game_land_speed_items else 0
        self.ring_required = max(self.gates.values()) if needs_land else 0
        self.ring_target = (4 * self.ring_required + 2) // 3
        remaining = max(0, self.ring_target - sum(Items.RING_VALUES.get(i.name, 0) for i in precollected))
        available=len(self.active_locations)-len(self.options.exclude_locations.value & set(self.active_locations))
        def minimum_currency(value):
            count=0
            for amount in (50,20,10,5,1):
                copies,value=divmod(value,amount)
                count+=copies
            return count
        capacity=available-len(names)-speed_count
        # In small check sets, mostly-single currency can occupy almost every
        # ordinary route and leave the abilities needed by Game Land stranded.
        # Bundle currency while retaining the exact target value and reserve
        # ordinary check capacity for the mandatory non-currency progression.
        ordinary=sum(next(s for s in STAGES if s['mission_id']==Locations.LOCATION_TABLE[n].mission)['zone_index']<7
                     for n in self.active_locations if n not in self.options.exclude_locations.value)
        minimum_currency_items=minimum_currency(remaining)
        capacity=min(capacity,max(minimum_currency_items,ordinary-len(names)-speed_count))
        ring_items = [Items.ring_name(n) for n in pack_rings(remaining, capacity)]
        names += ring_items
        # The restrictive filler already prevents item self-locks. Blanket
        # Wisp/world bans in Game Land and Red Ring bans on Clears exhaust
        # reachable slots with the completed per-check spreadsheet requirements.
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

    def pre_fill(self):
        from BaseClasses import LocationProgressType
        for group_id,group in self.multiworld.groups.items():
            members=group['players']
            if not members or self.player!=min(members) or self.player not in members:
                continue
            requests={}
            for player in sorted(members):
                for name,count in self.multiworld.local_early_items[player].items():
                    if name in group['item_pool']:requests[name]=max(requests.get(name,0),count)
            state=self.multiworld.state.copy();state.sweep_for_advancements()
            locations=sorted((loc for player in members for loc in self.multiworld.get_unfilled_locations(player)
                              if loc.progress_type!=LocationProgressType.EXCLUDED and loc.can_reach(state)),
                             key=lambda loc:(loc.player,loc.name))
            self.random.shuffle(locations)
            for name,count in sorted(requests.items()):
                selected=[item for item in self.multiworld.itempool
                          if item.player==group_id and item.name==name][:count]
                placed=0
                for item in selected:
                    location=next((loc for loc in locations if loc.can_fill(state,item,True)),None)
                    if location is None:break
                    location.place_locked_item(item)
                    self.multiworld.itempool.remove(item);locations.remove(location);placed+=1
                for player in members:
                    early=self.multiworld.local_early_items[player]
                    if name in early:
                        remaining=max(0,early[name]-placed)
                        if remaining:early[name]=remaining
                        else:early.pop(name)

    def fill_hook(self,progression,useful,filler,locations):
        from Fill import sweep_from_pool
        from collections import Counter
        owners={self.player}|{gid for gid,group in self.multiworld.groups.items()
                                  if self.player in group['players']}
        state=sweep_from_pool(self.multiworld.state,progression+useful)
        own=[loc for loc in locations if loc.player==self.player]
        total=sum(loc.can_reach(state) for loc in own)
        losses={}
        counts=Counter((item.player,item.name) for item in progression if item.player in owners)
        requirements={loc:0 for loc in own}
        for item in progression:
            key=(item.player,item.name)
            if item.player not in owners or key in losses:
                continue
            if item.player==self.player:
                reduced=state.copy();reduced.remove(item)
            else:
                # Linked receipts unlock events for every member. Rebuild the
                # state so removing a group item also removes those events.
                reduced=sweep_from_pool(self.multiworld.state,[i for i in progression if i is not item]+useful)
            losses[key]=total-sum(loc.can_reach(reduced) for loc in own)
            if item.player==self.player:
                for _ in range(counts[key]-1):reduced.remove(item)
            elif counts[key]>1:
                reduced=sweep_from_pool(self.multiworld.state,
                    [i for i in progression if (i.player,i.name)!=key]+useful)
            for loc in own:
                if not loc.can_reach(reduced):requirements[loc]+=counts[key]
        # Reverse fill uses harder checks first, leaving simple routes for
        # the last abilities even with minimal accessibility.
        positions=[i for i,loc in enumerate(locations) if loc.player==self.player]
        ordered=sorted(own,key=lambda loc:-requirements[loc])
        for i,loc in zip(positions,ordered):locations[i]=loc
        indices=[i for i,item in enumerate(progression) if item.player in owners]
        early_order={'Progressive Crouch':0}
        if self.options.movement_unlocks and self.options.red_ring_checks.value==2:
            # Sweet Mountain provides another check before Slide and Stomp
            # can both be obtained for Tropical Resort Act 3.
            early_order={'Sweet Mountain Shuttle':0,'Progressive Crouch':1}
        ordered=sorted((progression[i] for i in indices),key=lambda item:(
            early_order.get(item.name,2),-losses[item.player,item.name]))
        for i,item in zip(indices,ordered):progression[i]=item

    def create_item(self, name):
        from BaseClasses import ItemClassification
        kind=Items.classification(name)
        if name==Items.RANDOM_CAPSULES:
            kind=(ItemClassification.progression if (self.options.wisp_capsules or
                     (self.options.game_land_checks and self.options.movement_unlocks))
                  else ItemClassification.useful)
        return Items.SonicColoursItem(name,kind,Items.ITEM_TABLE[name],self.player)

    def get_filler_item_name(self):
        return self.random.choices(Items.FILLER, weights=tuple(Items.FILLER_WEIGHTS.values()), k=1)[0]

    def fill_slot_data(self):
        return {'schema_version': SCHEMA_VERSION, 'options_revision':10, 'music_mapping_version':2, 'game': GAME, 'seed_name': self.multiworld.seed_name,
                'music_seed': hashlib.sha256(json.dumps(['sonic-bgm-player-v1',self.multiworld.seed_name,self.player],separators=(',',':')).encode()).hexdigest(),
                'starting_world': 0, 'game_land_gates': self.gates,
                'game_land_speed_items': self.game_land_speed_items,
                'stage_mapping': self.stage_mapping, 'unknown_logic': list(self.unknown_logic),
                'logic_policy': 'sheet_v2',  # Client wire compatibility; rules use Sheet V3.
                'logic_engine_version': 3,
                'mandatory_prologue': ['stg110', 'stg130'],
                'locations': {n: Locations.LOCATION_TABLE[n].code for n in self.active_locations},
                'options': self.options.as_dict(*OPTION_NAMES)}

    def generate_output(self, output_directory):
        from .patch import SonicColoursPatch
        path=Path(output_directory)/f'{self.multiworld.get_out_file_name_base(self.player)}.apsoniccolours'
        patch=SonicColoursPatch(str(path),self.player,self.multiworld.get_player_name(self.player),
                               slot_data=self.fill_slot_data())
        patch.write()

