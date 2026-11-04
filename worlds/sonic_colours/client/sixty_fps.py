"""Native frame interval overrides for the optional 60 FPS mode."""
import struct
from ..world_constants import load_data


def patches(occupied):
    from .native_dol import branch
    from .red_ring_spawn import scatter
    sites = [s for s in load_data('red_ring_spawn_sites.json')
             if not any(a < s['address']+8 and s['address'] < a+len(new)
                        for a, old, new in occupied)]
    result = []
    # Force the interval before the engine calculates its frame delta. The
    # original r3 argument is volatile; r4 is also scratch under the PPC ABI.
    for hook, original, words in (
        (0x803E19B0, 0x9421FFF0,
         [0x38600001, 0x3C808091, 0x9064DB08, 0x9421FFF0, 0]),
        (0x803E19E4, 0x806D9874,
         [0x38600001, 0x906D9874, 0x3C808091, 0x9064DB08, 0]),
    ):
        code = scatter(words, sites, hook+4)
        result.extend(code)
        used = {a for a, old, new in code}
        sites = [s for s in sites if s['address'] not in used]
        result.append((hook, struct.pack('>I', original),
                       struct.pack('>I', branch(hook, code[0][0]))))
    return result
