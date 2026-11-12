"""File-only PAL DOL integration of the complete AP hook policy.

The unused DOL text slot maps 80001800..80003000 at load time. The first
cache line is non-executable reserved data: PAL runtime writes were observed
at 80001800. No codehandler executes, no JIT invalidation or host instruction
writes are used. The original BSS and all game sections remain in place.
"""
import hashlib
import json
import struct
from functools import lru_cache

PAL_DOL_SHA256='92aefe33b577493b492f8433ca68b90d25d29d2d6f9c85310a6829481281f8a9'
ARENA=0x80001800
# Captured PAL gameplay writes modify the word at ARENA. Do not execute it.
# Keep the whole first cache line out of code and all policy mailboxes.
ARENA_PREFIX_SIZE=32
SIGNATURE=0x80002fc0
ABI=2
_PLAN_FEATURES={}
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

@lru_cache(maxsize=128)
def plan(include_ring_materials=True,include_ring_spawn=True,include_boot_guards=True,include_accessible_colors=True,include_sixty_fps=False,include_luma_colors=False,legacy_fps_word_write=False,legacy_wisp_slots=False,include_physical_restore=True,include_score_reset=True,include_super_guard=True,include_spring_guard=True):
    """Rebuild every C2 payload as initialized native code, without C2 headers."""
    include_score_reset=bool(include_score_reset and include_physical_restore)
    include_super_guard=bool(include_super_guard and include_score_reset)
    include_spring_guard=bool(include_spring_guard and include_super_guard and include_sixty_fps and not legacy_fps_word_write)
    from .native_hook_table import hook_rows
    from .ap_hud_publisher import patches as hud
    from .rocket_skydiving import patches as rocket
    from .hud_renderer_batch import ADDRESS,ORIGINAL_HEX,replacement
    rows=hook_rows();i=0;cursor=ARENA+ARENA_PREFIX_SIZE;patches=[];payload=bytearray(ARENA_PREFIX_SIZE);hooks=[]
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
    ring_restore=cursor if include_physical_restore else None
    if include_physical_restore:
        payload.extend(bytes(12));cursor+=12
    patches.extend(native_events.patches(cursor,ring_restore=ring_restore,score_reset=include_score_reset))
    mailbox=bytearray(native_events.SIZE);struct.pack_into('>I',mailbox,0,native_events.MAGIC)
    for state in native_events.JUMP_STATES:
        offset=native_events.JUMP_TABLE+(state//32)*4
        value=struct.unpack_from('>I',mailbox,offset)[0]|(1<<(state%32))
        struct.pack_into('>I',mailbox,offset,value)
    payload.extend(mailbox);cursor+=len(mailbox)
    patches.append((ADDRESS,bytes.fromhex(ORIGINAL_HEX),replacement()))
    from . import boss_capsules,capsule_refresh,progression_hook
    capsule=next(h for h in hooks if h['hook']==capsule_refresh.HOOK)
    story=next(h for h in hooks if h['hook']==progression_hook.HOOK)
    capsule_control=capsule['target']+capsule_refresh.data_offset(capsule_refresh.payload_words(
        compact_abi=True,epilogue_abi=True,cache_permissions=True))
    story_control=story['target']+progression_hook.payload()[1]
    patches.extend(boss_capsules.patches(capsule_control,story_control,patches))
    from . import wisp_hud
    patches.extend(wisp_hud.patches(capsule_control,story_control,patches))
    from . import movement_gate
    movement=next(h for h in hooks if h['hook']==movement_gate.HOOK)
    from . import active_movement
    patches.extend(active_movement.patches(movement['target']+movement_gate.payload(gecko=True)[2],patches))
    from . import rail_actions
    patches.extend(rail_actions.patches(movement['target']+movement_gate.payload(gecko=True)[2],patches))
    from . import drill_turbo
    drill=next(h for h in hooks if h['hook']==drill_turbo.HOOK)
    patches.extend(drill_turbo.water_patches(drill['target']+drill_turbo.payload()[1],patches))
    from . import wisp_activation
    patches.extend(wisp_activation.patches(capsule_control,story_control,patches,legacy_slots=legacy_wisp_slots))
    from . import random_wisp_spawns
    patches.extend(random_wisp_spawns.patches(capsule_control,story_control,patches,legacy_slots=legacy_wisp_slots))
    from . import white_capsule_open
    patches.extend(white_capsule_open.patches(capsule_control,patches,legacy_slots=legacy_wisp_slots))
    from . import drift_input
    patches.extend(drift_input.patches(movement['target']+movement_gate.payload(gecko=True)[2],patches))
    if include_ring_materials:
        from .red_ring_render_test import allocation_patches
        patches.extend(allocation_patches())
        if include_ring_spawn:
            from .red_ring_spawn import patches as spawn_patches
            patches.extend(spawn_patches(include_accessible_colors,include_luma_colors))
    if cursor>SIGNATURE-4:raise ValueError('native executable section exhausted (HUD registry reserved)')
    if include_boot_guards:
        from .white_capsule_spawn import patches as white_spawn
        patches.extend(white_spawn(capsule_control,patches))
        from .boost_startup import apply as boost_startup
        payload,boost_patches=boost_startup(payload,hooks,patches)
        patches.extend(boost_patches)
    if include_sixty_fps:
        from .sixty_fps import patches as fps_patches
        patches.extend(fps_patches(patches,legacy_fps_word_write))
    if include_super_guard:
        from .super_sonic import patches as super_patches
        patches.extend(super_patches())
    if include_spring_guard:
        from .spring_retrigger import patches as spring_patches
        patches.extend(spring_patches(patches))
    ownership=[]
    for address,old,new in patches:
        if any(address<end and start<address+len(new) for start,end in ownership):raise ValueError(f'native hook collision at {address:#x}')
        ownership.append((address,address+len(new)))
    digest=hashlib.sha256(bytes(payload)+b''.join(struct.pack('>I',a)+n for a,o,n in patches)).digest()
    _PLAN_FEATURES[digest.hex()]={'physical_ring_restore':include_physical_restore,'native_score_reset':include_score_reset,'super_sonic_guard':include_super_guard,'spring_retrigger_guard':include_spring_guard}
    return patches,bytes(payload),digest,hooks

def patch_dol(original,seed,ring_colors=None,options=None,initial_items=()):
    if hashlib.sha256(original).hexdigest()!=PAL_DOL_SHA256:raise ValueError('unsupported original main.dol SHA256')
    image=Dol(original);patches,payload,digest,hooks=plan(include_sixty_fps=bool((options or {}).get('sixty_fps',0)),include_luma_colors=bool((options or {}).get('luma',0)));registry=[]
    from .red_ring_spawn import validate_colors,prefill
    validate_colors(ring_colors,luma=bool((options or {}).get('luma',0)))
    for address,old,new in patches:
        new=prefill(address,new,ring_colors,luma=bool((options or {}).get('luma',0)))
        old=image.read(address,len(new)) if old is None else old
        image.replace(address,old,new)
        registry.append({'address':address,'length':len(new),'original':old.hex(),'replacement':new.hex()})
    boot={}
    if options is not None:
        from .boot_permissions import initialize
        payload,boot=initialize(payload,hooks,options,initial_items)
    native=bytearray(SIGNATURE-ARENA+64);native[:len(payload)]=payload
    identity=hashlib.sha256(str(seed).encode()).digest()
    native[-64:]=MAGIC+struct.pack('>II',ABI,len(payload))+digest+identity[:16]
    image.add_text(ARENA,native)
    return bytes(image.data),{'abi':ABI,'signature':SIGNATURE,'native_payload_bytes':len(payload),
                            'native_sha256':digest.hex(),'hooks':hooks,'ownership':registry,
                            'source_sha256':PAL_DOL_SHA256,'seed_digest':identity.hex(),
                            'boot_permissions':boot}

@lru_cache(maxsize=64)
def plan_for_digest(digest):
    released={
        'c93c8e318a2b66d0f09716d0b9628d42027ebe94c733914dc348355b62c3cfa6':True,
        'bfd736d810b914c5981f55ef34ecef905e4c349a1543331fd413a5228e5ca395':False,
    }
    if digest in released:
        candidate=plan(include_physical_restore=False,legacy_wisp_slots=released[digest])
        if candidate[2].hex()==digest:return candidate
    variants = ({}, {'include_sixty_fps':True}, {'include_luma_colors':True},
                {'include_luma_colors':True,'include_sixty_fps':True},
                {'include_sixty_fps':True,'legacy_fps_word_write':True},
                {'include_sixty_fps':True,'include_luma_colors':True,'legacy_fps_word_write':True},
                {'include_accessible_colors':False},
                {'include_boot_guards':False,'include_accessible_colors':False},
                {'include_ring_spawn':False,'include_boot_guards':False,'include_accessible_colors':False},
                {'include_ring_materials':False,'include_boot_guards':False,'include_accessible_colors':False})
    for restore,score,super_guard,spring_guard in ((True,True,True,True),(True,True,True,False),(True,True,False,False),(True,False,False,False),(False,False,False,False)):
        for legacy in (False,True):
            for options in variants:
                candidate=plan(**options,legacy_wisp_slots=legacy,include_physical_restore=restore,include_score_reset=score,include_super_guard=super_guard,include_spring_guard=spring_guard)
                if candidate[2].hex()==digest:return candidate
    raise ValueError('incompatible native AP hook ABI/signature')


def handshake(memory):
    raw=memory.read_bytes(SIGNATURE,64)
    if raw[:8]!=MAGIC:return None
    try:patches,payload,digest,hooks=plan_for_digest(raw[16:48].hex())
    except ValueError:patches,payload,digest,hooks=plan()
    if raw[8:48]!=struct.pack('>II',ABI,len(payload))+digest:
        if raw[16:48].hex() in {'032d23d9e9395d2fe9e53e3c9139bc0fd8c42e2cf71adc124088f78969240081',
                                '131e58fb3e7f593daa983f66d61251ee417080c88dfe5646f7e7aa04514642b5'}:
            raise memory.error('Older native ISO lacks arena-entry protection; repatch the original ISO with this APWorld and your existing player patch')
        raise memory.error('incompatible native AP hook ABI/signature')
    from .red_ring_spawn import normalized,HOOK as SPAWN_HOOK
    has_spawn=any(a==SPAWN_HOOK for a,o,n in patches)
    from .red_ring_spawn import layout,MAGIC_V2,MAGIC_LUMA
    has_luma=has_spawn and any(a==layout()[0] and n[:4]==struct.pack('>I',MAGIC_LUMA) for a,o,n in patches)
    has_accessible=has_luma or has_spawn and any(a==layout()[0] and n[:4]==struct.pack('>I',MAGIC_V2) for a,o,n in patches)
    pages={}
    for address,old,new in patches:
        observed=bytearray();cursor=address
        while cursor<address+len(new):
            page=cursor&~0xfff
            if page not in pages:pages[page]=memory.read_bytes(page,4096)
            size=min(page+4096,address+len(new))-cursor
            observed.extend(pages[page][cursor-page:cursor-page+size]);cursor+=size
        try:checked=normalized(address,bytes(observed),new,has_accessible) if has_spawn else observed
        except ValueError as error:raise memory.error(str(error)) from error
        if checked!=new:raise memory.error(f'native AP patch modified at {address:#x}; disable legacy Gecko/Riivolution')
    # Previously only external hook branches and area-map code were checked
    # here. A valid signature does not prove the arena's entry instructions
    # survived; the captured failure changed its first stack allocation.
    arena_data=memory.read_bytes(ARENA,len(payload))
    # Dolphin's HLE::PatchFixedFunctions writes the HBReload signature here
    # when cheats are disabled. This prefix contains no AP code or mailboxes.
    prefix = arena_data[4:ARENA_PREFIX_SIZE]
    dolphin_prefix = b'STUBHAXX' + payload[12:ARENA_PREFIX_SIZE]
    if prefix not in (payload[4:ARENA_PREFIX_SIZE], dolphin_prefix):
        changed = [f'0x{ARENA + offset:08X}' for offset in range(4, ARENA_PREFIX_SIZE)
                   if arena_data[offset] != payload[offset]]
        entries_match = all(
            arena_data[hook['target']-ARENA:hook['target']-ARENA+4]
            == payload[hook['target']-ARENA:hook['target']-ARENA+4] for hook in hooks)
        raise memory.error(
            'Unexpected native arena prefix modification beyond the observed low-memory word; '
            f'prefix_address=0x{ARENA:08X}; observed={arena_data[:ARENA_PREFIX_SIZE].hex()}; '
            f'expected={payload[:ARENA_PREFIX_SIZE].hex()}; '
            f'changed_addresses={",".join(changed)}; executable_entries_match={entries_match}')
    for hook in hooks:
        target=hook['target'];offset=target-ARENA
        if arena_data[offset:offset+4]!=payload[offset:offset+4]:
            raise memory.error(f'native AP executable entry modified at {target:#x}; restart the corrected ISO')
    from .area_map_refresh import HOOK as AREA_HOOK
    area=next(h for h in hooks if h['hook']==AREA_HOOK)
    offset=area['target']-ARENA;size=area['size']
    # Eight cached data words are guest-owned; all executable words and the
    # return branch remain exact. Other hooks retain their module inspectors.
    if (memory.read_bytes(area['target'],size-36)!=payload[offset:offset+size-36]
            or memory.read_bytes(area['target']+size-4,4)!=payload[offset+size-4:offset+size]):
        raise memory.error('native area-map refresh executable modified')
    from .red_ring_render_test import allocation_patches
    ring_words = [memory.read_bytes(address,4) for address,old,new in allocation_patches()]
    ring_materials = ring_words == [new for address,old,new in allocation_patches()]
    if not ring_materials and ring_words != [old for address,old,new in allocation_patches()]:
        raise memory.error('incomplete Red Ring material allocation patch; repatch ISO')
    return {'abi':ABI,'seed_digest':raw[48:].hex(),'code_sha256':digest.hex(),'gecko_required':False,
            'red_ring_materials':ring_materials,
            **_PLAN_FEATURES[digest.hex()],
            'red_ring_spawn':has_spawn,
            'accessible_ring_colors':has_accessible,
            'luma_ring_colors':has_luma,
            'white_capsule_spawn':any(a==0x800D3C84 for a,o,n in patches),
            'reserved_low_word':hex(int.from_bytes(arena_data[:4],'big'))}
