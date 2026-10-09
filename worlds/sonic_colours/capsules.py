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


def build_catalog(rows, validation):
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
        if eligible and (not stage or item not in {w + ' Unlock' for w in WISPS}
                         or not evidence.get('native_identity_proof') or not evidence.get('accessibility_proof')):
            raise ValueError('capsule validation lacks mapping, confirmed subtype or proof: ' + key)
        code = BASE_ID + 10000 + index
        assert code not in ids
        ids.add(code)
        name = (f"{stage['name']} - Wisp Capsule {row['object_id']} "
                f"[Layer {row['layer']}, Instance {row['instance']}]" if stage else '')
        catalog[key] = Capsule(key, code, row['mission_id'], name, bool(stage and stage['zone_index'] < 7),
                               eligible, item, None if eligible else
                               'mission_unmapped' if not stage else 'native_identity_and_accessibility_unverified')
    if set(validation) - catalog.keys():
        raise ValueError('capsule validation references unknown instance keys')
    return catalog


CAPSULES = build_catalog(load_data('wisp_capsules.json'), load_data('capsule_validation.json'))
