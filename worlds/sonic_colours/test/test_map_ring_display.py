"""Execute the emitted PAL UI redirect; native visual rendering is a live test."""
import pytest
from ..client.map_ring_display import payload, HOOK, ORIGINAL
from ..client.native_hook_table import hook_rows


@pytest.mark.parametrize('zone',range(7))
@pytest.mark.parametrize('act',range(1,8))
@pytest.mark.parametrize('status',[1,2,3,4])
def test_native_node_badge_creation_without_faking_clear(zone,act,status):
    regs=list(range(32));regs[0]=status;regs[27]=act;regs[28]=zone
    before=regs[:];words=payload();pc=0;comparison=(status>4)-(status<4);ctr=0;target=HOOK+4
    for _ in range(20):
        w=words[pc];pc+=1
        if w==0:break
        op=w>>26;rt=w>>21&31;ra=w>>16&31;imm=w&65535
        if imm&0x8000:imm-=65536
        if op in (10,11):comparison=(regs[ra]>(w&65535))-(regs[ra]<(w&65535))
        elif op==16:
            take={0x41820000:comparison==0,0x40820000:comparison!=0,0x41810000:comparison>0}[w&0xffff0000]
            if take:pc=pc-1+imm//4
        elif op==18:
            delta=w&0x3fffffc
            if delta&0x2000000:delta-=0x4000000
            pc=pc-1+delta//4
        elif op==15:regs[rt]=((regs[ra] if ra else 0)+(imm<<16))&0xffffffff
        elif op==24:regs[ra]=regs[rt]|(w&65535)
        elif op==14:regs[rt]=regs[ra]+imm
        elif w==0x7d8903a6:ctr=regs[12]
        elif w==0x4e800420:target=ctr;break
        else:raise AssertionError(hex(w))
    draw=status==4 or zone<6 and act<=6
    assert target==(HOOK+4 if draw else 0x80269940)
    assert all(regs[i]==before[i] for i in range(32) if i!=12)
    assert ORIGINAL==0x40820198


def test_native_table_retains_ring_display_hook():
    code=hook_rows()
    assert sum(a==0xc2000000|(HOOK-0x80000000) for a,_ in code)==1
