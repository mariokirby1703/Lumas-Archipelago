from ..tools.private_assets import reference_root
import struct
import pytest
from ..client.ap_hud_publisher import patches,HOOK,ORIGINAL,MAGIC

def test_cast_lookup_abi_matches_original_native_caller():
    from pathlib import Path
    from ..tools.ppc import Executable
    path=reference_root()/'Sonic_Colours_PAL_Static_RE_v2/sonic_pal_disassembly.elf'
    if not path.exists():pytest.skip('private PAL ELF unavailable')
    image=Executable(path)
    # Original bonus caller unwraps its scene handle, then passes that result
    # as r4. The lookup accesses the layer's layout at +0xc, not handle data.
    assert image.read(0x80111290,4)==bytes.fromhex('484d8a59')
    assert image.read(0x80111298,4)==bytes.fromhex('7c641b78')
    assert image.read(0x805eb22c,4)==bytes.fromhex('8084000c')

def test_padding_is_ordinary_function_alignment_and_not_an_existing_branch_target():
    from pathlib import Path
    from ..tools.ppc import Executable
    path=reference_root()/'Sonic_Colours_PAL_Static_RE_v2/sonic_pal_disassembly.elf'
    if not path.exists():pytest.skip('private PAL ELF unavailable')
    image=Executable(path);plan=patches();occupied={a+i for a,old,new in plan[1:] for i in range(0,12,4)}
    assert image.read(HOOK,4)==ORIGINAL.to_bytes(4,'big')
    for a,old,new in plan[1:]:
        assert 0x80330000<a<0x80500000 and image.read(a,12)==old==b'\0'*12
        assert image.read(a-4,4)==bytes.fromhex('4e800020')
        assert image.read(a+12,1)==b'\x94'
    for section in image.sections:
        if section[1]!=1:continue
        blob=image.data[section[4]:section[4]+section[5]]
        for i in range(0,len(blob)-3,4):
            word=struct.unpack_from('>I',blob,i)[0]
            assert word not in occupied
            if section[2]&4 and word>>26 in (16,18):
                width=16 if word>>26==16 else 26;offset=word&((1<<width)-4)
                if offset&(1<<(width-1)):offset-=1<<width
                target=(offset if word&2 else section[3]+i+offset)&0xffffffff
                assert target not in occupied

@pytest.mark.parametrize('moved', [False,True])
@pytest.mark.parametrize('same_text', [False,True])
@pytest.mark.parametrize('target_alpha', [128,255])
@pytest.mark.parametrize('generation,ack,layer_class,expected',[(2,0,0x807abc40,True),(3,0,0x807abc40,False),(2,2,0x807abc40,True),(2,0,0,False)])
def test_guest_native_setter_ack_and_register_preservation(generation,ack,layer_class,expected,same_text,target_alpha,moved):
    instructions={a+i*4:w for a,old,new in patches() for i,w in enumerate(struct.unpack('>'+'I'*(len(new)//4),new))}
    r=[0x11000000+i for i in range(32)];r[1]=0x900f0000;r[26]=0x90002000;r[27]=0x90001000
    before=list(r);f=[100.+i for i in range(32)];fb=list(f);lr=0x80054320;ctr=0x1234;xer=0x5678
    cr=0x12345678;eq=False;lt=False
    mem={0x90001048:0x90005000,0x90005000:0x61705f63,0x90001040:0x90003000,
         0x90003004:0x90004000,0x90004000:MAGIC,0x90004004:generation,0x90003000:ack,
         0x90003008:0x90006000,0x90006004:0x90007000,0x90007000:0x90008000,
         0x90008000:layer_class,0x9000300c:0x9000d000,
         0x9000900c:0x90001000,0x90009034:0x9000a000,0x9000a00c:0x90002000,
         0x90009040:0x9000b000,0x9000b00c:0x9000c000,0x90003094:0x42500000,0x90003098:0x41504d42}
    mem.update({0x90001068:0x42500000,0x90002078:0x9000f000,
                0x9000f01c:0xaf70ffff,0x90003090:0xaf70ff00|target_alpha})
    desired_x=0x44160000 if moved else 0x42500000
    mem[0x90003094]=desired_x
    refreshed=not same_text or moved
    calls=[];saved_f={};pc=HOOK
    for _ in range(1000):
        if pc in (HOOK+4,0x805e0f50):break
        w=instructions[pc];at=pc;pc+=4;op=w>>26;rt=w>>21&31;ra=w>>16&31;rb=w>>11&31
        imm=w&65535;imm=imm-65536 if imm&32768 else imm
        if w==0x60000000:continue
        if w==0x7c000026:r[0]=cr
        elif w==0x7c0802a6:r[0]=lr
        elif w==0x7c0902a6:r[0]=ctr
        elif w==0x7c0102a6:r[0]=xer
        elif w==0x7c0ff120:cr=r[0];lt=bool(cr&0x80000000);eq=bool(cr&0x20000000)
        elif w==0x7c0803a6:lr=r[0]
        elif w==0x7c0903a6:ctr=r[0]
        elif w==0x7c0103a6:xer=r[0]
        elif w==0x7c0004ac:pass
        elif op in (14,15):r[rt]=(((r[ra] if ra else 0)+imm) if op==14 else imm<<16)&0xffffffff
        elif op==24:r[ra]=r[rt]|(w&65535)
        elif op in (32,34,36,37,38):
            address=((r[ra] if ra else 0)+imm)&0xffffffff
            if op==32:r[rt]=mem.get(address,0)
            elif op==34:r[rt]=(mem.get(address&~3,0)>>(24-8*(address&3)))&255
            elif op==38:
                shift=24-8*(address&3);base=address&~3
                mem[base]=(mem.get(base,0)&~(255<<shift))|((r[rt]&255)<<shift)
            else:mem[address]=r[rt]
            if op==37:r[ra]=address
        elif op in (46,47):
            if op==46:assert ra<rt, 'invalid lmw: base register is in load range'
            address=r[ra]+imm
            for reg in range(rt,32):
                if op==46:r[reg]=mem[address]
                else:mem[address]=r[reg]
                address+=4
        elif op in (50,54):
            address=r[ra]+imm
            if op==50:f[rt]=saved_f[address]
            else:saved_f[address]=f[rt]
        elif op==28:
            r[ra]=r[rt]&(w&65535);lt=False;eq=r[ra]==0;cr=(cr&0xfffffff)|(0x20000000 if eq else 0x40000000)
        elif op==11:
            lt=r[ra]<imm;eq=r[ra]==imm;cr=(cr&0xfffffff)|(0x80000000 if lt else 0x20000000 if eq else 0x40000000)
        elif op==31:
            xo=w>>1&1023
            if xo==444:r[ra]=r[rt]|r[rb]
            elif xo==0:
                lt=r[ra]<r[rb];eq=r[ra]==r[rb];cr=(cr&0xfffffff)|(0x80000000 if lt else 0x20000000 if eq else 0x40000000)
            else:raise AssertionError(hex(w))
        elif op==16:
            bo=w>>21&31;bi=w>>16&31;condition=lt if bi==0 else eq
            if (condition if bo==12 else not condition):pc=at+imm
        elif op==18:
            off=w&0x3fffffc;off=off-(1<<26) if off&0x2000000 else off;target=at+off
            if w&1:
                lr=pc;args=tuple(r[3:6]);calls.append(target)
                if target==0x805eb154:
                    assert args[1:]==(0x90008000,0x9000d000)
                    mem[args[0]+4]=0x9000e000;mem[0x9000e000]=0x90009000;ret=args[0]
                elif target==0x805e9ce8:ret=0x90009000
                elif target==0x8037b194:ret=0 if same_text else 1
                elif target==0x805e6888:
                    assert args[:2]==(0x90009000,0x90003010)
                    assert mem[0x90001068]==desired_x # Position precedes native geometry allocation.
                    ret=0
                elif target==0x805e6734:
                    assert args[:2]==(0x90009000,before[1]-0x160+0x128)
                    assert mem[args[1]]==(0xaf70fffe if not refreshed else 0xaf70ff00|target_alpha)
                    ret=0
                elif target==0x805e3198:assert args==(0x90002000,0x90001000,0x9000c000);ret=0
                elif target==0x805e9c68:assert args[1]==0;ret=0
                else:raise AssertionError(hex(target))
                for reg in range(3,13):r[reg]=0xf0000000+reg
                r[3]=ret;ctr=0xff;xer=0xaa;cr=0xffffffff;eq=True;lt=True
                for reg in range(14):f[reg]=-1.
            else:pc=target
        else:raise AssertionError(hex(w))
    else:raise AssertionError('publisher did not return')
    assert (0x805e6888 in calls)==(expected and refreshed)
    assert (0x805e3198 in calls)==(expected and refreshed)
    assert (0x805e6734 in calls)==(expected and target_alpha!=255)
    assert pc==(0x805e0f50 if expected and refreshed else HOOK+4)
    assert mem[0x90003000]==(generation if expected else ack)
    assert r[:3]==before[:3] and r[4:]==before[4:] and r[3]==before[27]
    assert f==fb and lr==0x80054320 and ctr==0x1234 and xer==0x5678 and cr==0x12345678
