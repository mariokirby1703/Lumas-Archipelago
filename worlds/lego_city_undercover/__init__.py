"""Experimental LCU generation world. Native item grants/gates remain unimplemented."""
import json
import logging
import pkgutil
from pathlib import Path
from BaseClasses import Item, ItemClassification, Location, Region
from worlds.AutoWorld import World
from .options import LCUOptions, enabled_categories

CATALOGUE=json.loads(pkgutil.get_data(__name__,'catalogue.json'))
TOKEN='City Completion Token'
TOKEN_ID=2_999_999_999


class LCUItem(Item):
    game='LEGO City Undercover'


class LCULocation(Location):
    game='LEGO City Undercover'


class LCUWorld(World):
    """Experimental catalog-based manual/read-only testing. No native randomization yet."""
    game='LEGO City Undercover'
    options_dataclass=LCUOptions
    options: LCUOptions
    topology_present=False
    item_name_to_id={**{n:r['id'] for n,r in CATALOGUE['items'].items()},TOKEN:TOKEN_ID}
    location_name_to_id={r['name']:r['id'] for r in CATALOGUE['locations'].values()}

    def generate_early(self):
        categories=enabled_categories(self.options)
        self.active_catalogue={k:r for k,r in CATALOGUE['locations'].items() if r['category'] in categories}
        if len(self.active_catalogue)<self.options.goal_tokens.value:
            raise ValueError('LCU: selected location count is below goal_tokens')
        logging.warning('LCU experimental: native grants, reward suppression, story/area locks and open-world setup are NOT implemented.')

    def create_regions(self):
        menu=Region('Menu',self.player,self.multiworld)
        city=Region('Experimental checks',self.player,self.multiworld)
        self.multiworld.regions.extend((menu,city));menu.connect(city)
        city.locations.extend(LCULocation(self.player,r['name'],r['id'],city) for r in self.active_catalogue.values())
        self.multiworld.completion_condition[self.player]=lambda state:state.has(TOKEN,self.player,self.options.goal_tokens.value)

    def create_item(self,name):
        classification=ItemClassification.progression if name==TOKEN else (
            ItemClassification.useful if CATALOGUE['items'][name]['classification']=='useful' else ItemClassification.filler)
        return LCUItem(name,classification,self.item_name_to_id[name],self.player)

    def get_filler_item_name(self):return 'Studs 1,000'

    def create_items(self):
        allowed={'character':self.options.character_items.value,'vehicle':self.options.vehicle_items.value,
                 'ability':self.options.ability_items.value,'area_pass':self.options.area_pass_items.value,
                 'story_access':self.options.story_access_items.value}
        names=[TOKEN]*self.options.goal_tokens.value
        candidates=[n for n,r in CATALOGUE['items'].items() if allowed.get(r['category'],False)]
        self.random.shuffle(candidates)
        count=len(self.active_catalogue)
        names+=candidates[:count-len(names)]
        names+=['Studs 1,000']*(count-len(names))
        self.multiworld.itempool.extend(self.create_item(n) for n in names)

    def fill_slot_data(self):
        return dict(version=1,experimental=True,goal_tokens=self.options.goal_tokens.value,
                    options={k:getattr(self.options,k).value for k in self.options.__dataclass_fields__
                             if k in LCUOptions.__annotations__},
                    locations={str(r['id']):dict(key=k,name=r['name'],runtime=r['runtime'],status=r['status'])
                               for k,r in self.active_catalogue.items()},
                    native_grants=False,native_locks=False,native_open_world_setup=False,
                    received_items_require_manual_testing=True)
