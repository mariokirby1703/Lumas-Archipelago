"""Canonical instance catalog; an ORC placement alone is not a playable check."""
from dataclasses import dataclass
import json
from .world_constants import BASE_ID, BY_MISSION, WISPS, load_data


def instance_key(row):
    return json.dumps([row['mission_id'], row['orc_file'], row['layer'],
                       str(row['object_id']), int(row['instance'])], separators=(',', ':'))


@dataclass(frozen=True)
class Capsule:
    key: str
    code: int
    mission: str
    name: str
    story: bool
    eligible: bool
    wisp_item: str | None
    exclusion: str | None
    raw_wisp: int = -1
    position: tuple = ()


def build_catalog(rows, validation):
    if validation.get('schema') == 2:
        proof = validation
        validation = {key: {'validated': True, 'wisp_item': item,
                            'native_identity_proof': proof['native_identity_proof'],
                            'accessibility_proof': proof['accessibility_proof']}
                      for key, item in proof['instances'].items()}
    catalog = {}
    ids = set()
    for index, row in enumerate(rows):
        key = instance_key(row)
        if key in catalog:
            raise ValueError('duplicate canonical capsule instance: ' + key)
        stage = BY_MISSION.get(row['mission_id'])
        evidence = validation.get(key, {})
        eligible = evidence.get('validated', False)
        item = evidence.get('wisp_item')
        if eligible and (not stage or item not in {w + ' Wisp' for w in WISPS}
                         or not evidence.get('native_identity_proof') or not evidence.get('accessibility_proof')):
            raise ValueError('capsule validation lacks mapping, confirmed subtype or proof: ' + key)
        code = BASE_ID + 10000 + index
        assert code not in ids
        ids.add(code)
        name = (f"{stage['name']} - Wisp Capsule {row['object_id']} "
                f"[Layer {row['layer']}, Instance {row['instance']}]" if stage else '')
        catalog[key] = Capsule(key, code, row['mission_id'], name, bool(stage and stage['zone_index'] < 7),
                               eligible, item, None if eligible else
                               'mission_unmapped' if not stage else 'native_identity_and_accessibility_unverified',
                               int(row['wisp_code']), tuple(float(row[axis]) for axis in ('x', 'y', 'z')))
    if set(validation) - catalog.keys():
        raise ValueError('capsule validation references unknown instance keys')
    return catalog


CAPSULES = build_catalog(load_data('wisp_capsules.json'), load_data('capsule_validation.json'))
CAPSULES_BY_NATIVE_ID = {(capsule.mission, int(json.loads(capsule.key)[3]), int(json.loads(capsule.key)[4])): capsule
                       for capsule in CAPSULES.values() if capsule.name}
if len(CAPSULES_BY_NATIVE_ID) != sum(bool(capsule.name) for capsule in CAPSULES.values()):
    raise ValueError('ambiguous capsule native ID across ORC layers')
