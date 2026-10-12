import pytest
from ..client.native_read import classify_playable_entry


def entry(state=97):
    return {'scene':'unclassified','state_handler':0x8001CDB4,'current_handler':0x800200CC,
            'player':{'mode':0,'movement':{'controller_vtable':'0x8075FA3C',
                'state_machine_vtable':'0x8075A0F8','current_id':state,'state_fields_plausible':True}}}


@pytest.mark.parametrize('state',[2,7,8,9,13,97])
def test_owned_playable_entry_does_not_wait_for_descriptor_replacement(state):
    assert classify_playable_entry(entry(state))['scene']=='gameplay'


@pytest.mark.parametrize('state',[-1,100,101,0x90000000])
def test_initialization_and_drowning_states_are_not_gameplay(state):
    assert classify_playable_entry(entry(state))['scene']=='unclassified'


@pytest.mark.parametrize('field,value',[('state_handler',0x8001EDE4),('current_handler',0x8001DF78),
                                        ('current_handler',0x80012345),('player',{})])
def test_unknown_or_menu_handlers_and_missing_ownership_remain_blocked(field,value):
    row=entry();row[field]=value
    assert classify_playable_entry(row)['scene']=='unclassified'


def test_invalid_player_identity_remains_blocked():
    row=entry();row['player']['movement']['state_machine_vtable']='0x00000000'
    assert classify_playable_entry(row)['scene']=='unclassified'
