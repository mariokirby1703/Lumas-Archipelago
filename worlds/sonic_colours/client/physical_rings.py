"""Restore witnessed physical pickups, never AP Red Ring counter items.

PAL 8015F16C/8015F18C: flags C-bank bits 320..499. Stage actor-state
8075A228 +91 is the native five-bit current collection bitmap.
The AP journal supplies restart durability; NAND flushing remains vanilla.
"""
from ..world_constants import BY_MISSION
from .memory import MemoryUnavailable


def witnessed(journal):
    binding=journal.data.get('native_binding') or {}
    epoch = journal.data.get('bootstrap', {}).get('epoch') or binding.get('bootstrap_epoch')
    recovered=(journal.data.get('binding_recovery')=='exact native witness from prior slot-data digest'
               and journal.data.get('save_identity')==binding.get('id') and epoch is not None)
    # Only epochs explicitly recorded by this authenticated seed's journal.
    # A fresh New Game changes native playthrough identity, not earned AP pickups.
    epochs={epoch} if epoch is not None else set()
    epochs.update(p.get('epoch') for p in journal.data.get('prior_prologues',()) if p.get('epoch'))
    epochs.update(p.get('bootstrap',{}).get('epoch') for p in journal.data.get('prior_playthroughs',())
                  if p.get('bootstrap',{}).get('epoch'))
    masks = {}
    if not epochs:
        return masks
    for event in journal.data.get('pickup_events', ()):
        event_epoch=event.get('playthrough_epoch')
        # The initial recovery build recorded witnessed pickups without the
        # restored bootstrap epoch. Only that exact bound recovery can repair them.
        if event_epoch is None and recovered:event_epoch=epoch
        if event.get('kind') != 'red_ring' or event_epoch not in epochs:
            continue
        mission, ring = event.get('mission'), event.get('ring')
        stage = BY_MISSION.get(mission, {})
        if not stage.get('normal') or type(ring) is not int or not 1 <= ring <= 5:
            continue
        masks[mission] = masks.get(mission, 0) | (1 << (ring-1))
    return masks


def targets(memory, snapshot, guard):
    if not snapshot.scene_verified or snapshot.stable_polls < 3:
        raise MemoryUnavailable('physical rings: unstable scene')
    masks = witnessed(guard.journal)
    result = {}
    context = (snapshot.session, snapshot.stage_epoch, snapshot.actual_mission)
    if not getattr(memory,'native_patch',None) and snapshot.scene == 'gameplay' and snapshot.death_state == 'alive' and guard.can_record_pickups(snapshot):
        rows = snapshot.evidence.get('native_data', {}).get('stage_objects', ())
        if len(rows) == 1 and rows[0].get('mission') == snapshot.actual_mission:
            stage, actor = rows[0].get('stage'), rows[0].get('actor_state')
            mask = masks.get(snapshot.actual_mission, 0)
            if mask and stage and actor and memory.read_u32(stage+0x114) == actor and memory.read_u32(actor) == 0x8075A228:
                result[actor+0x91] = (1, mask)
                context += (stage, actor)
    if guard.journal.data.get('save_identity') is not None and (snapshot.scene in ('world_map','global_map') or not getattr(memory,'native_patch',None) and snapshot.scene=='gameplay'):
        guard.check(snapshot)
        chain = memory.resolve_flags_ptr()
        if tuple(snapshot.evidence.get('chain', ())) != chain:
            raise MemoryUnavailable('physical rings: selected save changed')
        context += (chain,)
        for mission, mask in masks.items():
            stage = BY_MISSION[mission]
            for ring in range(5):
                if mask & (1 << ring):
                    bit = 320 + stage['zone_index']*30 + (stage['slot']-1)*5 + ring
                    address = chain[-1]+0x10+(bit//32)*4
                    result[address] = (4, result.get(address, (4,0))[1] | (1 << (bit%32)))
    return result, context


def apply(memory, snapshot, guard, runtime=None):
    restore=None
    if (runtime is not None and (getattr(memory,'native_patch',None) or {}).get('physical_ring_restore')
            and snapshot.scene=='gameplay' and snapshot.death_state=='alive'
            and guard.can_record_pickups(snapshot)):
        restore=publish_restore(runtime,memory)
    elif getattr(memory,'native_patch',None) and not memory.native_patch.get('physical_ring_restore'):
        restore={'status':'Repatch ISO for game-thread Red Ring restoration'}
    allowed, _ = targets(memory, snapshot, guard)
    changed = 0
    for address, (size, mask) in allowed.items():
        before = memory.read_bytes(address, size)
        value = int.from_bytes(before, 'big') | mask
        if value != int.from_bytes(before, 'big'):
            memory.write_bytes_verified(address, value.to_bytes(size,'big'), expected=before,
                                        operation='physical_ring_collection')
            changed += 1
    return {'status':'witnessed physical collections projected', 'changed_fields':changed,
            'nand_flush_verified':False,'native_restore':restore}


def mission_tag(mission):
    return int.from_bytes(mission[3:].encode('ascii'),'big')<<8


def restore_base(memory):
    if not (getattr(memory,'native_patch',None) or {}).get('physical_ring_restore'):
        raise MemoryUnavailable('Repatch ISO for game-thread Red Ring restoration')
    from .native_events import address
    return address(memory)-12


def restore_owner(memory,snapshot,guard):
    if (snapshot.scene!='gameplay' or snapshot.death_state!='alive'
            or not guard.can_record_pickups(snapshot)):
        raise MemoryUnavailable('Red Ring restore awaits attributed living stage')
    if not BY_MISSION.get(snapshot.actual_mission,{}).get('normal'):
        raise MemoryUnavailable('Red Ring restore requires a Story Act')
    rows=snapshot.evidence.get('native_data',{}).get('stage_objects',[])
    row=next(iter(rows),{})
    stage,actor,serial=row.get('stage'),row.get('actor_state'),row.get('player_actor_id')
    if (not stage or not actor or not serial or memory.read_u32(stage+0x114)!=actor
            or memory.read_u32(actor)!=0x8075A228 or memory.read_u32(actor+0x38)!=serial):
        raise MemoryUnavailable('Red Ring restore stage owner changed')
    name=memory.read_ptr_checked(stage+0x4c,7)
    if memory.read_bytes(name,7)!=snapshot.actual_mission.encode('ascii')+b'\0':
        raise MemoryUnavailable('Red Ring restore mission changed')
    return (snapshot.session,snapshot.save_identity,snapshot.stage_epoch,snapshot.actual_mission,serial,actor)


def publish_restore(runtime,memory):
    import struct
    owner=restore_owner(memory,runtime.snapshot,runtime.guard);base=restore_base(memory)
    current=struct.unpack('>3I',memory.read_bytes(base,12))
    if (getattr(runtime,'_physical_ring_owner',None)==owner and current[:2]==owner[4:]
            and current[2]&~31==mission_tag(owner[3])):
        return {'status':'game-thread restore active'}
    mask=witnessed(runtime.journal).get(owner[3],0)
    desired=(owner[4],owner[5],mission_tag(owner[3])|mask)
    if current[0]:memory.write_u32(base,0,expected=current[0],operation='physical_ring_restore')
    for offset,value in ((4,desired[1]),(8,desired[2]),(0,desired[0])):
        before=memory.read_u32(base+offset)
        if before!=value:memory.write_u32(base+offset,value,expected=before,operation='physical_ring_restore')
    runtime._physical_ring_owner=owner
    return {'status':'game-thread restore armed','mask':mask}


def observe_retained(runtime,memory):
    from dataclasses import replace
    import struct
    owner=getattr(runtime,'_physical_ring_owner',None)
    snap=runtime.snapshot
    if (not owner or owner[:2]!=(snap.session,snap.save_identity)
            or not runtime.guard.can_record(snap)):return
    base=restore_base(memory)
    serial,actor,mask=struct.unpack('>3I',memory.read_bytes(base,12))
    if (serial,actor)!=owner[4:] or mask&~31!=mission_tag(owner[3]):return
    mask &= 31
    runtime.observe_pickups(replace(snap,stage_epoch=owner[2],actual_mission=owner[3],
        pickup_verified=True,active_rings={owner[3]:frozenset(i+1 for i in range(5) if mask&(1<<i))}))
