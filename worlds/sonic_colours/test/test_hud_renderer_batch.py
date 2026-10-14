import struct
import pytest
from ..client.hud_renderer_batch import *

@pytest.mark.parametrize('initial',[0,127,128])
def test_actual_ppc_flush_bound_and_vertex_order(initial):
    words=struct.unpack('>41I',replacement());r=[0x12300000+i for i in range(32)]
    r[1]=0x90001000;r[4]=0x90002000;original=list(r);lr=0x80012340;ctr=0;lt=False;eq=False
    mem={COUNTER:initial,RENDERER:0x807abdf8};calls=[]
    for i in range(20):mem[r[4]+i*4]=0xabc00000+i
    pc=0
    for _ in range(400):
        w=words[pc];pc+=1;op=w>>26;rt=w>>21&31;ra=w>>16&31;rb=w>>11&31
        imm=w&65535;imm=imm-65536 if imm&32768 else imm
        if w==0x4e800020:break
        if w==0x60000000:continue
        if w==0x7c0802a6:r[0]=lr
        elif w==0x7c0803a6:lr=r[0]
        elif w==0x7d2903a6:ctr=r[9]
        elif op in (14,15):r[rt]=(((r[ra] if ra else 0)+imm) if op==14 else imm<<16)&0xffffffff
        elif op==24:r[ra]=r[rt]|(w&65535)
        elif op==7:r[rt]=(r[ra]*imm)&0xffffffff
        elif op in (32,36,37):
            address=((r[ra] if ra else 0)+imm)&0xffffffff
            if op==32:r[rt]=mem.get(address,0)
            else:mem[address]=r[rt]
            if op==37:r[ra]=address
        elif op in (46,47):
            address=r[ra]+imm
            for reg in range(rt,32):
                if op==46:r[reg]=mem.get(address,0)
                else:mem[address]=r[reg]
                address+=4
        elif op in (10,11):
            a=r[ra];b=(w&65535) if op==10 else imm
            lt=a<b;eq=a==b
        elif op==31:
            xo=w>>1&1023
            if xo==266:r[rt]=(r[ra]+r[rb])&0xffffffff
            elif xo==444:r[ra]=r[rt]|r[rb]
            else:raise AssertionError(hex(w))
        elif op==21:
            sh=w>>11&31;mb=w>>6&31;me=w>>1&31
            value=((r[rt]<<sh)|(r[rt]>>(32-sh if sh else 32)))&0xffffffff
            mask=sum(1<<(31-i) for i in range(32) if (mb<=i<=me if mb<=me else i>=mb or i<=me))
            r[ra]=value&mask
        elif op==16:
            bo=w>>21&31;bi=w>>16&31
            if bo==16:ctr-=1;take=ctr!=0
            elif bo==12:take=lt if bi==0 else eq
            elif bo==4:take=not eq
            else:raise AssertionError(hex(w))
            if take:pc=pc-1+imm//4
        elif op==18:
            assert ADDRESS+(pc-1)*4+(w&0x3fffffc)==0x805ec784
            assert mem[COUNTER]==128;calls.append('flush')
            # Real native flush has arbitrary volatile registers.
            lr=ADDRESS+pc*4
            for reg in range(3,13):r[reg]=0xf0000000+reg
        else:raise AssertionError(hex(w))
    else:raise AssertionError('PPC loop did not return')
    offset=0 if initial==128 else initial
    result=[mem[BUFFER+offset*80+i*4] for i in range(20)]
    assert result==[0xabc00000+i for vertex in (0,2,3,1) for i in range(vertex*5,vertex*5+5)]
    assert mem[COUNTER]==offset+1 and mem[RENDERER]==0x807abdf8
    assert calls==(['flush'] if initial==128 else [])
    assert r[1]==original[1] and r[29:]==original[29:] and lr==0x80012340

def test_exact_revision_normalization_and_capacity():
    assert BUFFER+CAPACITY*80==COUNTER and COUNTER<RENDERER
    assert normalize(None,replacement(),ADDRESS)==bytes.fromhex(ORIGINAL_HEX)
    altered=bytearray(replacement());altered[0]^=1
    assert normalize(None,bytes(altered),ADDRESS)==bytes(altered)
