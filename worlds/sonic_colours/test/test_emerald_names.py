import hashlib
import json
import pytest
from ..Locations import LOCATION_TABLE
from ..world_constants import BASE_ID,STAGES,GAME_LAND_EMERALD_COLOURS
from ..client.runtime import validate_slot
from ..client.client import slot_identity_digest
from . import generate


def test_emerald_locations_use_colour_names_with_unchanged_missions_and_ids():
    names={n for n,d in LOCATION_TABLE.items() if d.kind=='emerald'}
    assert names=={c+' Chaos Emerald' for c in GAME_LAND_EMERALD_COLOURS}
    for index,stage in enumerate(STAGES):
        if stage['zone_index']<7 or stage['slot']!=3:continue
        group=stage['zone_index']-6
        data=LOCATION_TABLE[GAME_LAND_EMERALD_COLOURS[group-1]+' Chaos Emerald']
        assert (data.code,data.mission,data.index)==(BASE_ID+1000+index*32+16,stage['mission_id'],group)


def test_old_emerald_names_normalize_without_changing_journal_identity():
    slot=generate({'game_land_checks':True,'chaos_emerald_checks':True}).worlds[1].fill_slot_data()
    old_names={n:f'Game Land {d.index} - Chaos Emerald Obtained' for n,d in LOCATION_TABLE.items() if d.kind=='emerald'}
    old={**slot,'locations':{old_names.get(n,n):code for n,code in slot['locations'].items()}}
    normalized=validate_slot(old)
    assert normalized['locations']==slot['locations']
    assert slot_identity_digest(normalized)==hashlib.sha256(json.dumps(old,sort_keys=True).encode()).hexdigest()
    assert validate_slot(normalized)==normalized
    assert slot_identity_digest(validate_slot(normalized))==slot_identity_digest(normalized)
    duplicate={**old,'locations':{**old['locations'],'Green Chaos Emerald':LOCATION_TABLE['Green Chaos Emerald'].code}}
    with pytest.raises(ValueError,match='duplicate location aliases'):validate_slot(duplicate)
