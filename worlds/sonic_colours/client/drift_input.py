import struct
from .capsule_refresh import PPC
HOOKS=(0x80066F20,0x80150588)
ORIGINAL=0x2C030000


def program(control):
    a=PPC()
    a.d(15,12,0,control>>16);a.d(24,12,12,control&65535)
    a.d(32,0,12,0);a.d(11,0,0,0);a.branch('done',0x41820000)
    a.d(32,0,12,4);a.d(28,0,0,128);a.branch('done',0x40820000)
    a.d(14,3,0,0)
    a.label('done');a.emit(ORIGINAL);a.emit(0)
    return a.finish()


def patches(control,occupied):
    from ..world_constants import load_data
    from .native_dol import branch
    from .native_events import scatter
    sites=load_data('drift_input_sites.json');words=program(control);result=[]
    used=0
    for hook in HOOKS:
        selected=sites[used:]
        chunks=scatter(words,selected,hook+4,compact=True)
        used+=len(chunks)
        result.append((hook,struct.pack('>I',ORIGINAL),struct.pack('>I',branch(hook,selected[0]['address']))))
        result.extend(chunks)
    if any(a<e+len(n) and e<a+len(new) for a,o,new in result for e,old,n in occupied):
        raise ValueError('Drift predicate overlaps another patch')
    return result


def planned_patches():
    from .native_dol import plan
    rows=plan()[0];start=next(i for i,row in enumerate(rows) if row[0]==HOOKS[0])
    from ..world_constants import load_data
    from .native_events import scatter
    count=len(scatter(program(0),load_data('drift_input_sites.json'),HOOKS[0]+4,compact=True))
    return rows[start:start+len(HOOKS)*(1+count)]
