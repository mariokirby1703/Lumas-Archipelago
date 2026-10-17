"""Boot-time Rocket fall callback guard sharing the authenticated Diving lock."""
import json
import struct
from pathlib import Path

HOOK=0x8025c478
ORIGINAL=0x9421fff0
LOCK_OFFSET=60
FAST_HOOK=0x8025c6e0
MOVEMENT_MASK_OFFSET=304

def patches():
    return _patches(False)+_patches(True)

def _patches(fast):
    hook=FAST_HOOK if fast else HOOK
    original=0x9421ffe0 if fast else ORIGINAL
    if __package__:
        from ..world_constants import load_data
        sites=load_data('hud_publisher_sites.json')
    else:sites=json.loads((Path(__file__).parents[1]/'data/hud_publisher_sites.json').read_text())
    sites=sites[134:149] if fast else sites[120:134]
    slots=[s['address']+o for s in sites for o in (0,4)]
    code=[];labels={};fix=[]
    def emit(w):code.append(w)
    def d(op,rt,ra,imm):emit(op<<26|rt<<21|ra<<16|(imm&65535))
    def branch(name,op=0x48000000):
        if op>>26==16:
            skip='skip'+str(len(code));fix.append((len(code),skip,op^0x01000000));emit(0)
            fix.append((len(code),name,0x48000000));emit(0);labels[skip]=len(code)
        else:fix.append((len(code),name,op));emit(0)
    if fast:
        d(15,12,0,0x8004);d(14,12,12,-0x6a50) # common movement C2
    else:d(15,12,0,0x8026);d(14,12,12,-0x3fec) # original Diving C2
    d(32,0,12,0)
    emit(21<<26|0<<21|11<<16|6<<11|26<<6|31<<1) # opcode
    d(11,0,11,18);branch('vanilla',0x40820000)
    d(28,0,11,3);branch('vanilla',0x40820000) # relative non-link branch only
    emit(21<<26|0<<21|11<<16|6<<11|0<<6|25<<1) # sign-extend displacement
    emit(31<<26|11<<21|11<<16|6<<11|824<<1) # srawi r11,r11,6
    emit(0x7d8c5a14) # add r12,r12,r11
    if fast:
        d(32,11,12,MOVEMENT_MASK_OFFSET);d(28,11,11,4096)
        branch('vanilla',0x40820000)
        emit(0x4e800020) # no turbo substate, animation or velocity side effects
    else:
        d(32,11,12,LOCK_OFFSET);d(11,0,11,1);branch('vanilla',0x40820000)
        emit(0x7c832378);d(14,4,0,15) # original native Fall request, owned machine r4
        d(15,12,0,0x8003);d(24,12,12,0x3878);emit(0x7d8903a6);emit(0x4e800420)
    labels['vanilla']=len(code);emit(original);branch(hook+4)
    for i,target,op in fix:
        address=slots[labels[target]] if isinstance(target,str) else target
        code[i]=op|((address-slots[i])&(0xfffc if op>>26==16 else 0x3fffffc))
    result=[(hook,original.to_bytes(4,'big'),(0x48000000|((slots[0]-hook)&0x3fffffc)).to_bytes(4,'big'))]
    for i in range((len(code)+1)//2):
        chunk=code[i*2:i*2+2]
        if len(chunk)<2:chunk.append(0x60000000)
        chunk.append(0x48000000|((sites[i+1]['address']-(sites[i]['address']+8))&0x3fffffc))
        result.append((sites[i]['address'],bytes(12),struct.pack('>3I',*chunk)))
    return result

def normalize(memory,data,base):
    plan=patches()
    if not all(memory.read_bytes(a,len(new))==new for a,old,new in plan):return data
    out=bytearray(data)
    for a,old,new in plan:
        if base<=a and a+len(new)<=base+len(out):out[a-base:a-base+len(new)]=old
    return bytes(out)
