"""Keep cosmetic ownership from bypassing an independently randomized class."""
import json
import pkgutil
from pathlib import Path
try:
    from .capabilities import class_for_skin,entitled_classes
except ImportError:
    from capabilities import class_for_skin,entitled_classes

_raw=pkgutil.get_data(__package__,'collection_manifest.json') if __package__ else Path(__file__).with_name('collection_manifest.json').read_bytes()
ROSTER=json.loads(_raw)
TOOL_CLASSES={'Scanner':'Police','DetectiveScan':'Police','Wiretap':'Police','Surveillance':'Police',
              'GrappleGun':'Police','EnergyGun':'Robber','FireAxe':'Firefighter','Jetpack':'Astronaut'}


def tool_class_ready(plan,received,options):
    if not options.get('class_tool_prerequisites',False):return True
    requirement=TOOL_CLASSES.get(plan.get('ability'))
    return requirement is None or requirement in entitled_classes(received)


def model_class_ready(native_name,received,options):
    if not options.get('separate_class_unlocks',False):return True
    requirement=class_for_skin(dict(category='character',native_name=native_name),ROSTER)
    return requirement is None or requirement in entitled_classes(received)
