"""PAL native enum evidence, separate from the stable AP item ordering."""
import struct
from pathlib import Path
import pytest
from ..world_constants import NATIVE_COLOURS
from ..capsules import CAPSULES


def test_capsule_requirements_match_native_colour_indices():
    names=('White Boost',)+NATIVE_COLOURS
    for capsule in CAPSULES.values():
        if capsule.eligible:
            assert capsule.wisp_item==names[capsule.raw_wisp]+' Wisp'
    assert NATIVE_COLOURS.index('Orange Rocket')==3
    assert NATIVE_COLOURS.index('Blue Cube')==5
    assert NATIVE_COLOURS.index('Green Hover')==6


def test_original_pal_indexed_sound_table_proves_colour_order():
    from ..tools.ppc import Executable
    path=Path(__file__).parents[1]/'notes/Sonic_Colours_PAL_Static_RE_v2/sonic_pal_disassembly.elf'
    if not path.exists():pytest.skip('original PAL ELF absent')
    executable=Executable(path)
    rows=struct.unpack('>12I',executable.read(0x80765390,48))
    suffix=('laser','spike','rocket','rodeo','puzzle','astronautes')
    for k,name in enumerate(suffix):
        index,address=rows[k*2:k*2+2]
        assert index==k+1
        assert executable.read(address,40).split(b'\0')[0]==f'sound/se_phantom_{name}.csb'.encode()


@pytest.mark.parametrize('index,name',tuple(enumerate(NATIVE_COLOURS)))
def test_each_item_projects_only_its_native_live_permission(index,name):
    from collections import Counter
    from types import SimpleNamespace
    from ..client.hooks import NativeHooks
    from ..client.memory import MemoryUnavailable
    class Memory:
        writes=[]
        def read_u8(self,a):return 0
        def read_u32(self,a):raise MemoryUnavailable('offline hook absent')
        def write_u8(self,a,v,**kwargs):self.writes.append((a,v))
    memory=Memory(); memory.writes=[]
    snapshot=SimpleNamespace(scene='gameplay',evidence={'native_data':{'stage_objects':[{'stage':0x90001000,'actor_state':0x90002000}]}})
    NativeHooks().project_live_permissions(memory,snapshot,{'counts':Counter({name+' Wisp':1})},{})
    assert memory.writes==[(0x90001061,1<<index),(0x90002090,1<<index)]
