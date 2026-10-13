"""Game Land labels: hidden when locked, faded until genuinely cleared."""
from .emerald_ui import targets
_PENDING_REFRESH=set()
_COMPLETED_REFRESH=set()


def stage_colour(memory,flags,index):
    if not memory.read_progress_bit(flags,210+index):return 0
    return 0xffffffff if memory.read_progress_bit(flags,252+index) else 0x606060ff


def apply(memory,snapshot,guard,owned):
    if snapshot.scene!='game_land_select':return {'status':'not on Game Land menu'}
    guard.check(snapshot)
    flags=memory.resolve_flags_ptr(allow_working=True)[-1]
    fields=targets(memory,stages=True);changed=0
    identity=tuple(sorted((a,stage_colour(memory,flags,c))
                          for a,(k,c) in fields.items() if k=='stage_colour'))
    # Prune disappeared native allocations; retain an interrupted publication.
    _PENDING_REFRESH.intersection_update({identity})
    _COMPLETED_REFRESH.intersection_update({identity})
    if identity not in _COMPLETED_REFRESH or any(memory.read_u32(a)!=value for a,value in identity):
        _PENDING_REFRESH.add(identity)
    refresh=identity in _PENDING_REFRESH
    # All pane/ancestor dirtiness precedes root cache reset. Publish both
    # native redraw markers LAST: the emulation can run between host writes.
    order={'stage_colour':0,'dirty_colour':1,'dirty':1,'zero':2,'one':3}
    for address,(kind,colour) in sorted(fields.items(),key=lambda row:order[row[1][0]]):
        before=memory.read_u32(address)
        if kind=='stage_colour':after=stage_colour(memory,flags,colour)
        elif not refresh:continue
        elif kind=='dirty_colour':after=before & ~0x00180080
        elif kind=='dirty':after=before & ~0x00100000
        else:after=int(kind=='one')
        if before!=after:
            memory.write_u32(address,after,expected=before,operation='game_land_ui');changed+=1
    _PENDING_REFRESH.discard(identity)
    _COMPLETED_REFRESH.add(identity)
    return {'status':'Game Land availability and clears displayed separately','changed_fields':changed,'visual_verified':False}
