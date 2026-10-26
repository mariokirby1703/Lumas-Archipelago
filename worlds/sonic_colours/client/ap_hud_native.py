from .memory import MemoryUnavailable
from .native_read import read_stage_objects,read_actors
ACTOR_VTABLE=0x80764440
LAYER_VTABLE=0x807ABC40

def probe(memory):
    memory.verify_revision()
    rows=read_stage_objects(memory,False)
    if len(rows)!=1 or rows[0].get('scene')!='gameplay':raise MemoryUnavailable('HUD probe requires a live gameplay scene')
    stage=rows[0]
    actors=[a for a in read_actors(memory,stage['context']) if memory.read_u32(a)==ACTOR_VTABLE]
    if len(actors)!=1:raise MemoryUnavailable('Bonus HUD owner not unique')
    actor=actors[0]
    if memory.read_u32(ACTOR_VTABLE+0x40)!=0x8010DE38:raise MemoryUnavailable('HUD update ABI differs')
    ref=memory.read_ptr_checked(actor+0x3a8,4);layer=memory.read_ptr_checked(ref,0xe0)
    if memory.read_u32(layer)!=LAYER_VTABLE:raise MemoryUnavailable('Bonus scene owner class differs')
    layout=memory.read_ptr_checked(layer+12,0x34);count=memory.read_u32(layout+0x2c)
    if count!=18:raise MemoryUnavailable('Bonus cast dictionary differs')
    table=memory.read_ptr_checked(layout+0x30,count*12);casts={}
    for i in range(count):
        entry=table+i*12;p=memory.read_ptr_checked(entry,4)
        name=memory.read_bytes(p,32).split(b'\0')[0].decode('ascii','replace')
        if name in ('word_bonus','num_bonus'):casts[name]=(memory.read_u32(entry+4),memory.read_u32(entry+8))
    if casts!={'num_bonus':(0,7),'word_bonus':(0,8)}:raise MemoryUnavailable('Bonus cast identities differ')
    if memory.read_u32(actor)!=ACTOR_VTABLE or memory.read_u32(ref)!=layer:raise MemoryUnavailable('HUD scene changed during read')
    return {'owner_verified':True,'hud_ready':False,'font_ready':False,'actor':hex(actor),'layer':hex(layer),
        'mission':stage['mission'],'casts':casts,'blocked_reason':'Live bonus scene verified; separate alphabetic casts and texture owner still unverified'}
