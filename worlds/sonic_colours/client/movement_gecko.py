"""Dolphin-installed PAL C2 movement + Game Land Speed V11 native-request diagnostics build.

Do not enable together with the original four-group Gecko export. Movement retains Grand Map refresh and every gameplay hook; an ABI-sized
capsule helper and compact request checks retain Game Land's speed UI while fitting codehandler's 3256-byte limit. This file intentionally does not attempt to enlarge Gecko low memory.
"""
import re
from .capsule_refresh import gecko_ini as original_export
from .gameplay_controls import HOOKS
from .map_refresh import HOOK as MAP_HOOK
from .movement_gate import HOOK as MOVEMENT_HOOK, gecko_lines

CAPACITY_BYTES = 0x3000 - (0x1800 + 2880) - 8
OMITTED = set()


def pairs(text):
    return [tuple(int(word, 16) for word in line.split()) for line in text.splitlines()
            if re.fullmatch(r'[0-9A-F]{8} [0-9A-F]{8}', line)]


def movement_ini():
    cleaned = original_export(compact_capsule=True).splitlines()
    marker = '[Gecko_Enabled]'
    if cleaned.count(marker) != 1:
        raise ValueError('unexpected Gecko section layout')
    # Insert in existing guarded scope BEFORE its final E0; no extra group.
    final_close = cleaned.index('E0000000 80008000', cleaned.index('$AP PAL Eggman Heart pickup capture'))
    cleaned[final_close:final_close] = gecko_lines()
    # Four owner-gated hooks are inert until the client authenticates the
    # complete PAL executable and exact installed payload. Their redundant
    # nested install comparisons are omitted to fit Swim in the stock arena;
    # retain the full disc guard and first install guard, plus all ungated
    # map/transition guards. Standalone exporters keep their comparisons.
    for kind in ('speed_get', 'speed_set', 'speed_ui', 'boost_add','boost_query'):
        hook, original = HOOKS[kind]
        cleaned.remove(f'20{hook-0x80000000:06X} {original:08X}')
    from . import progression_hook,medal_hook,movement_gate
    for module in (progression_hook,medal_hook,movement_gate):
        cleaned.remove(f'20{module.HOOK-0x80000000:06X} {module.ORIGINAL:08X}')
    result = '\n'.join(cleaned)+'\n'
    raw = pairs(result)
    if len(raw)*8 > CAPACITY_BYTES:
        raise ValueError(f'movement Gecko profile too large: {len(raw)*8} > {CAPACITY_BYTES}')
    starts=[x for x,_ in raw if (x>>24)==0xc2]
    if starts.count(0xc2000000 | (MOVEMENT_HOOK-0x80000000)) != 1:
        raise ValueError('movement Gecko C2 not exactly once')
    for omitted in OMITTED:
        if 0xc2000000 | (omitted-0x80000000) in starts:
            raise ValueError('removed hook remained installed')
    return result


if __name__=='__main__':
    from pathlib import Path
    path=Path(__file__).resolve().parents[1]/'data'/'SNCP8P_movement_request_gate_v11.ini'
    contents=movement_ini()
    path.write_text(contents,encoding='utf-8')
    print(f'Wrote {path}: {len(pairs(contents))*8}/{CAPACITY_BYTES} bytes')
