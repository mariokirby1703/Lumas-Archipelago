import faulthandler
import struct

import pytest

from ..client import quick_step, quick_step_edges as q
from ..client.native_dol import Dol, plan, plan_for_digest
from ..world_constants import load_data


def execute(x, previous, forward=1., permission=1, button=0, index=17, valid_owner=True):
    u = pytest.importorskip('unicorn')
    r = pytest.importorskip('unicorn.ppc_const')
    enabled = faulthandler.is_enabled()
    try:
        faulthandler.disable()
        cpu = u.Uc(u.UC_ARCH_PPC, u.UC_MODE_32 | u.UC_MODE_BIG_ENDIAN)
        cpu.mem_map(0x80000000, 0x1800000)
    finally:
        if enabled:
            faulthandler.enable()
    prior = plan(quick_step_forward=False)
    hook = next(h for h in prior[3] if h['hook'] == quick_step.HOOK)
    control = hook['target'] + quick_step.payload()[1]
    for address, _, raw in q.patches(control, prior[0]):
        cpu.mem_write(address, raw)
    machine, actor, input_address, direction = 0x81000000, 0x81001000, 0x81002000, 0x81008000

    def word(address, value):
        cpu.mem_write(address, struct.pack('>I', value))

    for address, value in ((control, permission), (machine, 0x8075A0F8),
                           (machine + 0x28, actor), (actor, 0x8075AEF8 if valid_owner else 0),
                           (actor + 0x88, input_address), (input_address, 0x8075AF40)):
        word(address, value)
    cpu.mem_write(input_address + 0xC, struct.pack('>ff', x, forward))
    cpu.mem_write(input_address + 0xA8, bytes([index]))
    previous_address = input_address + 0xAC + ((index - 1) & 255) * 0x48
    cpu.mem_write(previous_address, struct.pack('>f', previous))
    cpu.mem_write(direction, b'\x55')
    original = bytes(cpu.mem_read(input_address, 0x48C0))
    saved = {r.UC_PPC_REG_1: 0x81700000, r.UC_PPC_REG_28: machine,
             r.UC_PPC_REG_29: direction, r.UC_PPC_REG_30: 0,
             r.UC_PPC_REG_31: button, r.UC_PPC_REG_LR: 0x8020D62C}
    for register, value in saved.items():
        cpu.reg_write(register, value)
    stops = {q.SUCCESS, q.HOOK + 4}
    cpu.hook_add(u.UC_HOOK_CODE, lambda cpu, address, size, data:
                 cpu.emu_stop() if address in stops else None)
    cpu.emu_start(q.HOOK, 0, count=2000)
    assert bytes(cpu.mem_read(input_address, 0x48C0)) == original
    for register, value in saved.items():
        assert cpu.reg_read(register) == value
    accepted = cpu.reg_read(r.UC_PPC_REG_PC) == q.SUCCESS
    if accepted:
        assert cpu.reg_read(r.UC_PPC_REG_3) == 1
    return accepted, bytes(cpu.mem_read(direction, 1))


@pytest.mark.parametrize('x,previous,direction', [(.609, 0., 1), (-.609, 0., 0),
    (1., .1, 1), (-1., -.1, 0), (.6, -.6, 1), (-.6, .6, 0)])
@pytest.mark.parametrize('forward', [0., -1., 1., .609])
def test_fresh_side_crossing_without_native_flick(x, previous, direction, forward):
    assert execute(x, previous, forward=forward) == (True, bytes([direction]))


@pytest.mark.parametrize('index', [0, 1, 255])
def test_input_history_wrap(index):
    assert execute(.6, 0., index=index) == (True, b'\x01')


@pytest.mark.parametrize('x,previous', [(0., 0.), (.49, 0.), (.6, .6), (-.6, -.6),
    (.6, float('nan')), (float('nan'), 0.), (float('inf'), 0.), (2., 0.)])
def test_held_deadzone_and_invalid_inputs_do_not_repeat(x, previous):
    assert execute(x, previous) == (False, b'\x55')


@pytest.mark.parametrize('permission', [0, 2])
def test_unowned_quick_step_does_not_gain_an_input_route(permission):
    assert execute(.6, 0., permission=permission) == (False, b'\x55')


def test_invalid_owner_and_existing_native_button():
    assert execute(.6, 0., valid_owner=False) == (False, b'\x55')
    assert execute(.6, .6, button=1) == (True, b'\x55')


def test_old_forward_iso_is_still_recognized():
    digest = '180133002c2cf87c6d3b2ab89b3bd472f840f3cfd3ff38c255e2752843e514cc'
    assert plan_for_digest(digest)[2].hex() == digest


@pytest.mark.parametrize('digest', [None, '', '0'*64, 'g'*64, 'abc'])
def test_invalid_native_digest_is_rejected_before_variant_search(digest):
    with pytest.raises(ValueError, match='incompatible native'):
        plan_for_digest(digest)


def test_padding_and_original_entry(pal_dol_bytes):
    image = Dol(pal_dol_bytes)
    assert image.read(q.HOOK, 8) == bytes.fromhex('2c1f000041820104')
    references = set()

    def observe(value, address, code):
        references.add(value)
        if code and value >> 26 in (16, 18):
            mask, sign = (0xFFFC, 0x8000) if value >> 26 == 16 else (0x3FFFFFC, 0x2000000)
            delta = value & mask
            if delta & sign:
                delta -= 2 * sign
            references.add(delta if value & 2 else address + delta)

    for index, _, address, size in image.sections:
        raw = image.read(address, size)
        for offset in range(0, size - 3, 4):
            observe(int.from_bytes(raw[offset:offset+4], 'big'), address + offset, index < 7)
    for fps in (False, True):
        for luma in (False, True):
            prior = plan(include_sixty_fps=fps, include_luma_colors=luma, quick_step_forward=False)
            for address, _, raw in prior[0]:
                for offset in range(0, len(raw)-3, 4):
                    observe(int.from_bytes(raw[offset:offset+4], 'big'), address+offset, True)
    for site in load_data('quick_step_edge_sites.json'):
        anchor, end, address = site['anchor'], site['end'], site['address']
        size = site.get('size', 12)
        assert image.read(anchor-4, 4) == bytes.fromhex(site['before'])
        assert image.read(anchor, end-anchor) == bytes(end-anchor)
        assert anchor <= address and address+size <= end
        assert image.read(end, 4) == bytes.fromhex(site['after'])
        assert not set(range(address, address+size, 4)) & references
