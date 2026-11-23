import faulthandler
import struct

import pytest

from ..client import quick_step,quick_step_forward as q
from ..client.native_dol import plan,Dol
from ..world_constants import load_data


@pytest.mark.parametrize('permission,forward,accepted', [(1,.6,True),(1,-.6,True),(1,1.,True),
    (1,0.,False),(1,-0.,False),(0,.6,False),(2,.6,False),(1,float('nan'),False),
    (1,float('inf'),False),(1,2.,False)])
def test_forward_diagonal_only_bypasses_heading_check_after_ownership(permission,forward,accepted):
    u=pytest.importorskip('unicorn');r=pytest.importorskip('unicorn.ppc_const')
    cpu=u.Uc(u.UC_ARCH_PPC,u.UC_MODE_32|u.UC_MODE_BIG_ENDIAN)
    enabled=faulthandler.is_enabled()
    try:
        faulthandler.disable();cpu.mem_map(0x80000000,0x1800000)
    finally:
        if enabled:faulthandler.enable()
    prior=plan(quick_step_forward=False)
    hook=next(h for h in prior[3] if h['hook']==quick_step.HOOK)
    control=hook['target']+quick_step.payload()[1]
    for address,_,raw in q.patches(control,prior[0]):cpu.mem_write(address,raw)
    machine,actor,input=0x81000000,0x81001000,0x81002000
    def word(address,value):cpu.mem_write(address,struct.pack('>I',value))
    for address,value in ((control,permission),(machine,0x8075A0F8),(machine+0x28,actor),
                          (actor,0x8075AEF8),(actor+0x88,input),(input,0x8075AF40)):
        word(address,value)
    cpu.mem_write(input+0xc,struct.pack('>3f',.6,forward,0.))
    word(input+0x4c,4)
    original=bytes(cpu.mem_read(input,0x60))
    saved={r.UC_PPC_REG_1:0x81700000,r.UC_PPC_REG_28:machine,r.UC_PPC_REG_29:0x81003000,
           r.UC_PPC_REG_30:0,r.UC_PPC_REG_31:1,r.UC_PPC_REG_LR:0x8020D62C}
    for register,value in saved.items():cpu.reg_write(register,value)
    stop=q.SUCCESS if accepted else q.HOOK+4
    cpu.emu_start(q.HOOK,stop,count=1000)
    assert cpu.reg_read(r.UC_PPC_REG_PC)==stop
    assert cpu.reg_read(r.UC_PPC_REG_3)==(1 if accepted else machine)
    assert bytes(cpu.mem_read(input,0x60))==original
    for register,value in saved.items():assert cpu.reg_read(register)==value


def test_native_side_action_and_form_checks_still_precede_override(pal_dol_bytes):
    image=Dol(pal_dol_bytes)
    assert image.read(q.HOOK,4)==q.ORIGINAL.to_bytes(4,'big')
    assert image.read(q.HOOK-8,8)==bytes.fromhex('2c1f000041820104')
    references=set()
    def observe(value,address,is_code):
        references.add(value)
        if is_code and value>>26 in (16,18):
            mask,sign=(0xfffc,0x8000) if value>>26==16 else (0x3fffffc,0x2000000)
            delta=value&mask
            if delta&sign:delta-=2*sign
            references.add(delta if value&2 else address+delta)
    for index,offset,address,size in image.sections:
        raw=image.read(address,size)
        for k in range(0,size-3,4):observe(int.from_bytes(raw[k:k+4],'big'),address+k,index<7)
    for address,_,raw in plan(include_sixty_fps=True,include_luma_colors=True,quick_step_forward=False)[0]:
        for k in range(0,len(raw)-3,4):observe(int.from_bytes(raw[k:k+4],'big'),address+k,True)
    for site in load_data('quick_step_forward_sites.json'):
        anchor,end,address=site['anchor'],site['end'],site['address']
        assert image.read(anchor-4,4)==bytes.fromhex(site['before'])
        assert image.read(anchor,end-anchor)==bytes(end-anchor)
        assert anchor<=address and address+12<=end
        assert image.read(end,4)==bytes.fromhex(site['after'])
        assert not set(range(address,address+12,4))&references
