"""Recompute PAL area-map adjacency after AP changes waypoint statuses.

Runs after the native update has saved nonvolatile registers/FPRs, before
its first time-step load. No host calls into guest code or UI pointer writes.
"""
from .capsule_refresh import PPC

HOOK = 0x8026ADE4
ORIGINAL = 0x3FE08077


def payload():
    a = PPC()
    a.d(37, 1, 1, -0x30)
    a.d(36, 3, 1, 8); a.d(36, 4, 1, 12)
    a.emit(0x7C0802A6); a.d(36, 0, 1, 20)
    a.emit(0x48000005); base = len(a.words)*4
    a.emit(0x7FE802A6)  # r31 is saved by the native prologue
    a.d(32, 5, 3, 0)
    a.d(15, 6, 0, 0x8077); a.d(24, 6, 6, 0x73f8)
    a.emit(0x7C053000); a.branch('end', 0x40820000)
    # Resource path records must already exist before rebuilding adjacency.
    a.d(32, 5, 3, 0x694); a.d(11, 0, 5, 0)
    a.branch('end', 0x41820000)
    a.d(32, 5, 31, 0)  # cached actor identity
    a.emit(0x7C051800)
    a.d(14, 8, 0, 0); a.branch('same_actor', 0x41820000)
    a.d(14, 8, 0, 1)
    a.label('same_actor')
    # Seven exact comparisons; no hash collisions and no guessed UI offsets.
    for i in range(7):
        a.d(32, 5, 3, 0x1f8+i*0x9c)
        a.d(11, 0, 5, 1); a.branch('end', 0x41800000)
        a.d(11, 0, 5, 4); a.branch('end', 0x41810000)
        a.d(32, 6, 31, 4+i*4)
        a.emit(0x7C053000); a.branch(f'equal{i}', 0x41820000)
        a.d(14, 8, 0, 1)
        a.label(f'equal{i}')
    a.d(11, 0, 8, 0); a.branch('end', 0x41820000)
    a.d(36, 3, 31, 0)
    for i in range(7):
        a.d(32, 5, 3, 0x1f8+i*0x9c); a.d(36, 5, 31, 4+i*4)
    # 802693AC only clears unavailable path flags; it never re-enables them.
    # Restore the resource-existence predicate used by 80269330/80269338
    # before applying the native endpoint/permission filtering again.
    for i in range(7):
        a.d(32, 5, 3, 0x694+i*16); a.d(14, 6, 0, 0)
        a.d(11, 0, 5, 0); a.branch(f'path_absent{i}', 0x41820000)
        a.d(14, 6, 0, 1)
        a.label(f'path_absent{i}'); a.d(38, 6, 3, 0x690+i*16)
    a.call(0x802693AC)  # native path endpoints, availability and adjacency
    a.d(32, 3, 1, 8)
    a.call(0x80269F90)  # rebuild visible path vertices in existing buffers
    # That helper omits the current unlock-animation path. AP may enable it
    # after the native animation state has ended, so finish its vertices too.
    a.d(32, 3, 1, 8); a.d(32, 4, 3, 0x7ec)
    a.d(11, 0, 4, 0); a.branch('end', 0x41820000)
    a.d(32, 5, 4, 8); a.d(11, 0, 5, 0); a.branch('end', 0x41800000)
    a.d(11, 0, 5, 6); a.branch('end', 0x41810000)
    a.d(7, 5, 5, 16); a.emit(0x7C632A14)  # add r3,r3,r5
    a.d(36, 3, 1, 24)
    a.d(32, 4, 3, 0x698); a.d(32, 3, 3, 0x694)
    a.d(32, 5, 3, 0x18); a.d(48, 1, 3, 12); a.d(14, 6, 0, 0)
    a.call(0x80267880)
    a.d(32, 4, 1, 24); a.d(36, 3, 4, 0x69c)
    a.label('end')
    a.d(32, 0, 1, 20); a.emit(0x7C0803A6)
    a.d(32, 3, 1, 8); a.d(32, 4, 1, 12)
    a.d(14, 1, 1, 0x30); a.emit(ORIGINAL); a.branch('return')
    offset = len(a.words)*4
    for i, w in enumerate(a.words):
        if w >> 26 in (32, 36) and (w >> 16)&31 == 31:
            a.words[i] = (w & 0xffff0000) | ((w & 0xffff)+offset-base)
    for _ in range(8): a.emit(0)
    a.label('return'); a.emit(0)
    return a.finish()
