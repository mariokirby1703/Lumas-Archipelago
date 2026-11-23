"""Native frame interval overrides for the optional 60 FPS mode."""
import struct
from ..world_constants import load_data


def switch_patches(occupied, control):
    from .capsule_refresh import PPC
    from .native_events import scatter_mixed
    from .native_dol import branch
    sites=[s for s in (*load_data('native_event_sites.json'),*load_data('oneup_capture_sites.json'))
           if not any(p<s['address']+12 and s['address']<p+len(new) for p,_,new in occupied)]
    result=[]
    for setter,hook,original in ((True,0x803E19B0,0x9421FFF0),(False,0x803E19E4,0x806D9874)):
        a=PPC()
        a.d(37,1,1,-32);a.d(36,0,1,4);a.d(36,4,1,8);a.d(36,3,1,16)
        a.emit(0x7C000026);a.d(36,0,1,12)
        a.d(15,4,0,control>>16);a.d(24,4,4,control&65535)
        a.d(32,0,4,0);a.d(28,0,0,0xffff)
        a.d(11,0,0,2);a.branch('native',0x41820000)
        a.d(14,3,0,1)
        if not setter:a.d(36,3,13,-0x678C)
        a.branch('publish')
        a.label('native')
        # Off means the original argument / original getter, with no custom
        # timestep calculation. The engine retains its native scene timing.
        a.d(32,3,1,16) if setter else a.emit(original)
        a.label('publish')
        a.d(15,4,0,0x8091);a.d(38,3,4,-0x24F5)
        a.d(25,0,0,1)  # oris r0,r0,1: native consumption acknowledgement
        a.d(15,4,0,control>>16);a.d(24,4,4,control&65535);a.d(36,0,4,0)
        a.d(32,0,1,12);a.emit(0x7C0FF120)
        a.d(32,4,1,8);a.d(32,0,1,4);a.d(14,1,1,32)
        a.emit(original if setter else 0x4E800020);a.emit(0)
        code,used=scatter_mixed(a.finish(),sites,hook+4)
        sites=sites[used:]
        result.extend(code)
        result.append((hook,struct.pack('>I',original),struct.pack('>I',branch(hook,code[0][0]))))
    return result


def patches(occupied,legacy_word_write=False,control=None,correct_setter=True,native_switch=True):
    if control is not None and correct_setter and native_switch:
        return switch_patches(occupied,control)
    from .native_dol import branch
    from .red_ring_spawn import scatter
    sites = [s for s in load_data('red_ring_spawn_sites.json')
             if not any(a < s['address']+8 and s['address'] < a+len(new)
                        for a, old, new in occupied)]
    result = []
    # The published AR override changes only 8090DB0B. Preserve its adjacent
    # bytes; retain the old word-store form solely to recognize existing ISOs.
    vi_write = 0x9064DB08 if legacy_word_write else 0x9864DB0B
    # Force the interval before the engine calculates its frame delta. The
    # original r3 argument is volatile; r4 is also scratch under the PPC ABI.
    for hook, original, words in (
        (0x803E19B0, 0x9421FFF0,
         [0x38600001, 0x3C808091, vi_write, 0x9421FFF0, 0]),
        (0x803E19E4, 0x806D9874,
         [0x38600001, 0x906D9874, 0x3C808091, vi_write, 0]),
    ):
        code = scatter(words, sites, hook+4)
        result.extend(code)
        used = {a for a, old, new in code}
        sites = [s for s in sites if s['address'] not in used]
        result.append((hook, struct.pack('>I', original),
                       struct.pack('>I', branch(hook, code[0][0]))))
    if control is not None:
        from .capsule_refresh import PPC
        from .native_events import scatter_mixed
        a=PPC()
        a.d(37,1,1,-32);a.d(36,4,1,8);a.d(36,0,1,12)
        a.emit(0x7C000026);a.d(36,0,1,16)
        a.d(15,4,0,control>>16);a.d(24,4,4,control&65535)
        a.d(32,3,4,0);a.d(11,0,3,2);a.branch('sixty',0x40820000)
        a.d(15,4,0,0x3D08);a.d(24,4,4,0x8889);a.branch('publish')
        a.label('sixty');a.d(14,3,0,1)
        a.d(15,4,0,0x3C88);a.d(24,4,4,0x8889)
        a.label('publish');a.d(36,4,13,-0x6788);a.d(36,3,13,-0x678C)
        a.d(15,4,0,0x8091);a.d(38,3,4,-0x24F5)
        a.d(32,0,1,16);a.emit(0x7C0FF120)
        a.d(32,4,1,8);a.d(32,0,1,12);a.d(14,1,1,32)
        a.emit(0x4E800020);a.emit(0)
        sites=[s for s in load_data('native_event_sites.json')
               if not any(p<s['address']+12 and s['address']<p+len(new)
                          for p,_,new in (*occupied,*result))]
        code,_=scatter_mixed(a.finish(),sites,0x803E19E8)
        result=[r for r in result if r[0]!=0x803E19E4]
        result.extend(code)
        result.append((0x803E19E4,bytes.fromhex('806d9874'),
                       branch(0x803E19E4,code[0][0]).to_bytes(4,'big')))
        if correct_setter:
            a=PPC()
            a.d(37,1,1,-16);a.d(36,0,1,4)
            a.emit(0x7C000026);a.d(36,0,1,8)
            a.d(15,4,0,control>>16);a.d(24,4,4,control&65535)
            a.d(32,3,4,0);a.d(11,0,3,2);a.branch('selected',0x41820000)
            a.d(14,3,0,1)
            a.label('selected');a.d(15,4,0,0x8091);a.d(38,3,4,-0x24F5)
            a.d(32,0,1,8);a.emit(0x7C0FF120)
            a.d(32,0,1,4);a.d(14,1,1,16)
            a.emit(0x9421FFF0);a.emit(0)
            sites=[s for s in (*load_data('native_event_sites.json'),*load_data('oneup_capture_sites.json'))
                   if not any(p<s['address']+12 and s['address']<p+len(new)
                              for p,_,new in (*occupied,*result))]
            code,_=scatter_mixed(a.finish(),sites,0x803E19B4)
            result=[r for r in result if r[0]!=0x803E19B0]
            result.extend(code)
            result.append((0x803E19B0,bytes.fromhex('9421fff0'),
                           branch(0x803E19B0,code[0][0]).to_bytes(4,'big')))
    return result
