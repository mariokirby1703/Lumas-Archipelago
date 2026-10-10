"""Stable original Game Land EggmanMedal identities, independent of options."""
import csv
import io
from importlib.resources import files
from .world_constants import BASE_ID, BY_MISSION

MEDALS = tuple(dict(row, index=i, code=BASE_ID + 5000 + i,
                    object_id=int(row['object_id']), instance_index=int(row['instance_index']),
                    position=tuple(float(row[k]) for k in ('x', 'y', 'z')))
               for i, row in enumerate(csv.DictReader(io.StringIO(
                   files(__package__).joinpath('data/egg_medals.csv').read_text(encoding='utf-8')))))
BY_NATIVE_ID = {(r['mission_id'], r['object_id'], r['instance_index']): r for r in MEDALS}
if (len(MEDALS) != 21 or len(BY_NATIVE_ID) != 21
        or {r['mission_id'] for r in MEDALS} != {m for m, s in BY_MISSION.items() if s['zone_index'] >= 7}
        or any(r['object_type'] != 'EggmanMedal' or r['layer'] != '00' for r in MEDALS)):
    raise ValueError('invalid original Egg Medal catalog')
