from types import SimpleNamespace
import pytest
from ..client import game_land_ui as ui, game_land_menu
from ..client.memory import MemoryUnavailable


def test_visibility_and_completion_are_independent():
    class Memory:
        def read_progress_bit(self,flags,bit):return bit in (210,213,252)
    m=Memory()
    assert ui.stage_colour(m,100,0)==0xffffffff  # completed 1-1
    assert ui.stage_colour(m,100,3)==0x606060ff  # available, uncleared 2-1
    assert ui.stage_colour(m,100,6)==0           # locked 3-1


def test_stage_colours_dirty_before_redraw_and_never_write_clear_bits(monkeypatch):
    fields={100:('stage_colour',3),200:('dirty_colour',None),300:('zero',None),400:('one',None)}
    monkeypatch.setattr(ui,'targets',lambda m,stages:fields)
    ui._COMPLETED_REFRESH.clear();ui._PENDING_REFRESH.clear()
    class Memory:
        values={100:0,200:0xffffffff,300:1,400:0}
        writes=[]
        def resolve_flags_ptr(self,**kw):return [1000]
        def read_progress_bit(self,flags,bit):return bit==213
        def read_u32(self,a):return self.values[a]
        def write_u32(self,a,v,**kw):
            assert a in fields and kw=={'expected':self.values[a],'operation':'game_land_ui'}
            self.values[a]=v;self.writes.append(a)
    m=Memory();guard=SimpleNamespace(check=lambda s:None)
    result=ui.apply(m,SimpleNamespace(scene='game_land_select'),guard,{})
    assert m.values[100]==0x606060ff
    assert m.writes==[100,200,300,400]
    assert result['changed_fields']==4
    m.writes=[];ui.apply(m,SimpleNamespace(scene='game_land_select'),guard,{})
    assert not m.writes


def test_unattributed_save_cannot_write_ui(monkeypatch):
    def blocked(s):raise MemoryUnavailable('save not attributed')
    monkeypatch.setattr(ui,'targets',lambda *args,**kw:pytest.fail('resolve before guard'))
    with pytest.raises(MemoryUnavailable):
        ui.apply(None,SimpleNamespace(scene='game_land_select'),SimpleNamespace(check=blocked),{})


def test_export_restores_native_clear_tint_and_keeps_lock_visibility():
    lines=game_land_menu.gecko_lines()
    assert '042F0D98 4BE6E235' in lines
    assert '042F0DD4 7F64DB78' in lines
    base=min(game_land_menu.PATCHES)
    raw=bytearray(max(game_land_menu.PATCHES)-base+4)
    for address,(old,new) in game_land_menu.PATCHES.items():
        raw[address-base:address-base+4]=old.to_bytes(4,'big')
    original=bytes(raw)
    for line in lines:
        first,word=(int(x,16) for x in line.split())
        address=0x80000000+(first&0xffffff)
        raw[address-base:address-base+4]=word.to_bytes(4,'big')
    assert game_land_menu.normalize(None,bytes(raw),base)==original


def test_existing_linear_seed_gets_free_starter_without_changing_other_gates():
    from . import generate
    from ..client.runtime import validate_slot
    data=generate().worlds[1].fill_slot_data()
    from ..world_constants import game_land_gates
    gates=game_land_gates(data['options']['game_land_requirement_reduction'])
    old={**data,'options_revision':7,'game_land_gates':{**gates,'1-1':1}}
    current=validate_slot(old)
    assert current['game_land_gates']['1-1']==0
    assert all(current['game_land_gates'][k]==v for k,v in old['game_land_gates'].items() if k!='1-1')
    assert old['game_land_gates']['1-1']==1


def test_batch_reuses_full_revision_but_rejects_owner_change(monkeypatch):
    from ..client import native_read
    monkeypatch.setattr(native_read,'read_stage_objects',lambda m,*a:[{'context':0x9000}])
    monkeypatch.setattr(native_read,'read_actors',lambda m,c:[0x9100])
    class Memory:
        _game_land_ui_batch=None
        proofs=0
        values={0x9100:0x8077e59c,0x9188:0x9200,0x9200:0x9300}
        def verify_revision(self):self.proofs+=1
        def read_u32(self,a):return self.values.get(a,0)
        def read_ptr_checked(self,a,n):return self.read_u32(a)
        def read_bytes(self,a,n):return self.read_u32(a).to_bytes(4,'big')[:n].ljust(n,b'\0')
    m=Memory();fields={0x9500:('stage_colour',0)}
    with ui.verified_batch(m,fields):
        assert m.proofs==1
        for _ in range(20):assert ui.validate_batch(m,m._game_land_ui_batch)==fields
        assert m.proofs==1
        m.values[0x9200]=0x9400
        with pytest.raises(MemoryUnavailable):ui.validate_batch(m,m._game_land_ui_batch)
    assert m._game_land_ui_batch is None
