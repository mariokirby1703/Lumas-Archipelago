import struct
import pytest
from . import generate,legacy_rank_slot
from ..client.native_dol import plan, plan_for_digest


def test_fps_option_and_legacy_slot_compatibility():
    from ..client.runtime import validate_slot
    from ..client.client import slot_identity_digest
    slot = generate({'sixty_fps': True}).worlds[1].fill_slot_data()
    assert slot['options']['sixty_fps'] == 1
    assert validate_slot(slot) == slot
    old = {**slot, 'options_revision': 12, 'options': dict(slot['options'])}
    legacy_rank_slot(old)
    old['options'].pop('sixty_fps')
    old['options'].pop('luma')
    upgraded = validate_slot(old)
    assert upgraded['options']['sixty_fps'] == 0
    assert slot_identity_digest(upgraded) == slot_identity_digest(old)
    assert generate().worlds[1].options.sixty_fps.value == 0


@pytest.mark.parametrize('interval', (1, 2, 3))
def test_native_frame_interval_and_vi_override(interval):
    u = pytest.importorskip('unicorn')
    from unicorn import ppc_const as r
    machine = u.Uc(u.UC_ARCH_PPC, u.UC_MODE_32 | u.UC_MODE_BIG_ENDIAN)
    import faulthandler
    enabled = faulthandler.is_enabled()
    try:
        faulthandler.disable()
        machine.mem_map(0x80000000, 0x1800000)
    finally:
        if enabled: faulthandler.enable()
    base = plan()
    patches = plan(include_sixty_fps=True)[0]
    for address, old, new in patches:
        machine.mem_write(address, new)
    machine.mem_write(0x803E19E8, bytes.fromhex('4e800020'))
    machine.reg_write(r.UC_PPC_REG_13, 0x808F9520)
    machine.reg_write(r.UC_PPC_REG_1, 0x80020000)
    machine.reg_write(r.UC_PPC_REG_LR, 0x80010000)
    machine.mem_write(0x808F2D94, struct.pack('>I', interval))
    machine.mem_write(0x8090DB08, bytes.fromhex('aabbcc02'))
    machine.emu_start(0x803E19E4, 0x80010000, count=100)
    assert machine.reg_read(r.UC_PPC_REG_3) == 1
    assert bytes(machine.mem_read(0x808F2D94, 4)) == struct.pack('>I', 1)
    assert bytes(machine.mem_read(0x8090DB08, 4)) == bytes.fromhex('aabbcc01')
    machine.reg_write(r.UC_PPC_REG_3, interval)
    machine.emu_start(0x803E19B0, 0x803E19B4, count=100)
    assert machine.reg_read(r.UC_PPC_REG_3) == 1
    assert machine.reg_read(r.UC_PPC_REG_1) == 0x8001FFF0
    assert bytes(machine.mem_read(0x8090DB08, 4)) == bytes.fromhex('aabbcc01')
    assert base[2] != plan(include_sixty_fps=True)[2]
    assert plan_for_digest(plan(include_sixty_fps=True)[2].hex())[2] == plan(include_sixty_fps=True)[2]


@pytest.mark.parametrize('luma',[False,True])
def test_prior_native_fps_iso_remains_recognized(luma):
    old=plan(include_sixty_fps=True,include_luma_colors=luma,legacy_fps_word_write=True)
    current=plan(include_sixty_fps=True,include_luma_colors=luma)
    assert old[2]!=current[2]
    assert plan_for_digest(old[2].hex())[2]==old[2]


@pytest.mark.parametrize('enabled',[False,True])
def test_private_original_interval_setter_computes_correct_gameplay_delta(enabled):
    from pathlib import Path
    from ..client.native_dol import Dol
    source=Path('build/sonic_colours_reference/memdumps_and_more/main.dol')
    if not source.exists():pytest.skip('private original main.dol absent')
    u=pytest.importorskip('unicorn')
    from unicorn import ppc_const as r
    import faulthandler
    machine=u.Uc(u.UC_ARCH_PPC,u.UC_MODE_32|u.UC_MODE_BIG_ENDIAN)
    previous=faulthandler.is_enabled()
    try:
        faulthandler.disable()
        machine.mem_map(0x80000000,0x1800000)
    finally:
        if previous:faulthandler.enable()
    image=Dol(source.read_bytes())
    for index,offset,address,size in image.sections:machine.mem_write(address,image.read(address,size))
    if enabled:
        for address,old,new in plan(include_sixty_fps=True)[0]:machine.mem_write(address,new)
    machine.reg_write(r.UC_PPC_REG_MSR,0x2000)
    for reg,value in ((r.UC_PPC_REG_1,0x80020000),(r.UC_PPC_REG_2,0x808FC5C0),
                      (r.UC_PPC_REG_13,0x808F9520),(r.UC_PPC_REG_3,2),(r.UC_PPC_REG_LR,0x80010000)):
        machine.reg_write(reg,value)
    machine.mem_write(0x808F2D90,struct.pack('>f',60.))
    machine.mem_write(0x8090DB08,bytes.fromhex('aabbcc02'))
    machine.emu_start(0x803E19B0,0x80010000,count=200)
    delta=struct.unpack('>f',machine.mem_read(0x808F2D98,4))[0]
    assert delta==pytest.approx(1/(60 if enabled else 30))
    assert bytes(machine.mem_read(0x8090DB08,4))==bytes.fromhex('aabbcc01' if enabled else 'aabbcc02')


@pytest.mark.parametrize('luma',[False,True])
def test_private_legacy_fps_iso_passes_complete_revision_validation(luma):
    import hashlib
    from pathlib import Path
    from ..client.native_dol import Dol,ARENA,SIGNATURE,MAGIC,ABI
    from ..client.memory import SonicMemory
    source=Path('build/sonic_colours_reference/memdumps_and_more/main.dol')
    if not source.exists():pytest.skip('private original main.dol absent')
    image=Dol(source.read_bytes())
    patches,payload,digest,hooks=plan(include_sixty_fps=True,include_luma_colors=luma,legacy_fps_word_write=True)
    for address,old,new in patches:image.replace(address,image.read(address,len(new)) if old is None else old,new)
    native=bytearray(SIGNATURE-ARENA+64);native[:len(payload)]=payload
    native[-64:]=MAGIC+struct.pack('>II',ABI,len(payload))+digest+hashlib.sha256(b'ExistingFPSSeed').digest()[:16]
    image.add_text(ARENA,native)
    class Backend:
        def read_bytes(self,address,size):
            if address==0x80000000:return (b'SNCE8P'+bytes(26))[:size]
            if address==0x80000007:return bytes(size)
            try:return image.read(address,size)
            except ValueError:return bytes(size)
    memory=SonicMemory(Backend());memory.verify_revision()
    assert memory.native_patch['code_sha256']==digest.hex()
    assert memory.native_patch['luma_ring_colors']==luma
