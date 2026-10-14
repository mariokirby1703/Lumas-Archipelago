import struct
from pathlib import Path
import pytest
from ..client import rocket_skydiving as rocket
from ..client.skydiving import payload

@pytest.mark.parametrize('locked',[0,1])
@pytest.mark.parametrize('installed',[False,True])
@pytest.mark.parametrize('fast',[False,True])
def test_rocket_callback_shares_normal_diving_lock(locked,installed,fast):
    instructions={a+i*4:w for a,old,new in rocket.patches()
                  for i,w in enumerate(struct.unpack('>'+'I'*(len(new)//4),new))}
    r=list(range(32));r[1]=0x90001000;r[3]=0x90002000;r[4]=0x90003000
    initial=r[:];target=0x80002c00
    source=0x800395b0 if fast else 0x8025c014
    hook=rocket.FAST_HOOK if fast else rocket.HOOK
    mem={source:(0x48000000|((target-source)&0x3fffffc)) if installed else 0x9421fff0,
         target+(rocket.MOVEMENT_MASK_OFFSET if fast else rocket.LOCK_OFFSET):
             (0 if locked else 4096) if fast else locked}
    pc=hook;eq=False;ctr=0;tail=False
    for _ in range(100):
        if pc==hook+4:break
        w=instructions[pc];at=pc;pc+=4;op=w>>26;rt=w>>21&31;ra=w>>16&31;rb=w>>11&31
        imm=w&65535;imm=imm-65536 if imm&32768 else imm
        if w==0x60000000:continue
        if w==0x7c832378:r[3]=r[4]
        elif w==0x7d8903a6:ctr=r[12]
        elif w==0x4e800420:tail=True;break
        elif w==0x4e800020:tail=True;break
        elif w==0x7d8c5a14:r[12]=(r[12]+r[11])&0xffffffff
        elif op in (14,15):r[rt]=(((r[ra] if ra else 0)+imm) if op==14 else imm<<16)&0xffffffff
        elif op==24:r[ra]=r[rt]|(w&65535)
        elif op==28:r[ra]=r[rt]&(w&65535);eq=r[ra]==0
        elif op==32:r[rt]=mem[r[ra]+imm]
        elif op==37:r[ra]=(r[ra]+imm)&0xffffffff
        elif op==11:eq=r[ra]==imm
        elif op==21:
            shift=rb;mb=w>>6&31;me=w>>1&31
            value=((r[rt]<<shift)|(r[rt]>>(32-shift)))&0xffffffff
            mask=sum(1<<(31-i) for i in range(mb,me+1));r[ra]=value&mask
        elif op==31 and w>>1&1023==824:
            value=r[rt];value=value-(1<<32) if value&0x80000000 else value
            r[ra]=(value>>rb)&0xffffffff
        elif op==16:
            if eq if w>>21&31==12 else not eq:pc=at+imm
        elif op==18:
            off=w&0x3fffffc;off=off-(1<<26) if off&0x2000000 else off;pc=at+off
        else:raise AssertionError(hex(w))
    else:raise AssertionError('did not return')
    assert tail==(installed and locked==1)
    if tail:
        assert r[1]==initial[1]
        if fast:assert r[3:5]==initial[3:5]
        else:assert ctr==0x80033878 and r[3:5]==[initial[4],15]
    else:assert r[3:5]==initial[3:5] and r[1]==initial[1]-(32 if fast else 16)
    assert r[13:]==initial[13:]

def test_boot_patch_original_callback_and_padding_do_not_overlap_hud():
    from ..client.ap_hud_publisher import patches as hud_patches
    assert rocket.LOCK_OFFSET==payload()[1]
    from ..client.movement_gate import payload as movement_payload
    assert rocket.MOVEMENT_MASK_OFFSET==movement_payload()[2]+4
    plan=rocket.patches();occupied={a+i for a,_,new in hud_patches() for i in range(len(new))}
    assert not any(a+i in occupied for a,_,new in plan for i in range(len(new)))
    path=Path(__file__).parents[1]/'notes/Sonic_Colours_PAL_Static_RE_v2/sonic_pal_disassembly.elf'
    if not path.exists():pytest.skip('private PAL ELF absent')
    from ..tools.ppc import Executable
    image=Executable(path)
    assert image.read(0x807766e0+0x34,4)==rocket.HOOK.to_bytes(4,'big')
    for a,old,new in plan:assert image.read(a,len(old))==old
