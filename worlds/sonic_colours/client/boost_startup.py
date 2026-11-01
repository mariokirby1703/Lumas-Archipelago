"""Keep White Boost locked while the next native gauge is being created."""
import struct
from functools import lru_cache

from .capsule_refresh import PPC
from ..world_constants import load_data

KINDS = ('boost_use', 'boost_query', 'boost_add')
COMPARE = 0x7C033800


def program():
    a=PPC()
    # The surrounding gate already saves these scratch GPRs. The scattered
    # branches use CTR/r11/r12; keep its original CTR and PIC base intact.
    a.emit(0x7C0902A6);a.mr(6,12)
    a.d(11,0,7,0);a.branch('new_gauge',0x41820000)
    a.emit(COMPARE);a.branch('done')
    a.label('new_gauge');a.emit(0x7C031800)  # cmpw r3,r3
    a.label('done');a.mr(12,6);a.emit(0x7C0903A6);a.emit(0)
    return a.finish()


def apply(payload, hooks, occupied):
    from . import gameplay_controls
    from .native_dol import ARENA,branch
    from .red_ring_spawn import scatter
    data=bytearray(payload);result=[]
    for kind in KINDS:
        hook=next(h for h in hooks if h['hook']==gameplay_controls.HOOKS[kind][0])
        words,_=gameplay_controls.payload(kind)
        index=words.index(COMPARE)
        address=hook['target']+index*4
        if struct.unpack_from('>I',data,address-ARENA)[0]!=COMPARE:
            raise ValueError('White Boost startup comparison differs')
        sites=[site for site in load_data('red_ring_spawn_sites.json')
               if not any(a < site['address']+8 and site['address'] < a+len(new)
                          for a,old,new in (*occupied,*result))]
        code=scatter(program(),sites,address+4)
        struct.pack_into('>I',data,address-ARENA,branch(address,code[0][0]))
        result.extend(code)
    return bytes(data),result


@lru_cache(maxsize=6)
def words_for(kind,accessible=True):
    from . import gameplay_controls
    from .native_dol import plan,ARENA
    _,payload,_,hooks=plan(include_accessible_colors=accessible)
    hook=next(h for h in hooks if h['hook']==gameplay_controls.HOOKS[kind][0])
    offset=hook['target']-ARENA
    return list(struct.unpack('>'+'I'*(hook['size']//4),payload[offset:offset+hook['size']]))


@lru_cache(maxsize=1)
def planned_patches():
    from .native_dol import plan
    base=plan(include_boot_guards=False)
    from .white_capsule_spawn import planned_patches as capsules
    return apply(base[1],base[3],[*base[0],*capsules()])[1]
