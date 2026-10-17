import struct
import pytest
from ..client import ap_hud_connected as hud
from ..client.memory import SonicMemory,MemoryUnavailable


class Resource:
    def __init__(self):
        self.bytes={};self.calls=0
    def put(self,a,data):self.bytes.update((a+i,v) for i,v in enumerate(data))
    def word(self,a,v):self.put(a,struct.pack('>I',v))
    def read_bytes(self,a,n):
        self.calls+=1
        return bytes(self.bytes.get(a+i,0) for i in range(n))


def setup(monkeypatch):
    b=Resource();actor=0x90001000;handle=actor+0x84;ref=0x90002000
    layer=0x90003000;layout=0x90004000;table=0x90005000;groups=0x90006000;control=0x90007000
    b.word(handle+4,ref);b.word(ref,layer);b.word(layer,0x807abc40)
    b.word(layer+12,layout);b.word(layout+44,111);b.word(layout+48,table);b.word(layout+40,groups)
    b.word(control,hud.MAGIC);b.word(control+8,128)
    for i in range(111):
        name=0x90200000+i*64
        b.put(name,(f'ap_test{i}' if i<90 else f'native{i}').encode()+b'\0')
        group,index=1+i//15,i%15
        b.put(table+12*i,struct.pack('>III',name,group,index))
        if i>=90:continue
        array=0x90300000+group*256;record=0x90400000+i*256;box=0x90500000+i*256
        b.word(groups+group*16+4,array);b.word(array+index*4,record)
        b.word(record+4,2);b.word(record+64,box)
        b.word(box+4,control);b.word(box+12,name);b.word(box+152,0x41504d42)
    monkeypatch.setattr(hud,'read_stage_objects',lambda *a:[{'scene':'global_map','context':0x90100000}])
    monkeypatch.setattr(hud,'read_actors',lambda *a:[actor])
    return b,SonicMemory(b),layer


def test_bulk_reader_resolves_the_exact_owner_and_all_casts(monkeypatch):
    b,m,layer=setup(monkeypatch)
    owner=hud.discover(m)
    assert owner['layer']==layer and len(owner['boxes'])==90
    assert all(type(a) is int for a,data in owner['anchors'])
    assert b.calls<700
    hud.validate(m,owner)


def test_bulk_reader_still_rejects_a_foreign_controller(monkeypatch):
    b,m,layer=setup(monkeypatch)
    b.word(0x90500000+43*256+4,0x90008000)
    with pytest.raises(MemoryUnavailable,match='uniquely'):hud.discover(m)


def test_bulk_reader_rejects_corrupted_cast_pointer(monkeypatch):
    b,m,layer=setup(monkeypatch)
    b.word(0x90300000+256,0xdeadbeef)
    with pytest.raises(MemoryUnavailable,match='uniquely'):hud.discover(m)
