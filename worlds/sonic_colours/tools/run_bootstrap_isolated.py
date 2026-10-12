"""Only for offline CI where the full Archipelago installation is unavailable."""
import sys,types,importlib.util,pathlib,json
root=pathlib.Path(__file__).resolve().parents[1]
for name,pth in [('sonic_colours',root),('sonic_colours.client',root/'client'),('sonic_colours.test',root/'test')]:
 m=types.ModuleType(name);m.__path__=[str(pth)];m.__spec__=importlib.util.spec_from_loader(name,loader=None,is_package=True);sys.modules[name]=m
world=types.ModuleType('sonic_colours.world_constants')
world.load_data=lambda name:json.loads((root/'data'/name).read_text())
world.STAGES=world.load_data('stage_map.json')
world.STARTING_STAGES=tuple(s for s in world.STAGES if s['normal'] or (s['zone_index']<6 and s['mission_id']!='stg790'))
world.NATIVE_COLOURS=('Yellow Drill','Cyan Laser','Pink Spikes','Orange Rocket','Purple Frenzy','Blue Cube','Green Hover')
world.WISPS=('White Boost','Cyan Laser','Yellow Drill','Orange Rocket','Blue Cube','Green Hover','Pink Spikes','Purple Frenzy')
sys.modules['sonic_colours.world_constants']=world
from sonic_colours.client import native_read
# Normal native imports are pure; imports of test-world modules are avoided.
from sonic_colours.client import hooks
import pytest
sys.exit(pytest.main(['-v',*(sys.argv[1:] or [str(root/'test'/'test_new_game_no_slot.py')])]))
