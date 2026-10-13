"""Restore witnessed physical pickups, never AP Red Ring counter items.

PAL 8015F16C/8015F18C: flags C-bank bits 320..499. Stage actor-state
8075A228 +91 is the native five-bit current collection bitmap.
The AP journal supplies restart durability; NAND flushing remains vanilla.
"""
from ..world_constants import BY_MISSION
from .memory import MemoryUnavailable


def witnessed(journal):
    epoch = journal.data.get('bootstrap', {}).get('epoch')
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
        if event.get('kind') != 'red_ring' or event.get('playthrough_epoch') not in epochs:
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
    if snapshot.scene == 'gameplay' and snapshot.death_state == 'alive' and guard.can_record_pickups(snapshot):
        rows = snapshot.evidence.get('native_data', {}).get('stage_objects', ())
        if len(rows) == 1 and rows[0].get('mission') == snapshot.actual_mission:
            stage, actor = rows[0].get('stage'), rows[0].get('actor_state')
            mask = masks.get(snapshot.actual_mission, 0)
            if mask and stage and actor and memory.read_u32(stage+0x114) == actor and memory.read_u32(actor) == 0x8075A228:
                result[actor+0x91] = (1, mask)
                context += (stage, actor)
    if guard.journal.data.get('save_identity') is not None and snapshot.scene in ('gameplay','world_map','global_map'):
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


def apply(memory, snapshot, guard):
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
            'nand_flush_verified':False}
