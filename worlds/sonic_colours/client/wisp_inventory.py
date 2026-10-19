"""Discard an unowned held colour using PAL 80101360's inventory fields.

No native calls or executable writes. Reconcile only a stable living normal
Sonic, never while a Wisp transformation/death transition owns the model.
Normal boost energy (+8) and its maximum (+14) are preserved.
"""
import math
import struct
from .memory import MemoryUnavailable
from ..world_constants import NATIVE_COLOURS
from ..wisps import wisp_level


def owner(memory,snapshot,guard):
    guard.check_stats(snapshot)
    if not snapshot.scene_verified or snapshot.boost_address is None:
        raise MemoryUnavailable('Wisp inventory requires verified gameplay')
    row=next(iter(snapshot.evidence.get('native_data',{}).get('stage_objects',[])),{})
    player=row.get('player',{})
    if player.get('mode')!=0 or player.get('boost_address')!=snapshot.boost_address:
        raise MemoryUnavailable('Wisp inventory awaits normal Sonic inventory')
    from .movement_gate import observed
    state=observed(memory,player['actor'])
    current,requested=state['current_id'],state['requested_id']
    ordinary=lambda state:state in range(64) and state not in (24,25,26)
    if not ordinary(current) or not (requested==-1 or ordinary(requested)):
        raise MemoryUnavailable('Wisp inventory awaits an ordinary Sonic state')
    model=snapshot.boost_address-8
    if snapshot.boost_max_address!=model+0x14 or memory.read_u32(model)!=0x80763A18:
        raise MemoryUnavailable('Wisp inventory boost model changed')
    # Re-resolve the actor/stats provider rather than trusting a sampled model.
    actor=player['actor'];stats=memory.read_ptr_checked(actor+0x8c,0x34)
    if (memory.read_u32(actor)!=0x8075AEF8 or stats!=player.get('stats')
            or memory.read_u32(stats)!=0x8075E088 or memory.read_u32(stats+0x24)!=0
            or memory.read_ptr_checked(stats+0x30,0x64)!=model):
        raise MemoryUnavailable('Wisp inventory owner changed')
    return (snapshot.session,snapshot.stage_epoch,actor,stats,model,state['request_machine'])


def apply(memory,snapshot,guard,owned,slot):
    if snapshot.scene!='gameplay' or snapshot.death_state!='alive':
        return {'status':'awaiting living gameplay','cleared':False}
    player=next(iter(snapshot.evidence.get('native_data',{}).get('stage_objects',[])),{}).get('player',{})
    held=player.get('held_wisp',-1)
    if held==-1:
        pending=getattr(memory,'_wisp_inventory_pending_redraw',None)
        if pending:
            context=owner(memory,snapshot,guard)
            if context==pending:
                _notify(memory,context)
            else:memory._wisp_inventory_pending_redraw=None
        return {'status':'empty','cleared':False}
    if type(held) is not int or held not in range(len(NATIVE_COLOURS)):
        raise MemoryUnavailable('Unknown held Wisp colour')
    colour=NATIVE_COLOURS[held]
    if wisp_level(owned['counts'],colour,slot['options']):
        return {'status':'owned Wisp retained','colour':colour,'cleared':False}
    context=owner(memory,snapshot,guard);model=context[4]
    before=memory.read_bytes(model+0xc,0x1c)
    if struct.unpack_from('>i',before,12)[0]!=held:
        raise MemoryUnavailable('Held Wisp changed before clearing')
    # The native clear routine moves the old colour to +20 for its exit/HUD
    # transition, looks up its duration, and clears current/pending slots.
    duration_ptr=memory.read_u32(model+0x28+held*8)
    duration=memory.read_f32(duration_ptr) if duration_ptr else 0.
    if not math.isfinite(duration) or not 0<=duration<=3600:
        raise MemoryUnavailable('Invalid native Wisp duration')
    after=bytearray(before)
    struct.pack_into('>ff',after,0,duration,0.)
    struct.pack_into('>iiiI',after,12,-1,-1,held,0)
    if getattr(memory,'_wisp_inventory_transaction',None) is not None:
        raise MemoryUnavailable('Nested Wisp inventory transaction')
    memory._wisp_inventory_transaction={'owner':context,'model':model,'values':{model+0xc:bytes(after)}}
    memory._wisp_inventory_pending_redraw=context
    try:
        memory.write_bytes_verified(model+0xc,bytes(after),expected=before,operation='wisp_inventory')
    finally:memory._wisp_inventory_transaction=None
    _notify(memory,context)
    return {'status':'unowned Wisp discarded','colour':colour,'cleared':True}


def _notify(memory,context):
    model=context[4];flags=memory.read_u32(model+0x60)
    memory._wisp_inventory_transaction={'owner':context,'model':model,'values':{model+0x60:struct.pack('>I',flags|1)}}
    try:
        if not flags&1:memory.write_u32(model+0x60,flags|1,expected=flags,operation='wisp_inventory')
        memory._wisp_inventory_pending_redraw=None
    finally:memory._wisp_inventory_transaction=None
