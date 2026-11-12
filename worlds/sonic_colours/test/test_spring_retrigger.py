import faulthandler
import struct

import pytest

from ..client import spring_retrigger as spring
from ..client.native_dol import plan


@pytest.mark.parametrize('elapsed,blocked', [(0., True), (1/60, True), (1/30, True),
                                            (.049, True), (.05, False), (.2, False),
                                            (-1., False), (float('nan'), False)])
def test_repeated_spring_contact_preserves_the_original_launch(elapsed, blocked):
    run_guard(elapsed, blocked)


@pytest.mark.parametrize('field,value', [('vtable', 0x8075EA40), ('id', 7), ('active', 0), ('message', 0x6001)])
def test_other_states_and_messages_keep_original_handler(field, value):
    run_guard(0., False, **{field: value})


def run_guard(elapsed, blocked, vtable=spring.SPRING_STATE, id=18, active=1, message=0x6000):
    u = pytest.importorskip('unicorn')
    from unicorn import ppc_const as r
    cpu = u.Uc(u.UC_ARCH_PPC, u.UC_MODE_32 | u.UC_MODE_BIG_ENDIAN)
    enabled = faulthandler.is_enabled()
    try:
        faulthandler.disable()
        cpu.mem_map(0x80000000, 0x1800000)
    finally:
        if enabled: faulthandler.enable()
    for address, old, new in spring.patches(plan()[0]): cpu.mem_write(address, new)
    state, machine, msg, stack, caller = 0x80200000, 0x80201000, 0x80202000, 0x80024000, 0x80010000
    for address, value in ((state,vtable),(state+8,id),(state+12,active),(msg+4,message)):
        cpu.mem_write(address, struct.pack('>I',value))
    cpu.mem_write(state+0x24, struct.pack('>f',elapsed))
    state_before = bytes(cpu.mem_read(state, 0x40))
    original = {r.UC_PPC_REG_0:0x12345678,r.UC_PPC_REG_1:stack,
                r.UC_PPC_REG_3:state,r.UC_PPC_REG_4:machine,r.UC_PPC_REG_5:msg,
                r.UC_PPC_REG_6:0x11223344,r.UC_PPC_REG_7:0x55667788,
                r.UC_PPC_REG_LR:caller,r.UC_PPC_REG_CR:0x87654321,r.UC_PPC_REG_CTR:0x80012000}
    for register, value in original.items(): cpu.reg_write(register,value)
    stop = caller if blocked else spring.HOOK+4
    cpu.emu_start(spring.HOOK,stop,count=2000)
    assert cpu.reg_read(r.UC_PPC_REG_PC) == stop
    assert bytes(cpu.mem_read(state, 0x40)) == state_before
    assert bytes(cpu.mem_read(msg+0x38,1)) == (b'\1' if blocked else b'\0')
    for register,value in original.items():
        if register == r.UC_PPC_REG_1: value = stack if blocked else stack-0x30
        if register == r.UC_PPC_REG_3 and blocked: value = 1
        assert cpu.reg_read(register) == value


def test_spring_guard_is_only_installed_for_new_60_fps_images():
    assert not any(a==spring.HOOK for a,o,n in plan()[0])
    assert not any(a==spring.HOOK for a,o,n in plan(include_sixty_fps=True,include_spring_guard=False)[0])
    assert any(a==spring.HOOK for a,o,n in plan(include_sixty_fps=True)[0])


@pytest.mark.parametrize('luma', [False, True])
def test_existing_60_fps_images_without_retrigger_guard_remain_recognized(luma):
    from ..client.native_dol import plan_for_digest
    old = plan(include_sixty_fps=True, include_luma_colors=luma, include_spring_guard=False)
    assert plan_for_digest(old[2].hex()) == old
