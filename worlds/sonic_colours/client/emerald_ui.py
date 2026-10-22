"""Project AP emerald ownership into existing PAL Game Land UI colours only.

805EB214/805EB288 resolve named panes through a layout dictionary/cache;
805E6734/805E5794 update allocated colour data, then 805E34C8 dirties ancestors.
No save, clear, rank, stage-availability or location fields are changed.
"""
import struct
from .memory import MemoryUnavailable,valid_range
from .native_read import read_stage_objects,read_actors

from ..world_constants import GAME_LAND_EMERALD_COLOURS
UI_COLOURS=GAME_LAND_EMERALD_COLOURS
ACTOR_VTABLE=0x8077E59C
PANE_WRAPPER_VTABLE=0x807ABA34
_PENDING_REFRESH = set()
_COMPLETED_REFRESH = set()


def targets(memory, stages=False):
    rows=read_stage_objects(memory,include_pickups=False)
    if len(rows)!=1 or rows[0].get('scene')!='game_land_select':return {}
    context=rows[0]['context']
    actors=[a for a in read_actors(memory,context) if memory.read_u32(a)==ACTOR_VTABLE]
    if len(actors)!=1:raise MemoryUnavailable('Emerald UI owner unavailable')
    actor=actors[0];result={}
    for offset in ((0x84,) if stages else (0x84,0x94)):
        ref=memory.read_ptr_checked(actor+offset+4,4)
        layer=memory.read_ptr_checked(ref,0xe0)
        layout=memory.read_ptr_checked(layer+0xc,0x34)
        count=memory.read_u32(layout+0x2c)
        if not 14<=count<=512:raise MemoryUnavailable('Emerald UI dictionary size invalid')
        table=memory.read_ptr_checked(layout+0x30,count*12);wanted={}
        dictionary=memory.read_bytes(table,count*12)
        for i in range(count):
            nameptr,group,pane_index=struct.unpack_from('>III',dictionary,i*12)
            if nameptr%4 or not valid_range(nameptr,16):raise MemoryUnavailable('Invalid Game Land pane name')
            name=memory.read_bytes(nameptr,16).split(b'\0')[0]
            if stages:
                if len(name)!=7 or not name.startswith(b'act_') or name[5:6]!=b'_':continue
                zone=name[4]-48;act=name[6]-48
                if not (0<=zone<7 and 0<=act<3):continue
                key=(group,pane_index)
                if key in wanted:raise MemoryUnavailable('Duplicate Game Land stage pane')
                wanted[key]=zone*3+act
            else:
                for index,colour in enumerate(UI_COLOURS):
                    if name in (f'em_img_{index}'.encode(),f'em_bli_{index}'.encode()):
                        key=(group,pane_index)
                        if key in wanted:raise MemoryUnavailable('Duplicate Emerald pane')
                        wanted[key]=colour
        if len(wanted)!=(21 if stages else 14):raise MemoryUnavailable('Game Land UI named panes missing')
        # Resolve allocated panes directly, as 805E4AC0 does. The native
        # dictionary is complete before the lazy named-wrapper cache; waiting
        # for every em_img/em_bli wrapper misses the first menu presentation.
        flags=memory.resolve_flags_ptr(allow_working=True)[-1] if stages else None
        graph=memory.read_ptr_checked(layer+0x8c,0x10)
        groups=memory.read_ptr_checked(memory.read_ptr_checked(graph+0xc,8)+4,16)
        for (group,index),value in wanted.items():
            if not 0<=group<512 or not 0<=index<512:raise MemoryUnavailable('Invalid Game Land pane index')
            array=memory.read_ptr_checked(groups+group*16+4,(index+1)*0x144)
            pane=array+index*0x144
            # 805E0CF0 skips a pane whenever its cached hide property (+20)
            # is nonzero. Rows 2/3 start hidden in the native layout. Tinting
            # them alone never reveals them after AP availability changes.
            # Repair only settled, resolved panes with no native hide override;
            # no guest allocation, animation, or save bits are touched.
            visibility=(stages and memory.read_u32(actor+0x9c)==13
                        and memory.read_u32(pane+0x140)==1
                        and not memory.read_u32(pane+0x74)&1)
            if visibility:
                result[pane+0x28]=('stage_hidden',value)
                result[pane+0x20]=('stage_hidden_cache',value)
            cleared=stages and memory.read_progress_bit(flags,252+value)
            if not cleared:
                if not memory.read_u32(pane+0x74)&0x80:
                    raise MemoryUnavailable('Game Land pane colour not initialized')
                data=memory.read_ptr_checked(pane+0x78,0x20)
                result[data+0x1c]=('stage_colour' if stages else 'colour',value)
            elif not visibility:
                continue
            ancestors=set()
            while True:
                if pane in ancestors or len(ancestors)>=64:raise MemoryUnavailable('Game Land pane parent cycle')
                ancestors.add(pane)
                leaf=('dirty_visibility' if cleared else 'dirty_colour_visibility') if visibility else 'dirty_colour'
                result[pane+0x7c]=(leaf if len(ancestors)==1 else 'dirty',None)
                if not memory.read_u32(pane+0x80):break
                pane=memory.read_ptr_checked(pane+0x80,0x88)
            root=memory.read_ptr_checked(pane+0x84,0x10)
            owner=memory.read_ptr_checked(root+0xc,0x3c)
            result[root+8]=('zero',None);result[owner+8]=('zero',None);result[owner+0x38]=('one',None)
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
    from .game_land_ui import verified_batch
    with verified_batch(memory,fields,operation='emerald_ui'):
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
