from collections import Counter
from types import SimpleNamespace
import pytest
from ..client import emerald_ui as ui
from ..client.memory import MemoryUnavailable


@pytest.mark.parametrize('colour',ui.UI_COLOURS)
def test_received_colour_independent_of_slot_order_and_locations(monkeypatch,colour):
    fields={100+i:('colour',c) for i,c in enumerate(ui.UI_COLOURS)}
    fields.update({200:('dirty_colour',None),201:('dirty',None),202:('zero',None),203:('one',None)})
    monkeypatch.setattr(ui,'targets',lambda m:fields)
    class Memory:
        def __init__(self):self.values={a:0x606060ff if k=='colour' else 0xffffffff for a,(k,c) in fields.items()};self.writes=[]
        def read_u32(self,a):return self.values[a]
        def write_u32(self,a,v,**kw):
            assert kw=={'expected':self.values[a],'operation':'emerald_ui'}
            self.values[a]=v;self.writes.append(a)
    m=Memory();guard=SimpleNamespace(check=lambda s:None)
    snap=SimpleNamespace(scene='game_land_select',emerald_rewards=frozenset())
    result=ui.apply(m,snap,guard,{'counts':Counter({colour+' Chaos Emerald':1})})
    assert result['owned_colours']==[colour]
    for i,c in enumerate(ui.UI_COLOURS):assert m.values[100+i]==(0xffffffff if c==colour else 0x606060ff)
    assert snap.emerald_rewards==frozenset()
    assert m.values[200]==0xffe7ff7f and m.values[201]==0xffefffff
    assert m.values[202]==0 and m.values[203]==1
    m.writes=[];ui.apply(m,snap,guard,{'counts':Counter({colour+' Chaos Emerald':1})})
    assert m.writes==[]
    ui.apply(m,snap,guard,{'counts':Counter()})
    assert all(m.values[100+i]==0x606060ff for i in range(7))


def test_ui_order_and_unattributed_save_blocks(monkeypatch):
    assert ui.UI_COLOURS==('Green','Yellow','White','Red','Purple','Blue','Cyan')
    def blocked(s):raise MemoryUnavailable('save not attributed')
    monkeypatch.setattr(ui,'targets',lambda m:pytest.fail('must not resolve/write before save guard'))
    with pytest.raises(MemoryUnavailable):ui.apply(None,SimpleNamespace(scene='game_land_select'),SimpleNamespace(check=blocked),{'counts':Counter()})
    assert ui.apply(None,SimpleNamespace(scene='gameplay'),None,{})['status']=='not on Game Land menu'


def test_redraw_published_after_every_dirty_pane_and_retries_interruption(monkeypatch):
    # Deliberately interleave the root marker with other panes as the resolver
    # naturally does. A native frame may consume that marker immediately.
    fields={100:('colour','Green'),200:('dirty_colour',None),300:('zero',None),
            400:('one',None),201:('dirty_colour',None),301:('zero',None),401:('one',None)}
    monkeypatch.setattr(ui,'targets',lambda m:fields)
    ui._PENDING_REFRESH.clear()
    class Memory:
        values={100:0x606060ff,200:0xffffffff,201:0xffffffff,300:1,301:1,400:0,401:0}
        writes=[]
        fail=True
        def read_u32(self,a):return self.values[a]
        def write_u32(self,a,v,**kw):
            if a==201 and self.fail:
                self.fail=False
                raise MemoryUnavailable('native context interrupted')
            if a in (400,401):
                assert self.values[200]&0x00180080==0
                assert self.values[201]&0x00180080==0
                assert self.values[300]==self.values[301]==0
            self.values[a]=v;self.writes.append(a)
    m=Memory();snap=SimpleNamespace(scene='game_land_select');guard=SimpleNamespace(check=lambda s:None)
    owned={'counts':Counter({'Green Chaos Emerald':1})}
    with pytest.raises(MemoryUnavailable):ui.apply(m,snap,guard,owned)
    assert m.values[100]==0xffffffff
    assert not set(m.writes)&{400,401}
    ui.apply(m,snap,guard,owned)
    assert m.writes[-2:]==[400,401]
    assert not ui._PENDING_REFRESH


def test_initial_emerald_projection_does_not_require_lazy_wrapper_cache(monkeypatch):
    from .test_memory import FakeBackend
    from ..client.memory import SonicMemory
    b=FakeBackend();m=SonicMemory(b);actor=0x90001000
    def put(a,v):b.put(a,v.to_bytes(4,'big'))
    put(actor,ui.ACTOR_VTABLE)
    monkeypatch.setattr(ui,'read_stage_objects',lambda memory,**kw:[{'scene':'game_land_select','context':0x90002000}])
    monkeypatch.setattr(ui,'read_actors',lambda memory,context:[actor])
    for layer_index,offset in enumerate((0x84,0x94)):
        base=0x90100000+layer_index*0x100000;ref=base;layer=base+0x100;layout=base+0x300;table=base+0x400
        graph=base+0x800;group_ref=base+0x900;groups=base+0xa00;panes=base+0x1000
        put(actor+offset+4,ref);put(ref,layer);put(layer+0xc,layout)
        put(layout+0x2c,14);put(layout+0x30,table);put(layer+0x8c,graph)
        put(graph+0xc,group_ref);put(group_ref+4,groups);put(groups+4,panes)
        put(layer+0xd8,0) # no cached wrappers at all, as on first presentation
        for index in range(14):
            name=(f'em_img_{index//2}' if index%2==0 else f'em_bli_{index//2}').encode()
            nameptr=base+0x4000+index*16;b.put(nameptr,name.ljust(16,b'\0'))
            put(table+index*12,nameptr);put(table+index*12+4,0);put(table+index*12+8,index)
            pane=panes+index*0x144;data=base+0x5000+index*0x20;root=base+0x6000;owner=base+0x6100
            put(pane+0x74,0x80);put(pane+0x78,data);put(pane+0x84,root);put(root+0xc,owner)
    fields=ui.targets(m)
    colours=[c for k,c in fields.values() if k=='colour']
    assert len(colours)==28 and colours.count('Yellow')==4
    assert not b.writes
