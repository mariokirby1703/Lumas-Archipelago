"""Read loaded SuperBuildGizmo completion; no native calls or writes."""
import json
import math
from pathlib import Path
import struct
from inventory_reader import pointer
from scene_reader import player_scene,scene_component

MANAGER_RVA=0x17EC978


def parse_superbuild(data,base):
    if len(data)!=0x1E8 or struct.unpack_from('<Q',data)[0]!=base+0xC300F8:
        raise ValueError('Unsupported SuperBuildGizmo layout')
    position=list(struct.unpack_from('<3f',data,0x78))
    if not all(math.isfinite(v) for v in position):raise ValueError('Invalid Super Build position')
    state=struct.unpack_from('<H',data,0x1E2)[0]
    flags=struct.unpack_from('<I',data,0x1E4)[0]
    value=struct.unpack_from('<f',data,0x1D4)[0]
    # Same scalar returned by script GetSuperBuildValue (0x116990) and
    # consumed by the build UI branch at 0x73326. Keep the observation separate
    # from guide quotes and from an unproven affordability rule.
    native_value=int(value) if math.isfinite(value) and 0<=value<=100000000 and value.is_integer() else None
    return dict(name=data[0x58:0x78].split(b'\0')[0].decode('ascii'),position=position,
                state=state,completion_flags=flags,complete=bool(state==5 and flags&4),
                native_build_value=native_value,build_value_evidence='GetSuperBuildValue 0x116990; compare against native cost popup',
                cost_logic_verified=False)


def bind_superbuild(row, bindings, mission):
    """Use exact instance identity; city observations additionally pin world position."""
    matches=set()
    for binding in bindings:
        if binding['native_name']!=row['name']:continue
        if 'position' in binding:
            if any(abs(a-b)>0.05 for a,b in zip(row['position'],binding['position'])):continue
        elif binding.get('mission')!=mission:continue
        matches.add(binding['objective'])
    return next(iter(matches)) if len(matches)==1 else None


def read_superbuilds(read,base,mission):
    scene=player_scene(read,base)
    primary=scene_component(read,base,scene,MANAGER_RVA)
    bindings=json.loads((Path(__file__).parent/'superbuild_bindings.json').read_text())
    components=set();rows=[]

    def collect(component):
        if not component or component in components:return
        if pointer(read,component)!=base+0xC30608:raise ValueError('Unknown Super Build component')
        components.add(component)
        head=pointer(read,component+0xE0);node=head;seen=set();pending=[]
        while node:
            if node in seen or len(seen)>=1024:raise ValueError('Invalid Super Build list')
            seen.add(node);data=read(node,0x1E8)
            if struct.unpack_from('<Q',data,0x48)[0]!=component:raise ValueError('Invalid Super Build owner')
            row=parse_superbuild(data,base);row['address']=hex(node)
            row['objective_name']=bind_superbuild(row,bindings,mission)
            row['binding_evidence']='exact instance binding' if row['objective_name'] else 'unmapped'
            pending.append(row);node=struct.unpack_from('<Q',data,0x28)[0]
        # Completion may change during construction. Never queue a transient state.
        for row in pending:
            current=read(int(row['address'],16)+0x1E2,6)
            if struct.unpack('<HI',current)!=(row['state'],row['completion_flags']):
                raise RuntimeError('Super Build state changed during snapshot')
        if pointer(read,component+0xE0)!=head:raise RuntimeError('Super Build list changed')
        rows.extend(pending)

    collect(primary)
    registry=pointer(read,base+0x1C402D8)
    raw=b''.join(read(registry+0x18+offset,4096) for offset in range(0,16384,4096))
    owners=set();skipped=0
    for entry in struct.unpack('<2048Q',raw):
        if not entry:continue
        try:
            owner=pointer(read,entry+0xD8)
            if not owner or owner in owners:continue
            owners.add(owner)
            if not pointer(read,owner+0xB18):continue
            level=pointer(read,owner+0xBB0)
            table=pointer(read,pointer(read,level+0xA0)+0xC0)
            component=scene_component(read,base,dict(table=table),MANAGER_RVA)
            collect(component)
        except (OSError,ValueError,RuntimeError,struct.error):
            skipped+=1
    if (player_scene(read,base)['level']!=scene['level'] or
            pointer(read,base+0x1C402D8)!=registry or
            b''.join(read(registry+0x18+offset,4096) for offset in range(0,16384,4096))!=raw):
        raise RuntimeError('Super Build scene registry changed during snapshot')
    return dict(status='read',records=rows,components=len(components),skipped=skipped,
                coverage='player scene and bounded registered city scenes',
                evidence='state setter 0x73140; state 5 / flag 4')
