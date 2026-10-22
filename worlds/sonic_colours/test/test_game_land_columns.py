from ..client import game_land_columns as c
from ..client import native_read
from ..client.memory import MemoryUnavailable
import pytest


class Menu:
    actor=0x90001000
    array=0x90100000
    def __init__(self):
        self.values={self.actor:0x8077e59c,self.actor+0x9c:13,
                     self.actor+0x88:0x90002000,0x90002000:0x90003000,
                     0x9000300c:0x90004000,0x9000402c:64,0x90004030:0x90005000,
                     0x9000308c:0x90006000,0x9000600c:0x90007000,
                     0x90007004:0x90008000,0x90008000:64,0x90008004:self.array,
                     0x9000900c:0x9000a000}
        self.names={}
        for i in range(64):
            entry=0x90005000+12*i;nameptr=0x90200000+32*i
            self.values.update({entry:nameptr,entry+4:0,entry+8:i})
            self.names[nameptr]=(f'emerald_{(i-1)//9}' if i in range(1,56,9) else f'node_{i}').encode()
            pane=self.array+i*0x144
            self.values[pane+0x7c]=0x387fff
            self.values[pane+0x80]=0 if i==0 else self.array+(1+(i-1)//9*9)*0x144 if (i-1)%9 else self.array
            self.values[pane+0x84]=0x90009000
        self.available={210,213}
        self.values[self.array+0x144+0x38]=0x3f800000
        self.values[self.array+0x144+0x3c]=0x3f800000
        self.values[self.array+0x144]=self.values[self.array+0x144+16]=0x3f800000
    def read_u32(self,a):return self.values.get(a,0)
    def read_bytes(self,a,n):
        if a in self.names:return self.names[a].ljust(n,b'\0')
        return b''.join(self.read_u32(a+i).to_bytes(4,'big') for i in range(0,n,4))
    def read_ptr_checked(self,a,n=4):
        value=self.read_u32(a)
        if not value:raise MemoryUnavailable('null pointer')
        return value
    def read_progress_bit(self,f,b):return b in self.available


@pytest.fixture
def menu(monkeypatch):
    m=Menu()
    monkeypatch.setattr(native_read,'read_stage_objects',lambda *a:[{'scene':'game_land_select','context':123}])
    monkeypatch.setattr(native_read,'read_actors',lambda *a:[m.actor])
    # The resolver imports these functions at module load time.
    monkeypatch.setattr(c,'read_stage_objects',native_read.read_stage_objects)
    monkeypatch.setattr(c,'read_actors',native_read.read_actors)
    return m


def test_unlocked_collapsed_column_unfolds_without_unlocking_other_stages(menu):
    fields=c.targets(menu,1);column=menu.array+10*0x144
    assert {a for a,(k,_) in fields.items() if k=='column_scale'}=={column+0x38,column+0x3c}
    assert fields[column+0x7c][0]=='dirty_scale'
    assert fields[menu.array+16*0x144+0x7c][0]=='dirty_matrix'
    assert menu.array+19*0x144+0x38 not in fields
    assert fields[0x9000a038]==('one',None)


def test_dictionary_and_parent_tree_use_single_bulk_reads(menu):
    reads=[]
    original=menu.read_bytes
    def read_bytes(address,size):
        reads.append((address,size))
        return original(address,size)
    menu.read_bytes=read_bytes
    assert c.targets(menu,1)
    assert reads.count((0x90005000,64*12))==1
    assert reads.count((menu.array,64*0x144))==1


@pytest.mark.parametrize('state',[0,1,9,12,14,17])
def test_transitions_are_not_touched(menu,state):
    menu.values[menu.actor+0x9c]=state
    assert c.targets(menu,1)=={}


def test_native_scale_override_is_preserved(menu):
    menu.values[menu.array+10*0x144+0x74]=0x10
    assert c.targets(menu,1)=={}


def test_partial_animation_and_repeated_application_are_preserved(menu):
    column=menu.array+10*0x144
    menu.values[column+0x38]=0x3f000000
    assert c.targets(menu,1)=={}
    menu.values[column+0x38]=menu.values[column+0x3c]=0x3f800000
    menu.values[column]=menu.values[column+16]=0x3f800000
    assert c.targets(menu,1)=={}


def test_rejects_bad_column_tree(menu):
    menu.values[menu.array+16*0x144+0x80]=0xdeadbeef
    with pytest.raises(MemoryUnavailable,match='topology'):c.targets(menu,1)


def test_local_scale_alone_does_not_count_as_matrix_repair(menu):
    column=menu.array+10*0x144
    menu.values[column+0x38]=menu.values[column+0x3c]=0x3f800000
    fields=c.targets(menu,1)
    assert fields[column+0x7c]==('dirty_scale',None)
    # 805E5310 needs the local scale validity bits cleared as well as the
    # world-matrix cache, otherwise it reuses the previous zero-scale matrix.
    repaired=menu.read_u32(column+0x7c)&~0x00180030
    assert repaired&0x30==0
    assert repaired&0x80  # unrelated colour validity remains intact
