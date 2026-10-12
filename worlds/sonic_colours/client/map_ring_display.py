"""PAL world-map node badges independent of native cleared status.

802697A8 normally skips each node badge unless node +15C equals 4 (cleared).
Build the original native badge for normal Act nodes too. Native +5EC rank
validity still selects its empty-rank frame; +5FC supplies the physical mask.
No node availability, save, rank, score or completion fields are modified.
"""
from .capsule_refresh import PPC
from .gecko import inspect_c2

PREVIOUS_HOOK=0x8026A43C
PREVIOUS_ORIGINAL=0x3AD60001
HOOK=0x802697A8
ORIGINAL=0x40820198


def previous_payload():
    a=PPC()
    # CR0 is overwritten by the native loop immediately after continuation;
    # r12/CTR are ABI-volatile here, after a native call. r0 is untouched.
    a.d(11,0,21,0); a.branch('normal',0x40820000)
    a.d(10,0,24,5); a.branch('normal',0x41810000)
    a.d(10,0,22,5); a.branch('normal',0x41810000)
    a.d(15,12,0,0x8026); a.d(24,12,12,0xA394)
    a.emit(0x7D8903A6); a.emit(0x4E800420)
    a.label('normal'); a.emit(PREVIOUS_ORIGINAL); a.emit(0)
    return a.finish()


def payload():
    a=PPC()
    # Preserve the displaced bne semantics for completed nodes, using its
    # incoming CR0 from cmpwi r0,4. Other normal Act nodes may build the same
    # native badge. Native code supplies frame 5 for missing rank records.
    a.branch('draw',0x41820000)
    a.d(10,0,28,5); a.branch('skip',0x41810000)
    a.d(10,0,27,6); a.branch('skip',0x41810000)
    a.label('draw'); a.branch('return')
    a.label('skip')
    a.d(15,12,0,0x8026); a.d(24,12,12,0x9940)
    a.emit(0x7D8903A6); a.emit(0x4E800420)
    a.label('return'); a.emit(0x60000000); a.emit(0)
    return a.finish()


def installed(memory):
    return inspect_c2(memory,HOOK,ORIGINAL,{'physical_ring_node_badges':payload()},
                      label='world-map physical Ring node badges')['installed']


def previous_installed(memory):
    return inspect_c2(memory,PREVIOUS_HOOK,PREVIOUS_ORIGINAL,
                      {'physical_rings_without_rank':previous_payload()},
                      label='previous world-map detail Ring display')['installed']


def gecko_lines():
    words=payload()
    return [f'20{HOOK-0x80000000:06X} {ORIGINAL:08X}',
            f'C2{HOOK-0x80000000:06X} {len(words)//2:08X}']+[
        f'{words[i]:08X} {words[i+1]:08X}' for i in range(0,len(words),2)]
