"""Experimental LCU generation world with an opt-in native delivery client."""
import json
import logging
import pkgutil
from pathlib import Path
from BaseClasses import Item, ItemClassification, Location, Region, Tutorial
from worlds.AutoWorld import World, WebWorld
from .options import LCUOptions, enabled_categories
from .bridge.opening_logic import NO_POLICE_KEYS,POLICE_ITEMS,has_police

CATALOGUE=json.loads(pkgutil.get_data(__name__,'catalogue.json'))
TOKEN='City Completion Token'
TOKEN_ID=2_999_999_999


class LCUWeb(WebWorld):
    tutorials=[Tutorial('Experimental setup','Install and test the experimental LCU integration.',
                        'English','setup_en.md','setup/en',['Luma'])]


class LCUItem(Item):
    game='LEGO City Undercover'


class LCULocation(Location):
    game='LEGO City Undercover'


class LCUWorld(World):
    """Experimental catalogue generation; story access logic remains incomplete."""
    game='LEGO City Undercover'
    options_dataclass=LCUOptions
    web=LCUWeb()
    options: LCUOptions
    topology_present=False
    item_name_to_id={**{n:r['id'] for n,r in CATALOGUE['items'].items()},TOKEN:TOKEN_ID}
    location_name_to_id={r['name']:r['id'] for r in CATALOGUE['locations'].values()}

    def generate_early(self):
        categories=enabled_categories(self.options)
        self.active_catalogue={k:r for k,r in CATALOGUE['locations'].items() if r['category'] in categories}
        if len(self.active_catalogue)<self.options.goal_tokens.value:
            raise ValueError('LCU: selected location count is below goal_tokens')
        logging.warning('LCU experimental: native delivery requires opt-in; story/area entrance locks and open-world setup remain unavailable.')

    def create_regions(self):
        menu=Region('Menu',self.player,self.multiworld)
        city=Region('Experimental checks',self.player,self.multiworld)
        self.multiworld.regions.extend((menu,city))
        linear=self.options.story_mode.value==0
        opening=Region('Opening before Police',self.player,self.multiworld) if linear else city
        if linear:
            self.multiworld.regions.append(opening);menu.connect(opening)
            opening.connect(city,rule=lambda state:has_police(state,self.player))
        else:menu.connect(city)
        for key,row in self.active_catalogue.items():
            parent=opening if linear and key in NO_POLICE_KEYS else city
            parent.locations.append(LCULocation(self.player,row['name'],row['id'],parent))
        self.multiworld.completion_condition[self.player]=lambda state:state.has(TOKEN,self.player,self.options.goal_tokens.value)

    def create_item(self,name):
        classification=ItemClassification.progression if name==TOKEN or CATALOGUE['items'][name]['classification']=='progression' else (
            ItemClassification.useful if CATALOGUE['items'][name]['classification']=='useful' else ItemClassification.filler)
        return LCUItem(name,classification,self.item_name_to_id[name],self.player)

    def get_filler_item_name(self):return 'Studs 1,000'

    def pre_fill(self):
        self.early_police_location=None
        if self.options.story_mode.value!=0:return
        # Start-inventory Police already satisfies the opening requirement.
        if any(item.name in POLICE_ITEMS for item in self.multiworld.precollected_items[self.player]):return
        items=[item for item in self.multiworld.itempool if item.player==self.player and item.name in POLICE_ITEMS]
        if not items:
            raise ValueError('LCU linear story requires Police: enable ability_items or character_items, or start with Police')
        candidates=[item for item in items if item.name not in self.options.non_local_items.value]
        if not candidates:
            raise ValueError('LCU linear story needs a local opening Police item; remove Police from non_local_items')
        item=next((item for item in candidates if item.name=='Ability: Police'),candidates[0])
        excluded=self.options.exclude_locations.value
        locations=[self.multiworld.get_location(row['name'],self.player)
                   for key,row in self.active_catalogue.items() if key in NO_POLICE_KEYS and row['name'] not in excluded]
        locations=[loc for loc in locations if loc.item is None and loc.can_fill(self.multiworld.state,item,check_access=False)]
        if not locations:
            raise ValueError('LCU linear story has no enabled opening location for Police; enable opening checks or remove their exclusions')
        location=self.random.choice(locations)
        location.place_locked_item(item);self.multiworld.itempool.remove(item)
        self.early_police_location=location.name

    def create_items(self):
        allowed={'character':self.options.character_items.value,'vehicle':self.options.vehicle_items.value,
                 'ability':self.options.ability_items.value,'area_pass':self.options.area_pass_items.value,
                 'story_access':self.options.story_access_items.value,'cheat':self.options.cheat_items.value}
        names=[TOKEN]*self.options.goal_tokens.value
        candidates=[n for n,r in CATALOGUE['items'].items() if allowed.get(r['category'],False)]
        candidates+=['Super Bricks 1,000']*self.options.super_brick_1000_count.value
        candidates+=['Super Bricks 10,000']*self.options.super_brick_10000_count.value
        required=[n for n in candidates if CATALOGUE['items'][n]['classification']=='progression']
        candidates=[n for n in candidates if CATALOGUE['items'][n]['classification']!='progression']
        self.random.shuffle(candidates)
        count=len(self.active_catalogue)
        if len(names)+len(required)>count:raise ValueError('LCU: too few locations for required progression items')
        names+=required
        names+=candidates[:count-len(names)]
        names+=self.random.choices(['Studs 1,000','Studs 10,000','Studs 100,000','Super Bricks 100','Super Bricks 250'],
            weights=[80,18,1,30,15],k=count-len(names))
        self.multiworld.itempool.extend(self.create_item(n) for n in names)

    def fill_slot_data(self):
        return dict(version=1,experimental=True,goal_tokens=self.options.goal_tokens.value,
                    options={k:getattr(self.options,k).value for k in self.options.__dataclass_fields__
                             if k in LCUOptions.__annotations__},
                    locations={str(r['id']):dict(key=k,name=r['name'],runtime=r['runtime'],status=r['status'])
                               for k,r in self.active_catalogue.items()},
                    opening_logic=dict(partial=True,early_police_location=getattr(self,'early_police_location',None),
                        no_police_keys=sorted(k for k in self.active_catalogue if k in NO_POLICE_KEYS)),
                    native_grants=True,native_locks=False,native_open_world_setup=False,
                    native_reward_suppression='poll_after_checks',native_save_verification='model_ability_cheat_and_currency_marker',
                    item_effects={str(r['id']):dict(name=n,**r) for n,r in CATALOGUE['items'].items()},
                    received_items_require_manual_testing=True)
