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


def read_superbuilds(read,base,mission):
    scene=player_scene(read,base)
    component=scene_component(read,base,scene,MANAGER_RVA)
    if not component:return dict(status='read',records=[])
    if pointer(read,component)!=base+0xC30608:raise ValueError('Unknown Super Build component')
    bindings=json.loads((Path(__file__).parent/'superbuild_bindings.json').read_text())
    head=pointer(read,component+0xE0);node=head;seen=set();rows=[]
    while node:
        if node in seen or len(seen)>=1024:raise ValueError('Invalid Super Build list')
        seen.add(node);data=read(node,0x1E8)
        if struct.unpack_from('<Q',data,0x48)[0]!=component:raise ValueError('Invalid Super Build owner')
        row=parse_superbuild(data,base);row['address']=hex(node)
        matches={r['objective'] for r in bindings if r['mission']==mission and r['native_name']==row['name']}
        row['objective_name']=next(iter(matches)) if len(matches)==1 else None
        row['binding_evidence']='live mine gondola report; exact mission/name' if matches else 'unmapped'
        rows.append(row);node=struct.unpack_from('<Q',data,0x28)[0]
    if player_scene(read,base)['level']!=scene['level'] or pointer(read,component+0xE0)!=head:
        raise RuntimeError('Super Build scene changed during snapshot')
    return dict(status='read',records=rows,evidence='state setter 0x73140; state 5 / flag 4')
