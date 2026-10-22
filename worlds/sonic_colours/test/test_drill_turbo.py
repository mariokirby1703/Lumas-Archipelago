from ..tools.private_assets import reference_root
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
    assert offset==24 and words[5]==0x48000008
    path=reference_root()/'Sonic_Colours_PAL_Static_RE_v2/sonic_pal_disassembly.elf'
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


@pytest.mark.parametrize('permission',[0,1])
@pytest.mark.parametrize('pressed',[0,1])
def test_actual_water_turbo_predicate_uses_same_permission_as_ground(monkeypatch,permission,pressed):
    from ..client import native_events as n
    from ..client.native_dol import plan
    from .test_native_events import Machine
    rows=d.water_planned_patches();hooks=plan()[3]
    m=Machine('death');m.kind='water_drill_turbo'
    monkeypatch.setitem(n.HOOKS,m.kind,(d.WATER_HOOK,d.WATER_ORIGINAL))
    for address,old,new in rows:m.b.put(address,new)
    control=next(h for h in hooks if h['hook']==d.HOOK)['target']+d.payload()[1]
    m.put(control,permission);m.r[3]=pressed;m.before=m.r[:]
    m.run()
    assert m.r[3]==pressed&permission
    assert m.r[:3]==m.before[:3] and m.r[4:12]==m.before[4:12] and m.r[13:]==m.before[13:]
    assert m.lr==0x80001234 and m.ctr==0x80005678 and m.f==m.before_f
    assert not m.b.writes and not m.calls


def test_water_drill_original_input_and_padding():
    import struct
    from ..client.native_dol import Dol,patch_dol
    from ..world_constants import load_data
    im=Dol((reference_root()/'memdumps_and_more/main.dol').read_bytes())
    assert im.read(d.WATER_HOOK,4)==struct.pack('>I',d.WATER_ORIGINAL)
    # Independent held-action 1 query, before effects/internal turbo state.
    assert im.read(d.WATER_HOOK-8,4)==bytes.fromhex('38800001')
    word=int.from_bytes(im.read(d.WATER_HOOK-4,4),'big');delta=word&0x3fffffc
    if delta&0x2000000:delta-=0x4000000
    assert d.WATER_HOOK-4+delta==0x8020b020
    assert im.read(d.WATER_HOOK+4,4)==bytes.fromhex('41820050')
    refs=set()
    for index,offset,base,size in im.sections:
        for i in range(0,size-3,4):
            word=struct.unpack_from('>I',im.data,offset+i)[0];refs.add(word)
            if index<7 and word>>26 in (16,18):
                mask,sign=(0xfffc,0x8000) if word>>26==16 else (0x3fffffc,0x2000000)
                delta=word&mask
                if delta&sign:delta-=sign*2
                refs.add(delta if word&2 else base+i+delta)
    for site in load_data('water_drill_turbo_sites.json'):
        a=site['address'];before=int(site['before'],16)
        assert im.read(a-4,16)==struct.pack('>I',before)+bytes(12)
        assert before==0x4e800020 or before>>26==18 and not before&1
        assert not any(a+i in refs for i in range(12))
    patch_dol(bytes(im.data),'water-drill-turbo')

