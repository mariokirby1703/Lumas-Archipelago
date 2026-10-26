from ..tools.private_assets import reference_root
from pathlib import Path
import pytest
from ..client.game_land_native_tint import payload,HOOK,ORIGINAL
from ..tools.ppc import Executable

@pytest.mark.parametrize('available',[0,1])
@pytest.mark.parametrize('group',range(7))
@pytest.mark.parametrize('act',range(3))
def test_native_palette_uses_availability_not_completion(available,group,act):
    words=payload();regs=[0]*32;regs[1]=0x90001000;regs[2]=0x808fc5c0;regs[28]=group;regs[26]=act
    regs[27]=1;pc=0;ctr=0
    for _ in range(40):
        w=words[pc];pc+=1
        if not w:break
        op=w>>26;rt=w>>21&31;ra=w>>16&31;rb=w>>11&31;imm=w&65535
        if imm>=32768:imm-=65536
        if op==14:regs[rt]=((regs[ra] if ra else 0)+imm)&0xffffffff
        elif op==15:regs[rt]=(imm<<16)&0xffffffff
        elif op==24:regs[ra]=regs[rt]|(w&65535)
        elif op==7:regs[rt]=(regs[ra]*imm)&0xffffffff
        elif w==0x7d8903a6:ctr=regs[12]
        elif w==0x4e800421:
            assert ctr==0x8015ee9c
            assert (regs[3],regs[4],regs[5])==(0x9000100c,group+7,act)
            regs[3]=available
        elif op==31 and ((w>>1)&1023)==444:regs[ra]=regs[rt]|regs[rb]
        elif op==31 and ((w>>1)&1023)==266:regs[rt]=(regs[ra]+regs[rb])&0xffffffff
        else:raise AssertionError(hex(w))
    assert regs[27]==regs[2]-(0x14c0 if available else 0x14a8)
    assert regs[5]==group and regs[26]==act and regs[28]==group

def test_native_clear_branch_skips_tint_and_optimized_callers_restore_lr(pal_executable):
    e=pal_executable
    assert int.from_bytes(e.read(HOOK,4),'big')==ORIGINAL
    assert int.from_bytes(e.read(0x802f0da0,4),'big')==0x40820078
    # Each compact probe is inside a native frame that restores LR itself.
    for hook in (0x800cd730,0x8020e208,0x80104d08,0x8025067c,0x80091c60,0x802f1634):
        code=list(e.disassemble(hook+4,0x800))
        assert any(i.mnemonic=='mtlr' and i.op_str=='r0' for i in code),hex(hook)
