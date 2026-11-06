"""Native frame interval overrides for the optional 60 FPS mode."""
import struct
from ..world_constants import load_data


def patches(occupied,legacy_word_write=False):
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
    return result
