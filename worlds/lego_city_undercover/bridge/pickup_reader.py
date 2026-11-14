"""Native city-pickup binding derived from collection writer RVA 0x9a68d0.

Only the branch guarded by type flag 0x4000000 and object flag !0x200
uses this tile-byte encoding. Do not apply it to arbitrary story collectibles.
"""
import math
import struct
from copy import deepcopy
from inventory_reader import pointer,cstring
from scene_reader import player_scene,scene_component


def pickup_bit(x,y,width,index):
    if not (1<=width<=256 and 0<=x<width and 0<=y<256 and 0<=index<8):
        raise ValueError('Invalid native city pickup identity')
    bit=(y*width+x)*8+index
    if bit>=12800:raise ValueError('Pickup exceeds observed save payload')
    return bit


def read_loaded_pickups(read,base,scene=None):
    own_scene=scene is None
    scene=player_scene(read,base) if own_scene else scene
    component=scene_component(read,base,scene,0x17EC808)
    if not component or pointer(read,component)!=base+0xD89948:
        raise ValueError('Unsupported pickup scene component')
    manager=pointer(read,base+0x17EC808)
    bank=read(manager+0x120,1600)
    width=struct.unpack('<I',read(base+0x1165910,4))[0]
    definitions=pointer(read,pointer(read,base+0x1C9DF10))
    head=pointer(read,component+0xE0)
    level_owner=pointer(read,component+0x20)
    tile=pointer(read,level_owner+0xB18)
    scene_name=cstring(read,pointer(read,tile+0x68))
    node=head;rows=[];seen=set();links=[]
    while node:
        if node in seen or len(seen)>=4096:raise ValueError('Invalid pickup list')
        seen.add(node);data=read(node,0x198)
        if struct.unpack_from('<Q',data)[0]!=base+0xC2ED28:
            raise ValueError('Unknown loaded pickup layout')
        owner=struct.unpack_from('<Q',data,0x48)[0]
        if owner!=component:raise ValueError('Unexpected pickup owner')
        name=data[0x58:0x78].split(b'\0')[0].decode('ascii')
        position=struct.unpack_from('<3f',data,0x78)
        if not all(math.isfinite(v) for v in position):raise ValueError('Invalid pickup position')
        kind=data[0x193];flags=struct.unpack('<I',read(definitions+kind*128+0x18,4))[0]
        object_flags=struct.unpack_from('<H',data,0x158)[0];index=data[0x163]
        pickup_flags=struct.unpack_from('<H',data,0x160)[0]
        row=dict(address=hex(node),name=name,position=list(position),native_type=kind,
                 instance_flags=hex(object_flags),type_flags=hex(flags),local_index=index,
                 collection_bit=None,tile_name=scene_name,pickup_flags=hex(pickup_flags),
                 native_collected=bool(pickup_flags&2),status='not_in_verified_city_save_branch')
        if flags&0x4000000 and not object_flags&0x200 and index!=0xff:
            level_owner=pointer(read,owner+0x20)
            tile=pointer(read,level_owner+0xB18)
            x,y=read(tile+0x208,2)
            if x<width and y<38 and index<8:
                bit=pickup_bit(x,y,width,index)
                row.update(collection_bit=bit,tile_xy=[x,y],collected=bool(bank[bit//8]&(1<<(bit%8))),
                           tile_name=cstring(read,pointer(read,tile+0x68)),
                           status='native_writer_derived_binding')
        rows.append(row)
        next_node=struct.unpack_from('<Q',data,0x28)[0]
        links.append((node,next_node));node=next_node
    if ((own_scene and player_scene(read,base)!=scene) or pointer(read,component+0xE0)!=head or
            any(pointer(read,a+0x28)!=n for a,n in links) or read(manager+0x120,1600)!=bank):
        raise RuntimeError('Pickup state changed; retry')
    return dict(status='read',objects=rows,source='native writer 0x9a68d0',
                instance_positions_are_resource_space=True)


def read_city_pickups(read,base):
    """Walk bounded registered scene owners, including neighboring city tiles.

    Registry slots also contain non-level owners. Inaccessible/non-level slots
    are counted and excluded; the returned coverage is explicitly partial.
    """
    registry=pointer(read,base+0x1C402D8)
    raw=b''.join(read(registry+0x18+offset,4096) for offset in range(0,16384,4096))
    seen=set();components=set();rows=[];skipped=0;errors=[]
    system=pointer(read,base+0x17EC808)
    index=struct.unpack('<i',read(system+0xF4,4))[0]
    if not 0<=index<256:raise ValueError('Invalid pickup component index')
    for entry in struct.unpack('<2048Q',raw):
        if not entry:continue
        try:
            owner=pointer(read,entry+0xD8)
            if not owner or owner in seen:continue
            seen.add(owner)
            if not pointer(read,owner+0xB18):continue
            level=pointer(read,owner+0xBB0)
            table=pointer(read,pointer(read,level+0xA0)+0xC0)
            component=pointer(read,table+index*8)
            if not component or component in components:continue
            components.add(component)
            rows.extend(read_loaded_pickups(read,base,dict(level=level,table=table))['objects'])
        except (OSError,ValueError,RuntimeError,struct.error) as error:
            skipped+=1
            if len(errors)<5:errors.append(str(error))
    if pointer(read,base+0x1C402D8)!=registry:raise RuntimeError('Scene registry changed')
    return dict(status='read',objects=rows,components=len(components),skipped=skipped,
                sample_errors=errors,coverage='partial loaded scene registry',
                source='native city writer guards; cross-scene enumeration')


class PickupMemory:
    """Retain identity when an object disappears before the pickup poll.

    Never resolves conflicting identities for one bit by nearest distance.
    Reset on process/connection changes; consumers must also bind save slots.
    """
    def __init__(self):
        self.bindings={}
        self.tick=0

    def update(self,state):
        self.tick+=1
        if state.get('status')=='read':
            for row in state.get('objects',[]):
                bit=row.get('collection_bit')
                if bit is None:continue
                identity=(row.get('tile_name'),row['name'])
                self.bindings.setdefault(bit,{})[identity]=dict(deepcopy(row),last_seen_sample=self.tick)
        return dict(status='cached',objects=[deepcopy(row) for group in self.bindings.values() for row in group.values()],
                    conflicts=sorted(bit for bit,group in self.bindings.items() if len(group)>1),
                    sample=self.tick,scope='this connection only; identities are not proof of current presence')


def attach_source_identities(state,sources):
    lookup={}
    for row in sources:
        lookup.setdefault((row['tile_name'].lower().removesuffix('_tech'),row['name']),[]).append(row)
    for row in state.get('objects',[]):
        candidates=lookup.get((row.get('tile_name','').lower().removesuffix('_tech'),row['name']),[])
        matches={source['source_key'] for source in candidates
                 if source.get('native_type') in (None,row.get('native_type'))}
        row['source_candidates']=sorted(matches)
        row['source_key']=next(iter(matches)) if len(matches)==1 else None
        row['source_identity_evidence']='unique native tile/name match' if len(matches)==1 else 'unresolved'
    return state
