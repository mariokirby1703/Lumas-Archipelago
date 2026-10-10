"""Execute generated PPC control flow with explicit native-call stubs.

This tests registers, bounds, calls and duplicate suppression, not real GPU or
collision changes. PAL routines themselves still need live Dolphin validation.
"""
import pytest
from ..client.capsule_refresh import payload_words, ORIGINAL


def run(mode,owned,opened=0,colour=1,special=0,interaction=None,alternate=0,white_control=False,profile=1):
    actor,model,manager,state=0x90010000,0x90020000,0x90030000,0x90040000
    mem={actor:0x80761534,actor+0x110:opened,actor+0x148:special,actor+0x114:colour,
         actor+0xb0:model,actor+0x34:manager,model:0x8077d12c,
         model+8:actor,model+0x88:mode,actor+0x128:0,
         actor+0xb4: 0x90060000 if (mode if interaction is None else interaction) else 0,
         actor+0x149:alternate}
    regs=list(range(32));regs[1]=0x90050000;regs[2]=0x808f0000;regs[31]=actor
    mem[regs[2]-0x7c48]=0x80720000
    original=regs[:];lr,ctr,cr=0x80012345,0x80045678,0x12345678
    initial=(lr,ctr,cr);words=payload_words();pc=0;cmp=0;calls=[]
    from ..client.capsule_refresh import data_offset
    offset=data_offset(words)
    for i,v in enumerate((0x90070000 if white_control else 0,1,int(owned))): mem[offset+i*4]=v
    mem[0x90070000]=profile
    fpr=list(range(100,114));paired=list(range(200,214));fpscr=0x123456;gqr0=0x01010101
    floating=(fpr[:],paired[:],fpscr,gqr0)
    for _ in range(1000):
        w=words[pc];pc+=1
        if w==0:break
        op=w>>26;rt=w>>21&31;ra=w>>16&31;u=w&0xffff;imm=u if u<0x8000 else u-0x10000
        if op in (14,15):regs[rt]=((regs[ra] if ra else 0)+(imm<<(16 if op==15 else 0)))&0xffffffff
        elif op==24:regs[ra]=regs[rt]|u
        elif op in (32,34):regs[rt]=mem.get((regs[ra]+imm)&0xffffffff,0)
        elif op in (36,37):
            addr=(regs[ra]+imm)&0xffffffff;mem[addr]=regs[rt]
            if op==37:regs[ra]=addr
        elif op==54:mem[regs[ra]+imm]=fpr[rt]
        elif op==50:fpr[rt]=mem[regs[ra]+imm]
        elif op==60:mem[regs[ra]+imm]=(fpr[rt],paired[rt])
        elif op==56:fpr[rt],paired[rt]=mem[regs[ra]+imm]
        elif op in (10,11):
            lhs=regs[ra];rhs=u if op==10 else imm
            if op==11 and lhs&0x80000000:lhs-=0x100000000
            cmp=(lhs>rhs)-(lhs<rhs)
        elif op==16:
            kind=w&0xffff0000
            take={0x40820000:cmp!=0,0x41820000:cmp==0,0x41810000:cmp>0}[kind]
            if take:pc=pc-1+(imm//4)
        elif op==18:
            delta=w&0x3fffffc
            if delta&0x2000000:delta-=0x4000000
            if w&1:lr=pc*4
            pc=pc-1+delta//4
        elif w==0x7c0802a6:regs[0]=lr
        elif w==0x7c000026:regs[0]=cr
        elif w==0x7c0902a6:regs[0]=ctr
        elif w==0x7d8802a6:regs[12]=lr
        elif w==0x7d8903a6:ctr=regs[12]
        elif w==0x7c0903a6:ctr=regs[0]
        elif w==0x7c0ff120:cr=regs[0]
        elif w==0x7c0803a6:lr=regs[0]
        elif w==0x7c10e2a6:regs[0]=gqr0
        elif w==0x7c10e3a6:gqr0=regs[0]
        elif w==0xfc00048e:fpr[0]=fpscr
        elif w==0xfdfe058e:fpscr=fpr[0]
        elif w in (0x7c002800,0x7c00f800,0x7c001800):
            lhs=regs[0];rhs=regs[{0x7c002800:5,0x7c00f800:31,0x7c001800:3}[w]]
            cmp=(lhs>rhs)-(lhs<rhs)
        elif op==31 and w&0x7ff==0:
            lhs=regs[ra];rhs=regs[w>>11&31];cmp=(lhs>rhs)-(lhs<rhs)
        elif op==31 and w&0x7ff==0x378:
            rs=w>>21&31;rb=w>>11&31;regs[ra]=regs[rs]|regs[rb]
        elif w==0x4e800421:
            lr=pc*4;calls.append((ctr,regs[3:6]))
            # ABI-permitted native clobbers must not leak into the intercepted
            # caller. Also exercise the caller's argument-home save area.
            fpr[:]=[900]*14;paired[:]=[901]*14;fpscr=902;gqr0=903
            for offset in range(8,0x40,4):mem[regs[1]+offset]=904
            if ctr==0x800132d8:
                assert regs[3]==manager+8;regs[3]=state
            elif ctr==0x8003baac:
                assert regs[3]==state and regs[4]==colour;regs[3]=int(owned)
            elif ctr==0x800d3eb4:
                assert regs[3]==actor and regs[4]==manager and regs[5]==1
                mem[model+0x88]=1
            elif ctr==0x800d3da4:
                assert regs[3]==actor;mem[model+0x88]=0
            elif ctr==0x800d3ff8:
                assert regs[3]==actor and regs[4]==manager and not mem[actor+0xb4]
                mem[actor+0xb4]=0x90060000
            elif ctr==0x800d517c:
                assert regs[3]==actor and regs[4]==1 and mem[actor+0xb4]
                mem[mem[actor+0xb4]+0x54]=1
            elif ctr==0x800d5490:
                assert regs[3]==actor and regs[4] in (0x807613c0,0x807613d8)
            elif ctr==0x800d4298:assert regs[3]==actor
            else:raise AssertionError(hex(ctr))
        elif w==0x60000000:pass
        else:raise AssertionError(hex(w))
    else:raise AssertionError('PPC loop')
    assert regs[1:]==original[1:] and (lr,ctr,cr)==initial
    assert (fpr,paired,fpscr,gqr0)==floating
    assert regs[0]==0 # displaced original lwz r0,128(r31)
    assert mem[actor+0x110]==opened
    if 0x800d517c in [c[0] for c in calls]:
        assert mem[mem[actor+0xb4]+0x54] == 1
    return [c[0] for c in calls],mem[model+0x88]


@pytest.mark.parametrize('colour',range(7))
def test_each_coloured_capsule_uses_native_model_and_state_transition(colour):
    calls,mode=run(0,True,colour=colour)
    assert calls==[0x800132d8,0x8003baac,0x800d3eb4,0x800d3ff8,0x800d517c,0x800d5490,0x800d4298]
    assert mode==1
    calls,mode=run(mode,True,colour=colour)
    assert calls==[0x800132d8,0x8003baac] # no duplicate model or actor creation


def test_revocation_uses_native_ghost_lifecycle_without_collection():
    calls,mode=run(1,False)
    assert calls==[0x800132d8,0x8003baac,0x800d3da4,0x800d5490] and mode==0


@pytest.mark.parametrize('kwargs',[{'opened':1},{'colour':7},{'colour':0xffffffff},{'special':1}])
def test_opened_white_and_special_capsules_are_not_reinitialized(kwargs):
    assert run(0,True,**kwargs)[0]==[]


def test_old_model_only_refresh_repairs_interaction_without_model_replacement():
    calls, mode = run(1, True, interaction=False)
    assert calls == [0x800132d8,0x8003baac,0x800d3ff8,0x800d517c,0x800d5490,0x800d4298]
    assert mode == 1


@pytest.mark.parametrize('colour',[-1,0,1,2,3,4,5,6])
def test_ghost_with_existing_disabled_body_uses_native_registration(colour):
    calls, mode = run(0, True, colour=colour & 0xffffffff,
                      white_control=colour == -1, interaction=True)
    assert mode == 1
    assert 0x800d3ff8 not in calls  # retain the existing body
    assert calls[-3:] == [0x800d517c,0x800d5490,0x800d4298]


def test_alternate_native_capsule_keeps_its_colour_and_receives_interaction():
    calls, mode = run(0, True, colour=5, alternate=1)
    assert 0x800d3ff8 in calls and mode == 1


@pytest.mark.parametrize('opened',[0,1])
def test_white_capsule_permission_is_signed_minus_one_and_preserves_opened(opened):
    calls,mode=run(1,False,colour=0xffffffff,white_control=True,opened=opened)
    assert 0x8003baac not in calls
    assert mode == (1 if opened else 0)
    if not opened:
        assert calls == [0x800132d8,0x800d3da4,0x800d5490]
        calls,mode=run(0,True,colour=0xffffffff,white_control=True)
        assert calls == [0x800132d8,0x800d3eb4,0x800d3ff8,0x800d517c,0x800d5490,0x800d4298]
        assert mode == 1


def test_white_unrelated_save_and_boost_lock_off_keep_vanilla_available():
    assert run(1,False,colour=0xffffffff,white_control=True,profile=2) == ([],1)
    calls,mode=run(1,True,colour=0xffffffff,white_control=True)
    assert calls == [0x800132d8] and mode == 1
