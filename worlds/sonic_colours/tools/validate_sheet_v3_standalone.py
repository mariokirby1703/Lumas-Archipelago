import json,sys,types,collections,importlib.util
from pathlib import Path
from types import SimpleNamespace
root=Path(__file__).resolve().parents[1]
manifest=json.loads((root/'data/logic_from_sheet_v3.json').read_text())
v2=json.loads((root/'data/logic_from_sheet_v2.json').read_text())
# Fakes only package import wiring and world inventory; the actual logic.py and
# actual wisps.py are executed, not copied or approximated.
package=types.ModuleType('sonic_colours');package.__path__=[str(root)];sys.modules['sonic_colours']=package
con=types.ModuleType('sonic_colours.world_constants');con.WISPS=('White Boost','Cyan Laser','Yellow Drill','Orange Rocket','Blue Cube','Green Hover','Pink Spikes','Purple Frenzy');con.wisp_item=lambda c, movement_unlocks=True: ('Progressive ' if movement_unlocks and c in ('Yellow Drill','Green Hover','Pink Spikes') else '') + c + ' Wisp';con.STAGES=json.loads((root/'data/stage_map.json').read_text());sys.modules[con.__name__]=con
items=types.ModuleType('sonic_colours.Items');items.ALL_WISP_ITEMS=tuple(con.wisp_item(c,True) for c in con.WISPS) + tuple(con.wisp_item(c,False) for c in ('Yellow Drill','Green Hover','Pink Spikes'));items.RANDOM_CAPSULES='Random Capsules';sys.modules[items.__name__]=items
loc=types.ModuleType('sonic_colours.Locations');loc.LOCATION_TABLE={}
for key in v2['locations']:
 mission, *postfix=key.split(':');type_='clear';idx=0
 if postfix:
  type_={'ring':'ring','one_up':'one_up','eggman_heart':'medal'}[postfix[0]]
  idx=int(postfix[1]) if type_=='ring' else 0
 loc.LOCATION_TABLE[key]=SimpleNamespace(kind=type_,mission=mission,index=idx)
sys.modules[loc.__name__]=loc
from sonic_colours import logic as logic, wisps
assert logic.validate_manifest(manifest) is manifest
assert len(manifest['locations'])==298
assert not manifest['unresolved_routes']
class State:
 def __init__(self,*itemlist):self.items=collections.Counter(itemlist)
 def has(self,name,player,count=1):return self.items[name]>=count
 def count(self,name,player):return self.items[name]

def world(*,move=True,boost=True,land=True):return SimpleNamespace(player=1,options=SimpleNamespace(movement_unlocks=move,boost_lock=boost,game_land_checks=land))
def owned(*names):return State(*names)
def add(s,*names):s.items.update(names);return s
m=world()
base=['White Boost Wisp','Cyan Laser Wisp','Progressive Yellow Drill Wisp','Progressive Crouch','Progressive Crouch','Stomp']
assert not logic.check(m,owned(*base[:-1]),manifest,'stg510:ring:4')
assert logic.check(m,owned(*base),manifest,'stg510:ring:4')
for inventory in (
 ['Progressive Breathing','Swim','Cyan Laser Wisp','Progressive Crouch','Progressive Crouch','Stomp'],
 ['Progressive Breathing','Progressive Yellow Drill Wisp','Cyan Laser Wisp','Progressive Crouch','Progressive Crouch'],
 ['Progressive Breathing','Progressive Breathing','Swim','Cyan Laser Wisp','Progressive Crouch','Progressive Crouch'],
):assert logic.check(m,owned(*inventory),manifest,'stg510:ring:4'),inventory
assert not logic.check(m,owned('Progressive Breathing','Progressive Yellow Drill Wisp','Progressive Crouch','Progressive Crouch'),manifest,'stg510:ring:4')
# Both 7-3 routes explicitly require Random Capsules.
for key in ('stgC10','stgC10:eggman_heart'):
 a=['Progressive Breathing','Progressive Yellow Drill Wisp'];b=['Progressive Breathing']*3+['Orange Rocket Wisp']
 assert not logic.check(m,owned(*a),manifest,key)
 assert not logic.check(m,owned(*b),manifest,key)
 assert logic.check(m,owned(*a,'Random Capsules'),manifest,key)
 assert logic.check(m,owned(*b,'Random Capsules'),manifest,key)
# A/S rank requires all stage Wisps independently of NL/ML stage-clear routes.
assert logic.check(world(move=False),owned(),manifest,'stg110')
assert not logic.check(world(move=False),owned(),manifest,'stg110','A')
assert logic.check(world(move=False),owned('White Boost Wisp','Cyan Laser Wisp','Yellow Drill Wisp'),manifest,'stg110','A')
assert logic.check(world(move=False),owned('White Boost Wisp','Cyan Laser Wisp','Yellow Drill Wisp'),manifest,'stg110','S')
assert not logic.check(world(move=False),owned(),manifest,'stg110','S')
assert logic.check(world(move=False),owned(),manifest,'stg110','B')
assert logic.check(world(move=False),owned(),manifest,'stg110','C')
assert not logic.check(m,owned('White Boost Wisp','Cyan Laser Wisp','Progressive Yellow Drill Wisp'),manifest,'stg340','S')
assert logic.check(m,owned('Stomp'),manifest,'stg340','S')
assert not logic.check(m,owned('Cyan Laser Wisp','Homing Attack'),manifest,'stg390','S')
# Important option check: no White Boost required when Boost Lock is off.
assert logic.available(world(boost=False),State(),'boost')
assert not logic.available(world(boost=True),State(),'boost')
assert logic.available(world(boost=True),owned('White Boost Wisp'),'boost')
assert logic.available(world(move=False),owned('Yellow Drill Wisp'),'drill:2')
assert not logic.available(m,owned('Progressive Yellow Drill Wisp'),'drill:2')
assert logic.available(m,owned('Progressive Yellow Drill Wisp','Progressive Yellow Drill Wisp'),'drill:2')
assert logic.available(m,owned('Progressive Game Land Speed'),'land_speed')
assert not logic.available(m,State(),'land_speed')
assert logic.available(world(move=False),State(),'land_speed')
# Full legal inventory reaches every main route, in NL and ML, for every check.
for movement in (False,True):
 for boost in (False,True):
  w=world(move=movement,boost=boost)
  full=State(*(['White Boost Wisp','Cyan Laser Wisp','Orange Rocket Wisp','Blue Cube Wisp','Purple Frenzy Wisp']+['Progressive Yellow Drill Wisp','Progressive Green Hover Wisp','Progressive Pink Spikes Wisp']*2 + ['Yellow Drill Wisp','Green Hover Wisp','Pink Spikes Wisp'] + list(logic.MOVEMENTS.values())*5 + ['Progressive Game Land Speed']*4 + ['Random Capsules']))
  for key in manifest['locations']:
   assert logic.check(w,full,manifest,key),('unreachable',key,movement,boost)
  for mission in manifest['rank_wisps']:
   for rank in ('A','S'):
    assert logic.check(w,full,manifest,mission,rank),(mission,rank,movement,boost)
print('PASS: 298 NL/ML checks x 4 option modes; all A/S rank stage wisps; 4 Aquarium paths; 2 Game Land 7-3 paths; boost/speed/progression tiers.')
