"""File-only PAL DOL integration of the complete AP hook policy.

The unused DOL text slot maps the SDK-reserved 80001800..80003000 range
at load time. No codehandler executes, no JIT invalidation or host instruction
writes are used. The original BSS and all game sections remain in place.
"""
import hashlib
import json
import struct
from functools import lru_cache

PAL_DOL_SHA256='92aefe33b577493b492f8433ca68b90d25d29d2d6f9c85310a6829481281f8a9'
ARENA=0x80001800
SIGNATURE=0x80002fc0
ABI=2
MAGIC=b'SCAPNAT1'

def branch(source,target):
    delta=target-source
    if delta%4 or not -(1<<25)<=delta<(1<<25):raise ValueError('PPC branch alignment/range')
    return 0x48000000|(delta&0x3fffffc)

class Dol:
    def __init__(self,data):
        if len(data)<256:raise ValueError('truncated DOL')
        self.data=bytearray(data)
        self.sections=[]
        for i in range(18):
            offset,address,size=(struct.unpack_from('>I',data,p+4*i)[0] for p in (0,0x48,0x90))
            if size:
                if offset<256 or offset+size>len(data):raise ValueError('invalid DOL section bounds')
                if any(address<other[2]+other[3] and other[2]<address+size for other in self.sections):raise ValueError('overlapping DOL sections')
                self.sections.append((i,offset,address,size))
    def offset(self,address,size):
        rows=[s for s in self.sections if s[2]<=address and address+size<=s[2]+s[3]]
        if len(rows)!=1:raise ValueError(f'unmapped DOL address {address:#x}')
        return rows[0][1]+address-rows[0][2]
    def read(self,address,size):
        off=self.offset(address,size);return bytes(self.data[off:off+size])
    def replace(self,address,old,new):
        if address%4 or len(old)!=len(new) or len(new)%4:raise ValueError('unaligned DOL patch')
        if self.read(address,len(old))!=old:raise ValueError(f'original DOL bytes differ at {address:#x}')
        off=self.offset(address,len(old));self.data[off:off+len(new)]=new
    def add_text(self,address,blob):
        occupied={s[0] for s in self.sections};slot=next((i for i in range(7) if i not in occupied),None)
        if slot is None:raise ValueError('no free DOL text slot')
        bss,size=struct.unpack_from('>II',self.data,0xd8)
        if bss<address+len(blob) and address<bss+size:raise ValueError('new section overlaps BSS')
        if any(address<s[2]+s[3] and s[2]<address+len(blob) for s in self.sections):raise ValueError('new section overlaps DOL')
        self.data.extend(bytes((-len(self.data))%32));offset=len(self.data);self.data.extend(blob)
        for base,value in ((0,offset),(0x48,address),(0x90,len(blob))):struct.pack_into('>I',self.data,base+4*slot,value)
        self.sections.append((slot,offset,address,len(blob)))

@lru_cache(maxsize=1)
def plan():
    """Rebuild every C2 payload as initialized native code, without C2 headers."""
    from .movement_gecko import pairs,movement_ini
    from .ap_hud_publisher import patches as hud
    from .rocket_skydiving import patches as rocket
    from .hud_renderer_batch import ADDRESS,ORIGINAL_HEX,replacement
    rows=pairs(movement_ini(enforce_budget=False));i=0;cursor=ARENA;patches=[];payload=bytearray();hooks=[]
    while i<len(rows):
        first,second=rows[i];i+=1;kind=first>>24;address=0x80000000+(first&0xffffff)
        if kind==0xc2:
            words=[w for pair in rows[i:i+second] for w in pair];i+=second
            if len(words)!=second*2 or words[-1]!=0:raise ValueError('invalid C2 return placeholder')
            words[-1]=branch(cursor+len(words)*4-4,address+4)
            blob=struct.pack('>'+'I'*len(words),*words)
            patches.append((address,None,branch(address,cursor).to_bytes(4,'big')))
            hooks.append({'hook':address,'target':cursor,'size':len(blob),'return':address+4})
            payload.extend(blob);cursor+=len(blob)
        elif kind==4:patches.append((address,None,second.to_bytes(4,'big')))
        elif kind not in (0x20,0x28,0xe0):raise ValueError(f'unsupported export instruction {first:#x}')
    from . import capsule_capture
    words,_=capsule_capture.payload()
    words[-1]=branch(cursor+len(words)*4-4,capsule_capture.HOOK+4)
    blob=struct.pack('>'+'I'*len(words),*words)
    patches.append((capsule_capture.HOOK,capsule_capture.ORIGINAL.to_bytes(4,'big'),branch(capsule_capture.HOOK,cursor).to_bytes(4,'big')))
    hooks.append({'hook':capsule_capture.HOOK,'target':cursor,'size':len(blob),'return':capsule_capture.HOOK+4})
    payload.extend(blob);cursor+=len(blob)
    from . import area_map_refresh
    words=area_map_refresh.payload()
    words[-1]=branch(cursor+len(words)*4-4,area_map_refresh.HOOK+4)
    blob=struct.pack('>'+'I'*len(words),*words)
    patches.append((area_map_refresh.HOOK,area_map_refresh.ORIGINAL.to_bytes(4,'big'),branch(area_map_refresh.HOOK,cursor).to_bytes(4,'big')))
    hooks.append({'hook':area_map_refresh.HOOK,'target':cursor,'size':len(blob),'return':area_map_refresh.HOOK+4})
    payload.extend(blob);cursor+=len(blob)
    patches.extend(hud(native_registry=True));patches.extend(rocket())
    from . import native_events,oxygen_native
    # Oxygen code and its data precede the event mailbox, keeping that ABI's
    # end-relative address stable and within the reserved executable section.
    oxygen_start=cursor
    probe,_=oxygen_native.payload(oxygen_start,0x80002000)
    oxygen_control=cursor+len(probe)
    oxygen_code,reset_entry=oxygen_native.payload(oxygen_start,oxygen_control)
    for hook,old,target in ((oxygen_native.UPDATE,oxygen_native.ORIGINAL_UPDATE,oxygen_start),
                            (oxygen_native.RESET,oxygen_native.ORIGINAL_RESET,reset_entry)):
        patches.append((hook,old.to_bytes(4,'big'),branch(hook,target).to_bytes(4,'big')))
    payload.extend(oxygen_code);cursor+=len(oxygen_code)
    payload.extend(struct.pack('>I',oxygen_native.MAGIC)+bytes(oxygen_native.SIZE-4));cursor+=oxygen_native.SIZE
    patches.extend(native_events.patches(cursor))
    mailbox=bytearray(native_events.SIZE);struct.pack_into('>I',mailbox,0,native_events.MAGIC)
    for state in native_events.JUMP_STATES:
        offset=native_events.JUMP_TABLE+(state//32)*4
        value=struct.unpack_from('>I',mailbox,offset)[0]|(1<<(state%32))
        struct.pack_into('>I',mailbox,offset,value)
    payload.extend(mailbox);cursor+=len(mailbox)
    patches.append((ADDRESS,bytes.fromhex(ORIGINAL_HEX),replacement()))
    ownership=[]
    for address,old,new in patches:
        if any(address<end and start<address+len(new) for start,end in ownership):raise ValueError(f'native hook collision at {address:#x}')
        ownership.append((address,address+len(new)))
    if cursor>SIGNATURE-4:raise ValueError('native executable section exhausted (HUD registry reserved)')
    digest=hashlib.sha256(bytes(payload)+b''.join(struct.pack('>I',a)+n for a,o,n in patches)).digest()
    return patches,bytes(payload),digest,hooks

def patch_dol(original,seed):
    if hashlib.sha256(original).hexdigest()!=PAL_DOL_SHA256:raise ValueError('unsupported original main.dol SHA256')
    image=Dol(original);patches,payload,digest,hooks=plan();registry=[]
    for address,old,new in patches:
        old=image.read(address,len(new)) if old is None else old
        image.replace(address,old,new)
        registry.append({'address':address,'length':len(new),'original':old.hex(),'replacement':new.hex()})
    native=bytearray(SIGNATURE-ARENA+64);native[:len(payload)]=payload
    identity=hashlib.sha256(str(seed).encode()).digest()
    native[-64:]=MAGIC+struct.pack('>II',ABI,len(payload))+digest+identity[:16]
    image.add_text(ARENA,native)
    return bytes(image.data),{'abi':ABI,'signature':SIGNATURE,'native_payload_bytes':len(payload),
                            'native_sha256':digest.hex(),'hooks':hooks,'ownership':registry,
                            'source_sha256':PAL_DOL_SHA256,'seed_digest':identity.hex()}

def handshake(memory):
    raw=memory.read_bytes(SIGNATURE,64)
    if raw[:8]!=MAGIC:return None
    patches,payload,digest,hooks=plan()
    if raw[8:48]!=struct.pack('>II',ABI,len(payload))+digest:
        if raw[16:48].hex()=='032d23d9e9395d2fe9e53e3c9139bc0fd8c42e2cf71adc124088f78969240081':
            raise memory.error('Older native ISO has unsafe PowerPC stack restores; repatch the original ISO with this APWorld and your existing player patch')
        raise memory.error('incompatible native AP hook ABI/signature')
    pages={}
    for address,old,new in patches:
        observed=bytearray();cursor=address
        while cursor<address+len(new):
            page=cursor&~0xfff
            if page not in pages:pages[page]=memory.read_bytes(page,4096)
            size=min(page+4096,address+len(new))-cursor
            observed.extend(pages[page][cursor-page:cursor-page+size]);cursor+=size
        if observed!=new:raise memory.error(f'native AP patch modified at {address:#x}; disable legacy Gecko/Riivolution')
    from .area_map_refresh import HOOK as AREA_HOOK
    area=next(h for h in hooks if h['hook']==AREA_HOOK)
    offset=area['target']-ARENA;size=area['size']
    # Eight cached data words are guest-owned; all executable words and the
    # return branch remain exact. Other hooks retain their module inspectors.
    if (memory.read_bytes(area['target'],size-36)!=payload[offset:offset+size-36]
            or memory.read_bytes(area['target']+size-4,4)!=payload[offset+size-4:offset+size]):
        raise memory.error('native area-map refresh executable modified')
    return {'abi':ABI,'seed_digest':raw[48:].hex(),'code_sha256':digest.hex(),'gecko_required':False}
