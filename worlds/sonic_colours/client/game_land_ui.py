"""Game Land labels: hidden when locked, faded until genuinely cleared."""
from .emerald_ui import targets
from .memory import MemoryUnavailable
from contextlib import contextmanager
_PENDING_REFRESH=set()
_COMPLETED_REFRESH=set()


def stage_colour(memory,flags,index):
    if not memory.read_progress_bit(flags,210+index):return 0
    return 0xffffffff if memory.read_progress_bit(flags,252+index) else 0x606060ff


@contextmanager
def verified_batch(memory,fields):
    """One full code proof; recheck live owner/topology for every field write."""
    if not hasattr(memory,'verify_revision'):
        yield;return  # lightweight offline fixtures retain their own policy
    memory.verify_revision()
    from .native_read import read_stage_objects,read_actors
    row=read_stage_objects(memory,False)[0]
    actors=[a for a in read_actors(memory,row['context']) if memory.read_u32(a)==0x8077e59c]
    if len(actors)!=1:raise MemoryUnavailable('Game Land UI owner not unique')
    actor=actors[0];ref=memory.read_ptr_checked(actor+0x88,4);layer=memory.read_ptr_checked(ref,0xe0)
    # Retain owner, dictionary, graph, and each allocated colour-data link.
    pointers=[(actor,4),(actor+12,4),(actor+0x88,4),(ref,4),(layer,4),(layer+12,4),(layer+0x8c,4)]
    for address,(kind,_) in fields.items():
        if kind in ('dirty_colour','dirty','dirty_matrix','dirty_scale'):pointers.extend(((address+4,4),(address+8,4)))
        if kind=='dirty_colour':pointers.append((address-4,4))
        if kind=='column_scale':
            pane=address-(0x38 if fields.get(address+0x44,('',))[0]=='dirty_scale' else 0x3c)
            pointers.extend(((pane+0x74,4),(pane+0x80,4)))
    if any(k=='column_scale' for k,_ in fields.values()):
        pointers.append((actor+0x9c,4))
        flags=memory.resolve_flags_ptr(allow_working=True)[-1]
        pointers.extend((flags+0x10+i*4,4) for i in (6,7))
    anchors=tuple((a,memory.read_bytes(a,n)) for a,n in pointers)
    code=tuple((a,memory.read_bytes(a,n)) for a,n in ((0x80000000,8),(0x802f0d98,4),(0x802f0dd4,4)))
    if getattr(memory,'_game_land_ui_batch',None) is not None:raise MemoryUnavailable('nested UI batch')
    memory._game_land_ui_batch={'fields':fields,'anchors':anchors,'code':code}
    try:yield
    finally:memory._game_land_ui_batch=None

def validate_batch(memory,batch):
    if any(memory.read_bytes(a,len(value))!=value for a,value in (*batch['code'],*batch['anchors'])):
        raise MemoryUnavailable('WRITE_BLOCKED: Game Land UI owner/topology changed')
    return batch['fields']


def apply(memory,snapshot,guard,owned):
    if snapshot.scene!='game_land_select':return {'status':'not on Game Land menu'}
    guard.check(snapshot)
    flags=memory.resolve_flags_ptr(allow_working=True)[-1]
    fields=targets(memory,stages=True);changed=0
    if hasattr(memory,'verify_revision'):
        from .game_land_columns import targets as column_targets
        for address,value in column_targets(memory,flags).items():
            if (value[0]=='dirty_scale' or address not in fields
                    or value[0]=='dirty_matrix' and fields[address][0]!='dirty_colour'):
                fields[address]=value
    identity=tuple(sorted((a,stage_colour(memory,flags,c))
                          for a,(k,c) in fields.items() if k=='stage_colour'))
    # Prune disappeared native allocations; retain an interrupted publication.
    _PENDING_REFRESH.intersection_update({identity})
    _COMPLETED_REFRESH.intersection_update({identity})
    if identity not in _COMPLETED_REFRESH or any(memory.read_u32(a)!=value for a,value in identity):
        _PENDING_REFRESH.add(identity)
    refresh=identity in _PENDING_REFRESH or any(k=='column_scale' for k,_ in fields.values())
    # All pane/ancestor dirtiness precedes root cache reset. Publish both
    # native redraw markers LAST: the emulation can run between host writes.
    order={'stage_colour':0,'column_scale':0,'dirty_colour':1,'dirty_matrix':1,'dirty_scale':1,'dirty':1,'zero':2,'one':3}
    with verified_batch(memory,fields):
        for address,(kind,colour) in sorted(fields.items(),key=lambda row:order[row[1][0]]):
            before=memory.read_u32(address)
            if kind=='stage_colour':after=stage_colour(memory,flags,colour)
            elif kind=='column_scale':after=0x3f800000
            elif not refresh:continue
            elif kind=='dirty_colour':after=before & ~0x00180080
            elif kind=='dirty_matrix':after=before & ~0x00180000
            elif kind=='dirty_scale':after=before & ~0x00180030
            elif kind=='dirty':after=before & ~0x00100000
            else:after=int(kind=='one')
            if before!=after:
                memory.write_u32(address,after,expected=before,operation='game_land_ui');changed+=1
    _PENDING_REFRESH.discard(identity)
    _COMPLETED_REFRESH.add(identity)
    return {'status':'Game Land availability and clears displayed separately','changed_fields':changed,'visual_verified':False}
