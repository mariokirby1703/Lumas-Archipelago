"""Experimental LCU APWorld, with guarded native item delivery and area passes."""
import json
import logging
import pkgutil
from pathlib import Path
from BaseClasses import Item, ItemClassification, Location, Region, Tutorial
from worlds.AutoWorld import World, WebWorld
from .options import LCUOptions, enabled_categories
from .bridge.opening_logic import NO_POLICE_KEYS, POLICE_ITEMS, has_police
from .bridge.capabilities import pool_candidates, PROGRESSIVE_ASTRONAUT
from .bridge.progressive_items import PROGRESSIVE_FAMILIES
from .bridge.location_design import enrich_catalogue

CATALOGUE = json.loads(pkgutil.get_data(__name__, 'catalogue.json'))
enrich_catalogue(CATALOGUE)
TOKEN = 'City Completion Token'
TOKEN_ID = 2_999_999_999


class LCUWeb(WebWorld):
    tutorials = [Tutorial('Experimental setup',
                          'Install and test the experimental LCU integration.',
                          'English', 'setup_en.md', 'setup/en', ['Luma'])]


class LCUItem(Item):
    game = 'LEGO City Undercover'


class LCULocation(Location):
    game = 'LEGO City Undercover'


class LCUWorld(World):
    """Source-backed, incomplete city logic with carefully labelled native limits."""
    game = 'LEGO City Undercover'
    options_dataclass = LCUOptions
    web = LCUWeb()
    options: LCUOptions
    topology_present = True
    item_name_to_id = {**{n: r['id'] for n, r in CATALOGUE['items'].items()}, TOKEN: TOKEN_ID}
    location_name_to_id = {r['name']: r['id'] for r in CATALOGUE['locations'].values()}

    def generate_early(self):
        if (self.options.separate_class_unlocks.value and self.options.ability_items.value
                and not self.options.character_items.value):
            raise ValueError('LCU: separate_class_unlocks requires character_items when ability_items is enabled; otherwise vanilla class skins bypass the class lock')
        categories = enabled_categories(self.options)
        if self.options.area_pass_items.value and not self.options.experimental_area_restrictions.value:
            raise ValueError('LCU: area passes require experimental_area_restrictions; distant travel/reload remains unsupported')
        if self.options.area_pass_items.value and self.options.story_mode.value != 0:
            raise ValueError('LCU: native area rollback currently requires linear story mode; open_world has no safe native save bootstrap')
        if not self.options.experimental_items.value and self.options.story_access_items.value:
            raise ValueError('LCU: story tickets lack safe native entrance gates; enable experimental_items only for symbolic research seeds')
        self.active_catalogue = {
            k: r for k, r in CATALOGUE['locations'].items()
            if (r['category'] in categories and not r.get('legacy_aggregate')
                and not r.get('legacy_non_assignment_hub')
                and not r.get('token_relationship', {}).get('exclude_from_new_generation'))
        }
        self.active_catalogue = dict(sorted(self.active_catalogue.items(),
            key=lambda pair: (pair[1].get('design_order', 1_000_000), pair[0])))
        if self.options.goal.value == 2 and len(self.active_catalogue) < self.options.goal_tokens.value:
            raise ValueError('LCU: selected location count is below goal_tokens')
        if self.options.story_mode.value == 0:
            for option, name in self._early_tools():
                if name in self.options.non_local_items.value:
                    raise ValueError(f'LCU {option} needs a local {name.removeprefix("Ability: ")}; remove it from non_local_items')
                self.multiworld.local_early_items[self.player][name] = 1
        logging.warning('LCU experimental: incomplete traversal; area rollback is opt-in and near-boundary only; story gates and open-world setup are unavailable.')

    def create_regions(self):
        from .regions import create_regions
        create_regions(self, LCULocation, LCUItem)

    def create_item(self, name):
        classification = (
            ItemClassification.progression
            if name == TOKEN or CATALOGUE['items'][name]['classification'] == 'progression'
            else (ItemClassification.useful
                  if CATALOGUE['items'][name]['classification'] == 'useful'
                  else ItemClassification.filler)
        )
        return LCUItem(name, classification, self.item_name_to_id[name], self.player)

    def get_filler_item_name(self):
        return 'Studs 1,000'

    def _early_scans(self):
        scans = []
        if self.options.early_criminal_scan.value:
            scans.append(('early_criminal_scan', 'Ability: Criminal Scan'))
        if self.options.detective_scan_lock.value and (self.options.early_detective_scan.value or
                (self.options.story_mode.value==0 and self.options.ability_items.value)):
            scans.append(('early_detective_scan', 'Ability: Detective Scan'))
        return scans

    def _early_tools(self):
        tools=self._early_scans()
        if self.options.story_mode.value==0 and self.options.ability_items.value:
            tools.append(('mandatory_tutorial_superbuild','Ability: SuperBuild'))
        return tools

    def pre_fill(self):
        self.early_police_location = None
        if self.options.area_pass_items.value:
            from .bridge.area_passes import FIRST_PASS_KEYS
            name = 'Area Pass: SF_Residential'
            if not any(item.name == name for item in self.multiworld.precollected_items[self.player]):
                if name in self.options.non_local_items.value:
                    raise ValueError('First Cherry Tree Hills pass must be local')
                item = next((i for i in self.multiworld.itempool
                             if i.name == name and i.player == self.player), None)
                if item is None:
                    raise ValueError('LCU: Cherry Tree Hills area pass is not in the item pool')
                choices = [self.multiworld.get_location(row['name'], self.player)
                           for key, row in self.active_catalogue.items()
                           if key in FIRST_PASS_KEYS
                           and row['name'] not in self.options.exclude_locations.value]
                choices = [loc for loc in choices if loc.item is None
                           and loc.can_fill(self.multiworld.state, item)]
                if not choices:
                    raise ValueError('No reachable Auburn opening check for Cherry Tree Hills pass')
                self.random.choice(choices).place_locked_item(item)
                self.multiworld.itempool.remove(item)
        if self.options.story_mode.value != 0:
            return
        owned = {item.name for item in self.multiworld.precollected_items[self.player]}
        if 'Ability: Scanner' in owned:owned.add('Ability: Criminal Scan')
        early_scans = [(option, name) for option, name in self._early_tools() if name not in owned]
        for option, scanner in self._early_tools():
            if scanner in owned:
                self.multiworld.local_early_items[self.player].pop(scanner, None)
            else:
                if scanner in self.options.non_local_items.value:
                    raise ValueError(f'LCU {option} needs a local {scanner}; remove it from non_local_items')
                items = [item for item in self.multiworld.itempool
                         if item.player == self.player and item.name == scanner]
                if not items:
                    raise ValueError(f'LCU {option} requires ability_items or a starting {scanner}')
                available = [self.multiworld.get_location(row['name'], self.player)
                             for key, row in self.active_catalogue.items()
                             if self._opening_key(key, row)
                             and row['name'] not in self.options.exclude_locations.value]
                available = [loc for loc in available if loc.item is None
                             and loc.can_fill(self.multiworld.state, items[0], check_access=False)]
                needed = len(early_scans) + (0 if owned.intersection(POLICE_ITEMS) else 1)
                if len(available) < needed:
                    raise ValueError('LCU early scans need enough enabled opening checks for both Police and Criminal Scan / Detective Scan')
        for _, scanner in early_scans:
            item = next(item for item in self.multiworld.itempool
                        if item.player == self.player and item.name == scanner)
            available = [self.multiworld.get_location(row['name'], self.player)
                         for key, row in self.active_catalogue.items()
                         if self._opening_key(key, row)
                         and row['name'] not in self.options.exclude_locations.value]
            available = [loc for loc in available if loc.item is None
                         and loc.can_fill(self.multiworld.state, item, check_access=False)]
            self.random.choice(available).place_locked_item(item)
            self.multiworld.itempool.remove(item)
            self.multiworld.local_early_items[self.player].pop(scanner, None)
        if any(item.name in POLICE_ITEMS
               for item in self.multiworld.precollected_items[self.player]):
            return
        items = [item for item in self.multiworld.itempool
                 if item.player == self.player and item.name in POLICE_ITEMS]
        if not items:
            raise ValueError('LCU linear story requires Police: enable ability_items or character_items, or start with Police')
        candidates = [item for item in items if item.name not in self.options.non_local_items.value]
        if not candidates:
            raise ValueError('LCU linear story needs a local opening Police item; remove Police from non_local_items')
        item = next((item for item in candidates if item.name == 'Ability: Police'), candidates[0])
        excluded = self.options.exclude_locations.value
        locations = [self.multiworld.get_location(row['name'], self.player)
                     for key, row in self.active_catalogue.items()
                     if self._opening_key(key, row) and row['name'] not in excluded]
        locations = [loc for loc in locations if loc.item is None
                     and loc.can_fill(self.multiworld.state, item, check_access=False)]
        if not locations:
            raise ValueError('LCU linear story has no enabled opening location for Police; enable opening checks or remove their exclusions')
        location = self.random.choice(locations)
        location.place_locked_item(item)
        self.multiworld.itempool.remove(item)
        self.early_police_location = location.name

    def _opening_key(self, key, row):
        if key not in NO_POLICE_KEYS:
            return False
        if not self.options.area_pass_items.value:
            return True
        # With area passes, ALL locked Cherry / police_station locations must
        # be kept out of the initial local placement pool, even when they were
        # once observed before Police in a vanilla, non-area-gated save.
        from .bridge.area_passes import auburn_opening_key
        return auburn_opening_key(key, row)

    def create_items(self):
        allowed = {
            'character': self.options.character_items.value,
            'vehicle': self.options.vehicle_items.value,
            'ability': self.options.ability_items.value,
            'area_pass': self.options.area_pass_items.value,
            'story_access': self.options.story_access_items.value,
            'cheat': self.options.cheat_items.value,
        }
        names = [TOKEN] * self.options.goal_tokens.value if self.options.goal.value == 2 else []
        progressive_options={family:bool(getattr(self.options,'progressive_'+family.removeprefix('Progressive ').lower()).value)
                             for family in PROGRESSIVE_FAMILIES}
        candidates = pool_candidates(CATALOGUE['items'], allowed,
                                     self.options.experimental_items.value,
                                     self.options.progressive_astronaut.value,progressive_options)
        if self.options.area_pass_items.value:
            candidates.extend(name for name, row in CATALOGUE['items'].items()
                if row['category'] == 'area_pass'
                and name == 'Area Pass: ' + row.get('native_name', '')
                and row.get('native_name') != 'SF_Docks'
                and name not in candidates)
        for family in PROGRESSIVE_FAMILIES:
            if family in candidates:candidates.append(family)
        if not self.options.detective_scan_lock.value:
            candidates = [n for n in candidates if n != 'Ability: Detective Scan']
        candidates += ['Super Bricks 1,000'] * self.options.super_brick_1000_count.value
        candidates += ['Super Bricks 10,000'] * self.options.super_brick_10000_count.value
        required = [n for n in candidates if CATALOGUE['items'][n]['classification'] == 'progression']
        candidates = [n for n in candidates if CATALOGUE['items'][n]['classification'] != 'progression']
        self.random.shuffle(candidates)
        count = len(self.active_catalogue)
        if len(names) + len(required) > count:
            raise ValueError('LCU: too few locations for required progression items')
        names += required
        names += candidates[:count - len(names)]
        names += self.random.choices(
            ['Studs 1,000', 'Studs 10,000', 'Studs 100,000', 'Super Bricks 100', 'Super Bricks 250'],
            weights=[80, 18, 1, 30, 15], k=count - len(names))
        self.multiworld.itempool.extend(self.create_item(n) for n in names)

    def fill_slot_data(self):
        return dict(
            version=1, experimental=True, goal_tokens=self.options.goal_tokens.value,
            options={k: getattr(self.options, k).value
                     for k in self.options.__dataclass_fields__ if k in LCUOptions.__annotations__},
            locations={str(r['id']): dict(
                key=k, name=r['name'], runtime=r['runtime'], status=r['status'],
                display_name=r.get('display_name'), display_area=r.get('display_area'),
                district=r.get('district'), category=r['category'],
                source_type_code=r.get('source_type_code'),
                superbrick_size=r.get('superbrick_size'))
                for k, r in self.active_catalogue.items()},
            opening_logic=dict(partial=True, early_police_location=getattr(self, 'early_police_location', None),
                               no_police_keys=sorted(k for k in self.active_catalogue
                                                     if k in NO_POLICE_KEYS)),
            logic_coverage=dict(version=3, source_requirements=True,
                                assignment_sequence=True, city_traversal_complete=False,
                                auburn_start_always_open=True,
                                police_station_requires_cherry_pass=bool(self.options.area_pass_items.value)),
            native_grants=True, native_locks=False, native_open_world_setup=False,
            native_area_rollback=bool(self.options.area_pass_items.value
                                      and self.options.experimental_area_restrictions.value),
            native_detective_scan_lock=bool(self.options.detective_scan_lock.value
                                             and self.options.ability_items.value),
            native_reward_suppression='poll_after_checks',
            native_save_verification='model_ability_cheat_and_currency_marker',
            item_effects={str(r['id']): dict(name=n, **r)
                          for n, r in CATALOGUE['items'].items()},
            received_items_require_manual_testing=True,
        )
