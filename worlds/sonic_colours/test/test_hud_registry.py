from ..tools.private_assets import reference_root
from pathlib import Path
import pytest
from ..client.memory import SonicMemory
from ..client.native_read import read_stage_objects
from ..client.ap_hud_publisher import REGISTRY,MAGIC,patches
from .test_memory import FakeBackend


@pytest.mark.parametrize('magic,count,expected',[(MAGIC,350,'save_select'),(MAGIC,260,None),(0,350,None)])
def test_regular_save_menu_requires_registered_resource(magic,count,expected):
    b=FakeBackend();m=SonicMemory(b);m.native_patch={'abi':2}
    def put(a,v):b.put(a,v.to_bytes(4,'big'))
    put(0x808f336c,0x90010000);put(0x90010000,0x80758db8);put(0x90010004,0x90020000)
    put(0x90020000,0x90010000);put(0x9002001c,0x90030000);put(0x90030000,0x80758f38)
    put(0x90030034,0x90040000);put(0x90040000,0x807659c0)
    put(REGISTRY,0x90050000);put(0x90050000,magic);put(0x90050010,0x90060000)
    put(0x90060000,0x807abc40);put(0x9006000c,0x90070000);put(0x9007002c,count)
    assert read_stage_objects(m,False)[0].get('scene')==expected


def test_saved_draw_caller_is_layer_and_not_glyph_geometry():
    from ..tools.ppc import Executable
    elf=reference_root()/'Sonic_Colours_PAL_Static_RE_v2/sonic_pal_disassembly.elf'
    if not elf.exists():pytest.skip('private PAL ELF absent')
    e=Executable(elf)
    # 805E0C84 saves original r31 at +7C. Publisher's own frame adds 160.
    assert e.read(0x805e0c84,4)==bytes.fromhex('9421ff80')
    assert e.read(0x805e0c90,4)==bytes.fromhex('be010040')
    assert e.read(0x805eb04c,4)==bytes.fromhex('807f000c')
    assert any(bytes.fromhex('806101dc') in new for a,old,new in patches(native_registry=True))
    assert not any(bytes.fromhex('806101dc') in new for a,old,new in patches())
