"""Project AP emerald ownership into existing PAL Game Land UI colours only.

805EB214/805EB288 resolve named panes through a layout dictionary/cache;
805E6734/805E5794 update allocated colour data, then 805E34C8 dirties ancestors.
No save, clear, rank, stage-availability or location fields are changed.
"""
from .memory import MemoryUnavailable
from .native_read import read_stage_objects,read_actors

UI_COLOURS=('Green','Yellow','White','Red','Purple','Blue','Cyan')
ACTOR_VTABLE=0x8077E59C
PANE_WRAPPER_VTABLE=0x807ABA34
_PENDING_REFRESH = set()
_COMPLETED_REFRESH = set()


def targets(memory):
    rows=read_stage_objects(memory,include_pickups=False)
    if len(rows)!=1 or rows[0].get('scene')!='game_land_select':return {}
    context=rows[0]['context']
    actors=[a for a in read_actors(memory,context) if memory.read_u32(a)==ACTOR_VTABLE]
    if len(actors)!=1:raise MemoryUnavailable('Emerald UI owner unavailable')
    actor=actors[0];result={}
    for offset in (0x84,0x94):
        ref=memory.read_ptr_checked(actor+offset+4,4)
        layer=memory.read_ptr_checked(ref,0xe0)
        layout=memory.read_ptr_checked(layer+0xc,0x34)
        count=memory.read_u32(layout+0x2c)
        if not 14<=count<=512:raise MemoryUnavailable('Emerald UI dictionary size invalid')
        table=memory.read_ptr_checked(layout+0x30,count*12);wanted={}
        for i in range(count):
            entry=table+i*12
            nameptr=memory.read_ptr_checked(entry,16)
            name=memory.read_bytes(nameptr,16).split(b'\0')[0]
            for index,colour in enumerate(UI_COLOURS):
                if name in (f'em_img_{index}'.encode(),f'em_bli_{index}'.encode()):
                    key=(memory.read_u32(entry+4),memory.read_u32(entry+8))
                    if key in wanted:raise MemoryUnavailable('Duplicate Emerald pane')
                    wanted[key]=colour
        if len(wanted)!=14:raise MemoryUnavailable('Emerald UI named panes missing')
        todo=[memory.read_u32(layer+0xd8)];seen=set();found=set()
        while todo:
            node=todo.pop()
            if not node:continue
            if node in seen or len(seen)>=512:raise MemoryUnavailable('Emerald pane cache cycle')
            seen.add(node)
            todo.extend((memory.read_u32(node),memory.read_u32(node+4)))
            key=(memory.read_u32(node+0xc),memory.read_u32(node+0x10))
            if key not in wanted:continue
            found.add(key)
            wrapper=memory.read_ptr_checked(memory.read_ptr_checked(node+0x18,4),0x38)
            if memory.read_u32(wrapper)!=PANE_WRAPPER_VTABLE:raise MemoryUnavailable('Emerald pane wrapper class mismatch')
            component=memory.read_ptr_checked(wrapper+0x34,0x10)
            pane=memory.read_ptr_checked(component+0xc,0x88)
            if not memory.read_u32(pane+0x74)&0x80:raise MemoryUnavailable('Emerald colour not initialized')
            data=memory.read_ptr_checked(pane+0x78,0x20)
            colour=wanted[key];result[data+0x1c]=('colour',colour)
            result[pane+0x7c]=('dirty_colour',None)
            ancestors=set()
            while True:
                if pane in ancestors or len(ancestors)>=64:raise MemoryUnavailable('Emerald pane parent cycle')
                ancestors.add(pane);result[pane+0x7c]=('dirty_colour' if len(ancestors)==1 else 'dirty',None)
                parent=memory.read_u32(pane+0x80)
                if not parent:break
                pane=memory.read_ptr_checked(pane+0x80,0x88)
            root=memory.read_ptr_checked(pane+0x84,0x10)
            owner=memory.read_ptr_checked(root+0xc,0x3c)
            result[root+8]=('zero',None);result[owner+8]=('zero',None);result[owner+0x38]=('one',None)
        if found!=set(wanted):raise MemoryUnavailable('Emerald pane cache incomplete')
    if read_stage_objects(memory,include_pickups=False)[0]['context']!=context:
        raise MemoryUnavailable('Emerald UI changed during read')
    return result


def apply(memory,snapshot,guard,owned):
    if snapshot.scene!='game_land_select':return {'status':'not on Game Land menu'}
    guard.check(snapshot)
    fields=targets(memory);changed=0
    identity=tuple(sorted((a,0xffffffff if owned['counts'].get(c+' Chaos Emerald',0) else 0x606060ff)
                          for a,(k,c) in fields.items() if k=='colour'))
    # Prune disappeared native allocations; retain an interrupted publication.
    _PENDING_REFRESH.intersection_update({identity})
    _COMPLETED_REFRESH.intersection_update({identity})
    if identity not in _COMPLETED_REFRESH or any(memory.read_u32(a)!=value for a,value in identity):
        _PENDING_REFRESH.add(identity)
    refresh=identity in _PENDING_REFRESH
    # All pane/ancestor dirtiness precedes root cache reset. Publish both
    # native redraw markers LAST: the emulation can run between host writes.
    order={'colour':0,'dirty_colour':1,'dirty':1,'zero':2,'one':3}
    for address,(kind,colour) in sorted(fields.items(),key=lambda row:order[row[1][0]]):
        before=memory.read_u32(address)
        if kind=='colour':after=0xffffffff if owned['counts'].get(colour+' Chaos Emerald',0) else 0x606060ff
        elif not refresh:continue
        elif kind=='dirty_colour':after=before & ~0x00180080
        elif kind=='dirty':after=before & ~0x00100000
        else:after=int(kind=='one')
        if before!=after:
            memory.write_u32(address,after,expected=before,operation='emerald_ui');changed+=1
    _PENDING_REFRESH.discard(identity)
    _COMPLETED_REFRESH.add(identity)
    return {'status':'AP emerald colours projected','changed_fields':changed,
            'owned_colours':[c for c in UI_COLOURS if owned['counts'].get(c+' Chaos Emerald',0)],
            'location_source':'three native Game Land clears per group; UI ownership independent','visual_verified':False}
