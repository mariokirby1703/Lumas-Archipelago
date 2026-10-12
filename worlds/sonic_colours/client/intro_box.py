"""Act-2 ORC placement edit before native model/physics construction."""
import struct
from .memory import MemoryUnavailable, valid_range
from ..world_constants import load_data

SPEC = load_data('intro_act2_box.json')
ANCHORS = {(i,c):o for i,o,c in SPEC['anchors']}
ORIGINAL = struct.pack('>f', SPEC['position'][1])
RAISED = struct.pack('>f', SPEC['position'][1]+SPEC['lift'])
PREVIOUS_RAISED = struct.pack('>f', SPEC['position'][1]+20.0)
PLACEMENTS = (ORIGINAL, RAISED, PREVIOUS_RAISED)


def eligible(snapshot, guard, slot):
    return bool(slot['options'].get('movement_unlocks')
        and guard.can_record_pickups(snapshot))


def locate(memory, snapshot):
    from .native_read import read_actors
    if (snapshot.scene != 'gameplay' or not snapshot.scene_verified
            or snapshot.death_state != 'alive' or snapshot.actual_mission != SPEC['mission']):
        raise MemoryUnavailable('intro box requires verified living Act 2')
    rows=snapshot.evidence.get('native_data',{}).get('stage_objects',[])
    if len(rows)!=1 or rows[0].get('mission') != SPEC['mission']:
        raise MemoryUnavailable('intro box stage ownership unavailable')
    actors=read_actors(memory, rows[0]['context']); sources=set(); targets=[]
    for actor in actors:
        wrapper=memory.read_u32(actor+0x64)
        if not valid_range(wrapper,0x18) or memory.read_u32(wrapper+4)!=actor:continue
        record=memory.read_u32(wrapper+8)
        if not valid_range(record,0x28):continue
        key=(memory.read_u32(record)&0xfffff,memory.read_u32(record+4))
        offset=ANCHORS.get(key)
        if offset is None:continue
        base=record-offset
        if not valid_range(base,SPEC['file_size']):continue
        if (memory.read_u32(base)!=SPEC['file_size']
            or memory.read_bytes(base+0x18,4)!=b'BINA'
            or memory.read_bytes(base+0x20,4)!=b'SOBJ'
            or memory.read_u32(base+0x28)!=SPEC['dict_count']
            or memory.read_u32(base+0x38)!=SPEC['object_count']
            or memory.read_u32(base+0x40)!=SPEC['instance_count']):continue
        sources.add(base)
        if key==(SPEC['object_id'],SPEC['class_id']):targets.append(actor)
    if len(sources)!=1:raise MemoryUnavailable('intro box ORC resource not uniquely owned')
    base=sources.pop();record=base+SPEC['record_offset'];vector=base+SPEC['vector_offset']
    if (memory.read_u32(record)&0xfffff != SPEC['object_id']
            or memory.read_u32(record+4)!=SPEC['class_id']
            or memory.read_u32(record+0x1c)!=1
            or memory.read_u32(record+0x18)!=vector):
        raise MemoryUnavailable('intro box exact placement pointer mismatch')
    pos=memory.read_bytes(vector,12)
    expected=struct.pack('>3f',*SPEC['position'])
    if pos[:4]!=expected[:4] or pos[8:]!=expected[8:] or pos[4:8] not in PLACEMENTS:
        raise MemoryUnavailable('intro box placement does not match original PAL data')
    return base,vector+4,tuple(targets)


def apply(memory,snapshot,guard,slot):
    if snapshot.actual_mission!=SPEC['mission'] or snapshot.scene!='gameplay':
        return {'status':'not in Act 2','applied':False}
    if not guard.can_record_pickups(snapshot):
        return {'status':'waiting for attributed playthrough','applied':False}
    base,address,actors=locate(memory,snapshot)
    desired=RAISED if eligible(snapshot,guard,slot) else ORIGINAL
    current=memory.read_bytes(address,4)
    if current==desired:
        return {'status':'Act 2 box raised' if desired==RAISED else 'original placement',
                'applied':desired==RAISED,'lift':SPEC['lift'] if desired==RAISED else 0,
                'native_collision_verified':False}
    if actors:
        return {'status':'restart Act 2: box already constructed; refusing model/physics desynchronization',
                'applied':False,'native_collision_verified':False}
    memory.write_bytes_verified(address,desired,expected=current,operation='intro_box_placement')
    return {'status':'raised native spawn placement' if desired==RAISED else 'restored original spawn placement',
            'applied':desired==RAISED,'lift':SPEC['lift'] if desired==RAISED else 0,
            'native_collision_verified':False}
