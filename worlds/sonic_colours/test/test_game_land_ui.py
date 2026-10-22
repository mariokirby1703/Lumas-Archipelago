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


@pytest.mark.parametrize('operation',['game_land_ui','emerald_ui'])
def test_batch_reuses_full_revision_but_rejects_owner_change(monkeypatch,operation):
    from ..client import native_read
    monkeypatch.setattr(native_read,'read_stage_objects',lambda m,*a:[{'context':0x9000}])
    monkeypatch.setattr(native_read,'read_actors',lambda m,c:[0x9100])
    class Memory:
        _game_land_ui_batch=None
        proofs=0
        values={0x9100:0x8077e59c,0x9188:0x9200,0x9200:0x9300,0x9198:0x9600,0x9600:0x9700}
        def verify_revision(self):self.proofs+=1
        def read_u32(self,a):return self.values.get(a,0)
        def read_ptr_checked(self,a,n):return self.read_u32(a)
        def read_bytes(self,a,n):
            return b''.join(self.read_u32(a+i).to_bytes(4,'big') for i in range(0,n,4))[:n]
    m=Memory();fields={0x9500:('stage_colour',0)}
    with ui.verified_batch(m,fields,operation=operation):
        assert m.proofs==1
        for _ in range(20):assert ui.validate_batch(m,m._game_land_ui_batch)==fields
        assert m.proofs==1
        m.values[0x9200]=0x9400
        with pytest.raises(MemoryUnavailable):ui.validate_batch(m,m._game_land_ui_batch)
    assert m._game_land_ui_batch is None


def test_bulk_proof_checks_every_anchor_and_ignores_mutable_gaps():
    base=0x90000000
    data=bytearray(64*0x144)
    anchors=tuple((base+i*0x144+0x80,b'\x90\x00\x00\x00') for i in range(64))
    for a,value in anchors:data[a-base:a-base+4]=value
    class Memory:
        reads=0
        def read_bytes(self,a,n):
            self.reads+=1
            return bytes(data[a-base:a-base+n])
    m=Memory();fields={}
    batch={'fields':fields,'anchors':anchors,'code':(), 'blocks':ui.anchor_blocks(anchors)}
    assert ui.validate_batch(m,batch)==fields
    assert m.reads==1  # 64 former cross-process reads, for every write
    data[0x100]=123  # native animation data between anchors is not immutable
    ui.validate_batch(m,batch)
    for a,value in anchors:
        offset=a-base;data[offset]^=1
        with pytest.raises(MemoryUnavailable):ui.validate_batch(m,batch)
        data[offset]^=1


@pytest.mark.parametrize('state',[12,13,14])
def test_row_visibility_resolves_cleared_labels_without_allocating_colour(monkeypatch,state):
    from .test_game_land_columns import Menu
    from ..client import emerald_ui
    m=Menu();m.values[m.actor+0x9c]=state
    flags=0x9000b000
    m.resolve_flags_ptr=lambda **kw:[flags]
    m.available=set(range(210,230))|{252,253,255,256}  # last Act locked; first two groups cleared
    cleared={0,1,3,4}
    for zone in range(7):
        for act in range(3):
            index=7+zone*9+act;ordinal=zone*3+act
            nameptr=0x90200000+index*32
            m.names[nameptr]=f'act_{zone}_{act}'.encode()
            pane=m.array+index*0x144
            m.values[pane+0x140]=1
            m.values[pane+0x28]=m.values[pane+0x20]=int(act>0)
            if ordinal not in cleared:
                m.values[pane+0x74]=0x80
                m.values[pane+0x78]=0x90300000+ordinal*0x20
    monkeypatch.setattr(emerald_ui,'read_stage_objects',lambda *a,**kw:[{'scene':'game_land_select','context':123}])
    monkeypatch.setattr(emerald_ui,'read_actors',lambda *a:[m.actor])
    fields=emerald_ui.targets(m,stages=True)
    hidden={a:c for a,(k,c) in fields.items() if k in ('stage_hidden','stage_hidden_cache')}
    assert len(hidden)==(42 if state==13 else 0)
    colours={c for k,c in fields.values() if k=='stage_colour'}
    assert colours==set(range(21))-cleared
    if state==13:
        cleared_second=m.array+8*0x144
        assert fields[cleared_second+0x28]==('stage_hidden',1)
        assert fields[cleared_second+0x7c]==('dirty_visibility',None)
        assert not m.read_u32(cleared_second+0x78)  # no host-side allocation required


@pytest.mark.parametrize('interrupted',[False,True])
def test_hidden_rows_follow_availability_and_invalidate_before_redraw(monkeypatch,interrupted):
    fields={100:('stage_hidden',1),104:('stage_hidden_cache',1),108:('dirty_visibility',None),
            200:('stage_hidden',20),204:('stage_hidden_cache',20),208:('dirty_colour_visibility',None),
            300:('zero',None),400:('one',None)}
    monkeypatch.setattr(ui,'targets',lambda *a,**kw:fields)
    ui._COMPLETED_REFRESH.clear();ui._PENDING_REFRESH.clear()
    class Memory:
        def __init__(self):self.values={a:1 if k.startswith('stage_hidden') or k=='zero' else 0xffffffff for a,(k,_) in fields.items()};self.writes=[];self.fail=interrupted
        def resolve_flags_ptr(self,**kw):return [1000]
        def read_progress_bit(self,flags,bit):return bit in (211,253) # unlocked and cleared 1-2
        def read_u32(self,a):return self.values[a]
        def write_u32(self,a,v,**kw):
            assert kw=={'expected':self.values[a],'operation':'game_land_ui'}
            if a==108 and self.fail:
                self.fail=False
                raise MemoryUnavailable('scene interrupted after hide publication')
            self.values[a]=v;self.writes.append(a)
    m=Memory();snap=SimpleNamespace(scene='game_land_select');guard=SimpleNamespace(check=lambda _:None)
    if interrupted:
        with pytest.raises(MemoryUnavailable):ui.apply(m,snap,guard,{})
        assert m.values[300]==1 and m.values[400]==0xffffffff
    ui.apply(m,snap,guard,{})
    assert m.values[100]==m.values[104]==0
    assert m.values[200]==m.values[204]==1 # locked 7-3 remains hidden
    assert m.values[108]&0x001a0001==0
    assert m.values[208]&0x001e0081==0
    assert m.writes[-2:]==[300,400]
    m.writes=[];ui.apply(m,snap,guard,{})
    assert not m.writes
def test_early_visibility_is_published_once_and_only_reused_for_same_snapshot(monkeypatch):
    from ..client.runtime import Runtime
    from ..client import game_land_ui
    runtime=Runtime.__new__(Runtime);runtime.snapshot=object();runtime.guard=object()
    calls=[]
    def apply(*args):calls.append(args);return {'status':'ready','changed_fields':21}
    monkeypatch.setattr(game_land_ui,'apply',apply)
    runtime.refresh_game_land_display(None,{},early=True)
    assert runtime.refresh_game_land_display(None,{})['changed_fields']==21
    assert len(calls)==1
    runtime.snapshot=object()
    runtime.refresh_game_land_display(None,{})
    assert len(calls)==2


def test_early_not_ready_is_retried_later_in_same_poll(monkeypatch):
    from ..client.runtime import Runtime
    from ..client import game_land_ui
    runtime=Runtime.__new__(Runtime);runtime.snapshot=object();runtime.guard=object()
    calls=[]
    def apply(*args):
        calls.append(args)
        if len(calls)==1:raise MemoryUnavailable('panes still loading')
        return {'status':'ready'}
    monkeypatch.setattr(game_land_ui,'apply',apply)
    runtime.refresh_game_land_display(None,{},early=True)
    assert runtime.refresh_game_land_display(None,{})['status']=='ready'
    assert len(calls)==2
