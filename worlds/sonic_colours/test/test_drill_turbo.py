from collections import Counter
from pathlib import Path
import pytest
from ..client import drill_turbo as d


@pytest.mark.parametrize('level',[0,1,2,3])
def test_progressive_drill_data_only(monkeypatch,level):
    monkeypatch.setattr(d,'installed_data',lambda m:0x80002a00)
    writes=[]
    class Memory:
        def read_u32(self,a):return 0
        def write_u32(self,a,v,**kw):writes.append((a,v,kw))
    result=d.configure(Memory(),None,{'counts':Counter({d.ITEM:level})})
    assert result['allowed']==(level>=2)
    assert writes==([(0x80002a00,1,{'expected':0,'operation':'drill_turbo'})] if level>=2 else [])


def test_native_predicate_and_displaced_instruction():
    from ..client.player_switch import payload as assist_payload
    from ..tools.ppc import Executable
    words,offset=d.payload()
    assert (words,offset)==assist_payload()  # already verified boolean mask ABI
    assert offset==32 and words[7]==0x48000008
    path=Path(__file__).parents[1]/'notes/Sonic_Colours_PAL_Static_RE_v2/sonic_pal_disassembly.elf'
    if not path.exists():pytest.skip('private executable absent')
    e=Executable(path)
    assert int.from_bytes(e.read(d.HOOK,4),'big')==d.ORIGINAL
    calls=list(e.disassemble(d.HOOK-4,4))
    assert calls[0].mnemonic=='bl' and calls[0].op_str=='0x8020b020'
    assert int.from_bytes(e.read(0x80104d20,4),'big')==0x901D0060


def test_two_progression_copies_and_existing_item_id():
    from . import generate
    from ..Items import ITEM_TABLE,classification
    from ..world_constants import BASE_ID
    from ..client.test_inventory import MAXIMUM,resolve_item
    from BaseClasses import ItemClassification
    assert ITEM_TABLE[d.ITEM]==BASE_ID+9
    assert classification(d.ITEM)==ItemClassification.progression
    assert resolve_item('drill')==d.ITEM and MAXIMUM[d.ITEM]==2
    world=generate().worlds[1]
    assert sum(item.name==d.ITEM for item in world.multiworld.itempool)==2

