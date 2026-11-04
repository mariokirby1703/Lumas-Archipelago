"""Apply seeded ring materials during native model creation, before drawing."""
from functools import lru_cache
import struct

from .capsule_refresh import PPC
from .item_colors import LUMA
from ..world_constants import load_data

HOOK = 0x801D52F0
ORIGINAL = 0x901C00B4
COPY_MATERIAL = 0x805BC810
CACHE_FLUSH = 0x8033B130
MAGIC = 0x52524331
MAGIC_V2 = 0x52524332
MAGIC_LUMA = 0x52524C31
PALETTE = ('red','purple','blue','light_blue','gold','accessible_blue','gray','orange')
RGB = ((0,0,0),(175,112,255),(48,91,216),(100,200,255),
       (240,228,66),(0,114,178),(153,153,153),(213,94,0))

LUMA_PALETTE = PALETTE[:4] + tuple('luma_' + name for name in LUMA)
LUMA_RGB = RGB[:4] + tuple(tuple(bytes.fromhex(color[1:])) for color in LUMA.values())


def missions():
    return tuple(sorted({row['mission_id'] for row in load_data('red_rings.json')}))


def encode(colors,extended=True,luma=False):
    palette=(LUMA_PALETTE if luma else PALETTE) if extended else PALETTE[:4]
    if not isinstance(colors,(tuple,list)) or len(colors) != 5 or any(c not in palette for c in colors):
        raise ValueError('five valid Red Ring colors required')
    return 0x8000 | sum(palette.index(c) << ((3 if extended else 2)*i) for i,c in enumerate(colors))


def validate_colors(colors,luma=False):
    if colors is None:return None
    if not isinstance(colors,dict) or set(colors) != set(missions()):
        raise ValueError('complete normal-Act Red Ring colors required')
    for row in colors.values():encode(row,luma=luma)
    return colors


def program(header, first, extended=False, table=0, luma=False):
    a = PPC()
    def const(r,v):
        a.d(15,r,0,(v>>16)&65535);a.d(24,r,r,v&65535)
    def check(r,value):
        const(10,value);a.emit(0x7C000000 | r<<16 | 10<<11);a.branch('done',0x40820000)
    def load(r,owner,offset):
        a.d(32,r,owner,offset);a.d(11,0,r,0);a.branch('done',0x41820000)
    a.emit(ORIGINAL)
    # SDK callees may use the caller's linkage/argument area at SP+4..2C.
    a.d(37,1,1,-0x140);a.d(36,0,1,0x30)
    for instruction,offset in ((0x7C000026,0x34),(0x7C0802A6,0x38),(0x7C0902A6,0x3C)):
        a.emit(instruction);a.d(36,0,1,offset)
    a.d(47,3,1,0x40)
    for f in range(14):a.d(54,f,1,0xC0+f*8)
    const(14,header);a.d(32,3,14,0);check(3,MAGIC_LUMA if luma else MAGIC_V2 if extended else MAGIC)
    a.d(32,19,14,4);a.d(11,0,19,0);a.branch('done',0x41820000)
    a.d(28,19,3,1);a.branch('done',0x40820000)
    a.emit(0x7C0004AC)
    a.d(32,3,28,0);check(3,0x8076F8D0)
    const(3,0x808F336C);load(3,3,0);load(3,3,4);load(3,3,0x1C);load(3,3,0x34)
    a.d(32,4,3,0);check(4,0x80759438);load(4,3,0x4C)
    # All normal Act identifiers are stg followed by three decimal digits.
    a.d(34,15,4,3);a.d(14,15,15,-48);a.d(10,0,15,9);a.branch('done',0x41810000)
    a.d(34,5,4,4);a.d(14,5,5,-48);a.d(10,0,5,9);a.branch('done',0x41810000)
    a.d(34,6,4,5);a.d(14,6,6,-48);a.d(10,0,6,9);a.branch('done',0x41810000)
    a.d(7,15,15,100);a.d(7,5,5,10)
    a.emit(0x7C000214 | 15<<21 | 15<<16 | 5<<11)
    a.emit(0x7C000214 | 15<<21 | 15<<16 | 6<<11)
    const(16,first);a.d(14,18,0,36)
    a.label('find');a.d(40,3,16,0);a.emit(0x7C000000 | 15<<16 | 3<<11)
    a.branch('found',0x41820000)
    load(16,16,4);a.d(14,18,18,-1);a.d(11,0,18,0);a.branch('find',0x40820000)
    a.branch('done')
    a.label('found');a.d(40,15,16,2)
    a.d(28,15,3,0x8000);a.branch('done',0x41820000)
    load(3,28,0x64);load(3,3,8);a.d(32,4,3,0x24)
    a.d(10,0,4,4);a.branch('done',0x41810000)
    a.d(7,4,4,3 if extended else 2);a.emit(0x7C000430 | 15<<21 | 15<<16 | 4<<11)
    a.d(28,15,15,7 if extended else 3);a.branch('done',0x41820000)
    load(3,28,0xB4);load(14,3,0x1C)
    a.d(32,4,14,0);check(4,0x807AA950)
    load(16,14,0x168);load(17,14,0x174);load(18,14,0x140)
    a.emit(0x7C0004AC);const(3,header);a.d(32,3,3,4)
    a.emit(0x7C000000 | 3<<16 | 19<<11);a.branch('done',0x40820000)
    # SDK copy initializes the private display lists and fixes their metadata.
    a.mr(3,14);a.d(14,4,0,0);a.d(14,5,0,0x900);a.call(COPY_MATERIAL)
    if extended:
        const(14,table)
        a.label('color_next');a.d(32,14,14,4)
        a.d(14,15,15,-1);a.d(11,0,15,0);a.branch('color_next',0x40820000)
        a.d(34,3,14,0);a.d(38,3,16,68)
        a.d(34,3,14,1)
        a.emit(0x5464E13E)  # srwi r4,r3,4
        a.d(24,4,4,0x80);a.d(38,4,16,71)
        a.emit(0x54632036)  # slwi r3,r3,4
        a.d(38,3,16,72)
        a.d(34,3,14,2);a.d(38,3,16,73)
    else:
        a.d(11,0,15,1);a.branch('purple',0x41820000)
        a.d(11,0,15,2);a.branch('blue',0x41820000)
        for label,color in (('light',3),('purple',1),('blue',2)):
            a.label(label)
            red,green,blue = RGB[color]
            for offset,value in ((68,red),(71,0x80|(green>>4)),(72,(green&15)<<4),(73,blue)):
                a.d(14,3,0,value);a.d(38,3,16,offset)
            a.branch('shader')
    a.label('shader')
    for offset,value in ((101,0),(111,12),(210,252),(233,192),(258,140)):
        a.d(14,3,0,value);a.d(38,3,17,offset)
    for pointer,length in ((16,128),(17,512)):
        a.mr(3,pointer);a.d(14,4,0,length);a.call(CACHE_FLUSH)
    a.emit(0x7C0004AC)
    a.label('done')
    for f in range(14):a.d(50,f,1,0xC0+f*8)
    a.d(46,3,1,0x40)
    for offset,instruction in ((0x3C,0x7C0903A6),(0x38,0x7C0803A6),(0x34,0x7C0FF120)):
        a.d(32,0,1,offset);a.emit(instruction)
    a.d(32,0,1,0x30);a.d(14,1,1,0x140);a.emit(0)
    return a.finish()


def scatter(words, sites, return_address=None, exits=None):
    from .native_dol import branch
    return_address = HOOK+4 if return_address is None else return_address
    exits = exits or {}
    lengths = [11 if w>>26==16 and (w>>21)&31==4 else 10 if w>>26==16 else 1 for w in words]
    if sum(lengths)>len(sites):raise ValueError('Red Ring spawn padding exhausted')
    offsets=[];count=0
    for length in lengths:offsets.append(count);count+=length
    positions=[sites[i]['address'] for i in offsets]
    result=[]
    for index,word in enumerate(words):
        start=offsets[index];op=word>>26
        if index in exits or index==len(words)-1:
            emitted=[branch(sites[start]['address'],exits.get(index,return_address))]
        elif op==16:
            bo,bi=(word>>21)&31,(word>>16)&31
            if bo not in (4,12):raise ValueError('unsupported spawn branch condition')
            delta=word&0xFFFC
            if delta&0x8000:delta-=0x10000
            target=positions[index+delta//4];following=positions[index+1]
            difference=(target-following)&0xFFFFFFFF
            emitted=[0x7D800026,21<<26 | 12<<21 | 12<<16 | ((bi+1)%32)<<11 | 31<<6 | 31<<1]
            if bo==4:emitted.append(26<<26 | 12<<21 | 12<<16 | 1)
            emitted += [15<<26 | 11<<21 | difference>>16,24<<26 | 11<<21 | 11<<16 | difference&65535,
                        0x7C0001D6 | 12<<21 | 12<<16 | 11<<11,
                        15<<26 | 11<<21 | following>>16,24<<26 | 11<<21 | 11<<16 | following&65535,
                        0x7C000214 | 12<<21 | 11<<16 | 12<<11,0x7D8903A6,0x4E800420]
        elif op==18:
            delta=word&0x3FFFFFC
            if delta&0x2000000:delta-=0x4000000
            emitted=[branch(sites[start]['address'],positions[index+delta//4])]
        else:emitted=[word]
        if len(emitted)!=lengths[index]:raise ValueError('spawn branch expansion length')
        for j,instruction in enumerate(emitted):
            address=sites[start+j]['address']
            following=sites[start+j+1]['address'] if start+j+1<count else return_address
            result.append((address,bytes(8),struct.pack('>II',instruction,branch(address+4,following))))
    return result


@lru_cache(maxsize=1)
def layout():
    from .native_dol import plan
    occupied=plan(include_ring_spawn=False,include_boot_guards=False,include_accessible_colors=False)[0]
    sites=[s for s in load_data('red_ring_spawn_sites.json')
           if not any(a<s['address']+8 and s['address']<a+len(n) for a,o,n in occupied)]
    names=missions();header=sites[0]['address'];rows={name:sites[i+1]['address'] for i,name in enumerate(names)}
    code=sites[len(names)+1:]
    return header,rows,code


@lru_cache(maxsize=4)
def patches(extended=True,luma=False):
    from .native_dol import branch
    header,rows,sites=layout()
    result=[(header,bytes(8),struct.pack('>II',MAGIC_LUMA if luma else MAGIC_V2 if extended else MAGIC,0))]
    names=tuple(rows)
    for i,(name,address) in enumerate(rows.items()):
        following=rows[names[i+1]] if i+1<len(names) else 0
        result.append((address,bytes(8),struct.pack('>HHI',int(name[3:]),0,following)))
    table=0
    if extended:
        colors,sites=sites[:8],sites[8:]
        table=colors[0]['address']
        for i,(red,green,blue) in enumerate(LUMA_RGB if luma else RGB):
            following=colors[i+1]['address'] if i<7 else 0
            result.append((colors[i]['address'],bytes(8),struct.pack('>4BI',red,green,blue,0,following)))
    code=scatter(program(header,next(iter(rows.values())),extended,table,luma),sites)
    return result+[(HOOK,ORIGINAL.to_bytes(4,'big'),branch(HOOK,code[0][0]).to_bytes(4,'big'))]+code


def normalized(address, observed, expected, extended=True):
    header,rows,_=layout()
    if address==header:
        if len(observed)!=8 or observed[:4]!=expected[:4]:
            raise ValueError('invalid native ring color header')
        return expected
    if address in rows.values():
        flags=int.from_bytes(observed[2:4],'big')
        if observed[:2]!=expected[:2] or observed[4:]!=expected[4:] or flags&~(0xFFFF if extended else 0x83FF) or flags and not flags&0x8000:
            raise ValueError('invalid native ring color row')
        return expected
    return observed


def prefill(address, expected, colors,luma=False):
    header,rows,_=layout()
    if colors is not None and address==header:return expected[:4]+(2).to_bytes(4,'big')
    for mission,slot in rows.items():
        if colors is not None and address==slot:return expected[:2]+encode(colors[mission],luma=luma).to_bytes(2,'big')+expected[4:]
    return expected


def normalize(memory, data, base):
    if not (getattr(memory,'native_patch',None) or {}).get('red_ring_spawn'):return data
    data=bytearray(data)
    extended=(getattr(memory,'native_patch',None) or {}).get('accessible_ring_colors',False)
    for address,old,new in patches(extended,bool(memory.native_patch.get('luma_ring_colors'))):
        if base<=address and address+len(new)<=base+len(data):
            offset=address-base
            if normalized(address,bytes(data[offset:offset+len(new)]),new,extended)!=new:
                raise memory.error('native ring spawn code changed')
            data[offset:offset+len(old)]=old
    return data


def publish(runtime,memory):
    from .memory import MemoryUnavailable
    colors=runtime.red_ring_colors
    if colors is None or not colors.enabled or not (getattr(memory,'native_patch',None) or {}).get('red_ring_spawn'):
        return
    header,rows,_=layout()
    extended=bool(memory.native_patch.get('accessible_ring_colors',True))
    luma=bool(colors.options.get('luma',0))
    if luma != bool(memory.native_patch.get('luma_ring_colors')):
        colors.renderer.status={'native_rendering':False,'reason':'Repatch ISO for selected ring palette'}
        return
    if colors.options.get('colorblind_mode') and not extended:
        colors.renderer.status={'native_rendering':False,'reason':'Repatch ISO for Colorblind Mode ring colors'}
        return
    values={}
    for mission,address in rows.items():
        if all(colors.locations.get((mission,ring)) in colors.rewards for ring in range(1,6)):
            values[address+2]=encode(colors.stage_colors(mission),extended,luma).to_bytes(2,'big')
    if not values:return
    values={address:data for address,data in values.items() if memory.read_bytes(address,len(data))!=data}
    old_generation=memory.read_bytes(header+4,4)
    generation=int.from_bytes(old_generation,'big')
    if not values and generation and not generation&1:return
    start=((generation+1)|1)&0xFFFFFFFF
    if start==0xFFFFFFFF:start=1
    finish=start+1
    tx={'source':colors,'identity':colors.identity,'values':values,
        'generation_start':start,'generation_end':finish}
    memory._ring_spawn_transaction=tx
    try:
        fields=list(values.items())
        values[header+4]=start.to_bytes(4,'big')
        memory.write_bytes_verified(header+4,values[header+4],expected=old_generation,operation='red_ring_spawn')
        for address,data in fields:
            old=memory.read_bytes(address,len(data))
            if old!=data:memory.write_bytes_verified(address,data,expected=old,operation='red_ring_spawn')
        values[header+4]=finish.to_bytes(4,'big')
        memory.write_bytes_verified(header+4,values[header+4],expected=start.to_bytes(4,'big'),operation='red_ring_spawn')
    except MemoryUnavailable as error:
        colors.renderer.status={'native_rendering':True,'reason':'native spawn palette pending: '+str(error)}
    finally:
        memory._ring_spawn_transaction=None


def authorize(memory,guard,address,size):
    import hashlib
    tx=getattr(memory,'_ring_spawn_transaction',None)
    identity=tuple(guard.journal.identity[key] for key in ('seed','team','slot'))
    native=getattr(memory,'native_patch',None) or {}
    if (not tx or not native.get('red_ring_spawn') or tx['identity']!=identity
            or tx['source'].identity!=identity or not tx['source'].enabled
            or bool(tx['source'].options.get('luma')) != bool(native.get('luma_ring_colors'))
            or native.get('seed_digest')!=hashlib.sha256(identity[0].encode()).digest()[:16].hex()):
        raise memory.error('WRITE_BLOCKED: unauthenticated native ring palette')
    header,rows,_=layout()
    value=tx['values'].get(address)
    if not isinstance(value,bytes) or len(value)!=size:
        raise memory.error('WRITE_BLOCKED: invalid ring palette field')
    if address==header+4:
        start,end=tx.get('generation_start'),tx.get('generation_end')
        if (type(start) is not int or not 0<start<0xFFFFFFFF or not start&1 or end!=start+1
                or int.from_bytes(value,'big') not in (start,end)):
            raise memory.error('WRITE_BLOCKED: invalid ring palette generation')
    else:
        mission=next((name for name,slot in rows.items() if address==slot+2),None)
        colors=tx['source']
        if (mission is None or not all(colors.locations.get((mission,ring)) in colors.rewards for ring in range(1,6))
                or value!=encode(colors.stage_colors(mission),native.get('accessible_ring_colors',True),native.get('luma_ring_colors',False)).to_bytes(2,'big')):
            raise memory.error('WRITE_BLOCKED: palette differs from authenticated scout data')
    return identity,native['code_sha256'],address
