"""Signed boot-time publisher in audited ordinary-function alignment padding.

No exception-vector padding, heap code, or additional Gecko arena. The builder
audits all sites against PAL ELF direct branch/pointer references. Installation
is performed by Riivolution before emulation, never by host memory writes.
"""
import json
import struct
from pathlib import Path
from functools import lru_cache
HOOK=0x805e0ddc
ORIGINAL=0x7f63db78
MAGIC=0x41504845
REGISTRY=0x80002FBC  # guest-owned word before the native ISO signature

@lru_cache(maxsize=2)
def patches(native_registry=False):
    if __package__:
        from ..world_constants import load_data
        sites=load_data('hud_publisher_sites.json')
    else:sites=json.loads((Path(__file__).parents[1]/'data'/'hud_publisher_sites.json').read_text())
    # Slots 120..148 are reserved for the Rocket guards. Slot 149 was unused
    # and supplies the two extra words needed for valid stack-base restores.
    sites=sites[:120]+sites[149:]
    slots=[row['address']+off for row in sites for off in (0,4)]
    code=[];labels={};fix=[]
    def emit(w):code.append(w)
    def d(op,rt,ra,imm):emit(op<<26|rt<<21|ra<<16|(imm&65535))
    def mr(rt,rs):emit(0x7c000378|rs<<21|rt<<16|rs<<11)
    def label(name):labels[name]=len(code)
    def branch(name,condition=0x48000000):
        if condition>>26==16:
            skip='skip'+str(len(code))
            fix.append((len(code),skip,condition^0x01000000));emit(0)
            fix.append((len(code),name,0x48000000));emit(0);label(skip)
        else:fix.append((len(code),name,condition));emit(0)
    def call(address):fix.append((len(code),address,0x48000001));emit(0)
    def cmp(ra,imm):d(11,0,ra,imm)
    d(37,1,1,-0x160);d(47,0,1,0x20)
    for op,offset in ((0x7c000026,0xa0),(0x7c0802a6,0xa4),(0x7c0902a6,0xa8),(0x7c0102a6,0xac)):
        emit(op);d(36,0,1,offset)
    for f in range(14):d(54,f,1,0xb0+f*8)
    d(32,3,27,0x48);d(32,3,3,0);d(15,4,0,0x6170);d(24,4,4,0x5f63)
    emit(0x7c032000);branch('done',0x40820000) # font name starts ap_c
    d(32,30,27,0x40);cmp(30,0);branch('done',0x41820000)
    d(32,3,30,152);d(15,4,0,0x4150);d(24,4,4,0x4d42)
    emit(0x7c032000);branch('done',0x40820000)
    d(32,31,30,4);d(32,3,31,0);d(15,4,0,MAGIC>>16);d(24,4,4,MAGIC&65535)
    emit(0x7c032000);branch('done',0x40820000)
    # 805EB054 calls 805E0C84 with its Layer this in r31. The latter saves
    # r16..r31 at stack+40 before reusing r31 for group traversal. Recover
    # that saved Layer at original stack+7C (our frame adds 160).
    # The controller holds a borrowed two-hop handle, never a refcount owner.
    # This replaces the invalid assumption that Save Select uses stage actors
    # or that an allocator's current heap entry is a stable UI owner.
    if native_registry:
        d(32,3,1,0x1dc);d(36,3,31,16)
        d(15,4,0,REGISTRY>>16);d(36,31,4,REGISTRY&65535)
    d(32,11,31,4);cmp(11,0);branch('done',0x41820000)
    emit(0x71600001);branch('done',0x40820000)
    # Also visit acknowledged casts: alpha converges on the game thread,
    # independently of the host's polling cadence.
    d(34,3,30,143);cmp(3,0);branch('done',0x40820000)
    d(32,4,30,8);cmp(4,0);branch('done',0x41820000)
    d(36,11,1,0x12c)
    # Scene handle supplied by a host-verified live actor. Guest rechecks class.
    d(32,3,4,4);cmp(3,0);branch('done',0x41820000)
    d(32,3,3,0);cmp(3,0);branch('done',0x41820000)
    # Cast lookup takes the unwrapped layer, not its reference handle.
    mr(4,3)
    d(32,3,3,0);d(15,5,0,0x807b);d(14,5,5,-0x43c0)
    emit(0x7c032800);branch('done',0x40820000)
    d(32,5,30,12);d(14,3,1,0x138);call(0x805eb154)
    d(14,3,1,0x138);call(0x805e9ce8);cmp(3,0);branch('release',0x41820000)
    d(36,3,1,0x130);d(32,4,3,12);emit(0x7c04d800);branch('release',0x40820000)
    d(32,4,3,0x34);d(32,4,4,12);emit(0x7c04d000);branch('release',0x40820000)
    d(14,0,0,0);d(36,0,1,0x134)
    # The native text setter builds glyph geometry from the resource's pixel
    # position. Publish X before invoking it, including unchanged headings.
    d(32,0,30,148);d(32,3,27,104);emit(0x7c001800)
    branch('initial_position_same',0x41820000)
    d(36,0,27,104);d(14,0,0,1);d(36,0,1,0x134)
    label('initial_position_same')
    d(32,4,26,0x64);cmp(4,0);branch('have_text',0x40820000)
    d(32,4,27,0x44)
    label('have_text');d(14,3,30,16);call(0x8037b194)
    cmp(3,0);branch('replace_text',0x40820000)
    d(32,3,1,0x134);cmp(3,0);branch('text_same',0x41820000)
    label('replace_text')
    d(14,0,0,1);d(36,0,1,0x134)
    d(32,3,1,0x130);d(14,4,30,16);call(0x805e6888)
    label('text_same')
    # Build the colour on the stack. For unchanged text, fade down at most
    # one alpha unit per draw (~4.25 seconds at 60 Hz), without hiding the cast.
    d(32,0,30,144);d(36,0,1,0x128)
    d(32,3,1,0x134);cmp(3,0);branch('set_colour',0x40820000)
    d(32,4,26,0x78);cmp(4,0);branch('set_colour',0x41820000)
    d(34,3,4,0x1f);d(34,5,30,147);emit(0x7c032800)
    branch('set_colour',0x41800000);branch('set_colour',0x41820000)
    d(14,3,3,-1);d(38,3,1,0x12b)
    label('set_colour')
    d(32,4,26,0x78);cmp(4,0);branch('colour_changed',0x41820000)
    d(32,3,4,0x1c);d(32,5,1,0x128);emit(0x7c032800)
    branch('colour_same',0x41820000)
    label('colour_changed');d(32,3,1,0x130);d(14,4,1,0x128);call(0x805e6734)
    label('colour_same')
    # Pixel X can change with Received/Sent prefix width. Native transform rebuild.
    d(32,0,30,148);d(32,3,27,104);emit(0x7c001800)
    branch('position_same',0x41820000)
    d(14,3,0,1);d(36,3,1,0x134)
    label('position_same');d(36,0,27,104)
    d(32,3,1,0x134);cmp(3,0);branch('no_transform',0x41820000)
    mr(3,26);mr(4,27);d(32,5,1,0x130);d(32,5,5,0x40);cmp(5,0);branch('no_transform',0x41820000);d(32,5,5,12);call(0x805e3198)
    label('no_transform')
    d(32,11,1,0x12c);d(32,3,31,4);emit(0x7c035800);branch('release',0x40820000)
    emit(0x7c0004ac);d(36,11,30,0) # sync before ACK
    # Setter invalidates the scene's composed transform. Do not draw with the
    # old matrix in this frame; the normal scene update rebuilds it next frame.
    d(14,3,1,0x138);d(14,4,0,0);call(0x805e9c68)
    d(32,3,1,0x134);cmp(3,0);branch('done',0x41820000)
    branch('restore_skip')
    label('release');d(14,3,1,0x138);d(14,4,0,0);call(0x805e9c68)
    label('done')
    def restore(target):
        for f in range(14):d(50,f,1,0xb0+f*8)
        for op,offset in ((0x7c0ff120,0xa0),(0x7c0803a6,0xa4),(0x7c0903a6,0xa8),(0x7c0103a6,0xac)):
            d(32,0,1,offset);emit(op)
        d(46,2,1,0x28);d(32,0,1,0x20);d(14,1,1,0x160);emit(ORIGINAL)
        fix.append((len(code),target,0x48000000));emit(0)
    restore(HOOK+4)
    label('restore_skip');restore(0x805e0f50)
    if len(code)>len(slots):raise ValueError('audited publisher padding exhausted')
    for index,target,condition in fix:
        address=slots[labels[target]] if isinstance(target,str) else target
        delta=address-slots[index]
        if condition>>26==16 and not -32768<=delta<=32764:raise ValueError('publisher conditional range')
        code[index]=condition|(delta&(0xfffc if condition>>26==16 else 0x3fffffc))
    result=[(HOOK,ORIGINAL.to_bytes(4,'big'),(0x48000000|((slots[0]-HOOK)&0x3fffffc)).to_bytes(4,'big'))]
    for i in range((len(code)+1)//2):
        chunk=code[i*2:i*2+2]
        while len(chunk)<2:chunk.append(0x60000000)
        next_address=sites[i+1]['address'] if i+1<len(sites) else HOOK+4
        chunk.append(0x48000000|((next_address-(sites[i]['address']+8))&0x3fffffc))
        result.append((sites[i]['address'],b'\0'*12,struct.pack('>3I',*chunk)))
    return result

def installed(memory):
    from .hud_renderer_batch import ADDRESS,replacement
    return (memory.read_bytes(ADDRESS,len(replacement()))==replacement()
            and all(memory.read_bytes(a,len(new))==new for a,old,new in patches(bool(getattr(memory,'native_patch',None)))))

def normalize(memory,data,base):
    plan=[(a,old,new) for a,old,new in patches(bool(getattr(memory,'native_patch',None))) if base<=a and a+len(new)<=base+len(data)]
    if not any(data[a-base:a-base+len(new)]==new for a,old,new in plan):return data
    if not installed(memory):return data
    out=bytearray(data)
    for a,old,new in plan:out[a-base:a-base+len(new)]=old
    return bytes(out)
