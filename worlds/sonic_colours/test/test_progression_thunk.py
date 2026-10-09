"""Execute the emitted native interception, including its mutable data block.

This validates PPC behavior; it does not substitute for gameplay validation.
"""
import pytest
from ..client.progression_hook import payload


def execute(bit, value, worlds=1<<20, colours=0, bound=True, discoveries=0, clears=0):
    words, data = payload()
    origin=0x80002000
    actor, flags=0x90010000,0x90020000
    regs=list(range(32));regs[1]=0x90030000;regs[3]=actor;regs[4]=bit;regs[5]=value
    original=regs[:];lr=0x80011234;cr=0x12345678;oldlr=lr
    mem={actor:flags,origin+data:flags if bound else 0,origin+data+4:worlds,
         origin+data+8:colours,origin+data+12:discoveries,origin+data+16:clears}
    pc=0;cmp=0
    for _ in range(300):
        w=words[pc];pc+=1
        if w==0:break
        op=w>>26;rt=w>>21&31;ra=w>>16&31;rb=w>>11&31;u=w&65535;imm=u if u<32768 else u-65536
        if op==14:regs[rt]=((regs[ra] if ra else 0)+imm)&0xffffffff
        elif op in (32,36,37):
            addr=(regs[ra]+imm)&0xffffffff
            if op==32:regs[rt]=mem.get(addr,0)
            else:
                mem[addr]=regs[rt]
                if op==37:regs[ra]=addr
        elif op in (10,11):
            lhs=regs[ra];rhs=u if op==10 else imm
            if op==11 and lhs&0x80000000:lhs-=0x100000000
            cmp=(lhs>rhs)-(lhs<rhs)
        elif op==16:
            take={0x40820000:cmp!=0,0x41820000:cmp==0,0x41810000:cmp>0,
                  0x40810000:cmp<=0,0x41800000:cmp<0}[w&0xffff0000]
            if take:pc=pc-1+imm//4
        elif op==18:
            delta=w&0x3fffffc
            if delta&0x2000000:delta-=0x4000000
            if w&1:lr=origin+pc*4
            pc=pc-1+delta//4
        elif w==0x7c0802a6:regs[0]=lr
        elif w==0x7c000026:regs[0]=cr
        elif w==0x7d8802a6:regs[12]=lr
        elif w==0x7c0ff120:cr=regs[0]
        elif w==0x7c0803a6:lr=regs[0]
        elif w==0x7c063800:cmp=(regs[6]>regs[7])-(regs[6]<regs[7])
        elif op==31 and w&0x7ff==0x30:regs[ra]=(regs[rt]<<(regs[rb]&31))&0xffffffff
        elif op==31 and w&0x7ff==0x378:regs[ra]=regs[rt]|regs[rb]
        elif op==31 and w&0x7ff==0x38:regs[ra]=regs[rt]&regs[rb]
        elif w==0x60000000:pass
        else:raise AssertionError(hex(w))
    else:raise AssertionError('PPC loop')
    assert regs[1:5]==original[1:5] and regs[6:]==original[6:]
    assert lr==oldlr and cr==0x12345678
    assert cmp==(regs[5]>0)-(regs[5]<0) # displaced cmpwi r5,0
    return regs[5],mem[origin+data+12],mem[origin+data+16]


@pytest.mark.parametrize('zone',range(7))
def test_native_vanilla_world_grant_is_replaced_with_ap_ownership(zone):
    bit=20+zone
    assert execute(bit,1,worlds=0)[0]==0
    assert execute(bit,0,worlds=1<<bit)[0]==1
    assert execute(bit,1,bound=False)[0]==1


@pytest.mark.parametrize('colour',range(7))
def test_discovery_event_survives_denied_permission_without_granting_wisp(colour):
    assert execute(colour,1,colours=0)==(0,1<<colour,0)
    assert execute(colour,0,colours=1<<colour)==(1,0,0)
    assert execute(colour,1,discoveries=0x7f)[1]==0x7f


def test_super_is_only_ap_owned_and_does_not_create_discovery():
    assert execute(7,1,colours=0)==(0,0,0)
    assert execute(7,0,colours=0x80)==(1,0,0)


@pytest.mark.parametrize('bit',range(252,273))
def test_game_land_clear_event_is_monotonic_and_does_not_modify_clear(bit):
    assert execute(bit,1)==(1,0,1<<(bit-252))
    assert execute(bit,0)==(0,0,0)
    assert execute(bit,1,clears=0x1fffff)[2]==0x1fffff


@pytest.mark.parametrize('bit',[8,19,27,30,90,150,251,273,400])
def test_unrelated_flags_keep_vanilla_value(bit):
    assert execute(bit,1)==(1,0,0)
    assert execute(bit,0)==(0,0,0)
