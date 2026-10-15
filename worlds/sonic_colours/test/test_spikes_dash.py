from pathlib import Path
from . import generate
from ..Items import ITEM_TABLE
from ..world_constants import BASE_ID
from ..client.test_inventory import MAXIMUM,resolve_item


def test_spikes_two_copies_and_same_numeric_id():
    assert ITEM_TABLE['Progressive Pink Spikes Wisp']==BASE_ID+13
    assert MAXIMUM['Progressive Pink Spikes Wisp']==2
    assert resolve_item('spikes')=='Progressive Pink Spikes Wisp'
    world=generate().worlds[1]
    assert sum(item.name=='Progressive Pink Spikes Wisp' for item in world.multiworld.itempool)==2


def test_native_charge_transition_precedes_dash_entry():
    import pytest
    from ..tools.ppc import Executable
    path=Path(__file__).parents[1]/'notes/Sonic_Colours_PAL_Static_RE_v2/sonic_pal_disassembly.elf'
    if not path.exists():pytest.skip('private executable absent')
    e=Executable(path)
    assert e.read(0x801fd4e0,4)==bytes.fromhex('38800052')
    instructions=list(e.disassemble(0x801fd4e4,4))
    assert instructions[0].mnemonic=='bl' and instructions[0].op_str=='0x80033878'
    assert int.from_bytes(e.read(0x80771e08+0x28,4),'big')==0x801fdd90


def test_owned_spikes_has_complete_abilities_when_movement_randomization_is_off():
    from collections import Counter
    from ..client.runtime import Runtime
    from ..client.movement_gate import permissions
    r=object.__new__(Runtime);r.slot_data={'options':{'movement_unlocks':False}}
    owned={'counts':Counter({'Progressive Pink Spikes Wisp':1})}
    mask=permissions(r.movement_policy(owned)['counts'])
    assert mask & 8192 and mask & 4095 == 4095
    assert owned['counts']['Double Jump']==0
    owned['counts']['Progressive Pink Spikes Wisp']=2
    assert permissions(r.movement_policy(owned)['counts']) & 8192
