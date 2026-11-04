import struct
import pytest
from . import generate
from ..client.native_dol import plan, plan_for_digest


def test_fps_option_and_legacy_slot_compatibility():
    from ..client.runtime import validate_slot
    from ..client.client import slot_identity_digest
    slot = generate({'sixty_fps': True}).worlds[1].fill_slot_data()
    assert slot['options']['sixty_fps'] == 1
    assert validate_slot(slot) == slot
    old = {**slot, 'options_revision': 12, 'options': dict(slot['options'])}
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
    machine.emu_start(0x803E19E4, 0x80010000, count=100)
    assert machine.reg_read(r.UC_PPC_REG_3) == 1
    for address in (0x808F2D94, 0x8090DB08):
        assert bytes(machine.mem_read(address, 4)) == struct.pack('>I', 1)
    machine.reg_write(r.UC_PPC_REG_3, interval)
    machine.emu_start(0x803E19B0, 0x803E19B4, count=100)
    assert machine.reg_read(r.UC_PPC_REG_3) == 1
    assert machine.reg_read(r.UC_PPC_REG_1) == 0x8001FFF0
    assert bytes(machine.mem_read(0x8090DB08, 4)) == struct.pack('>I', 1)
    assert base[2] != plan(include_sixty_fps=True)[2]
    assert plan_for_digest(plan(include_sixty_fps=True)[2].hex())[2] == plan(include_sixty_fps=True)[2]
