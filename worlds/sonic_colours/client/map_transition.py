"""PAL optional world-map path cleanup when AP leaves the next node locked.

802693AC leaves actor+7EC null if there is no eligible outgoing path.
8026C904's -3 transition nevertheless dereferences it at 8026C93C.
Skip only the optional camera/path work, using the original cleanup at
8026C984. No save, waypoint, rank or availability state is changed here.
"""
HOOK = 0x8026C938
ORIGINAL = 0x806407EC
CLEANUP = 0x8026C984


def payload():
    # r3 is the displaced output. CR is overwritten by the original routine
    # before its next conditional branch. r12/CTR are volatile at this ABI.
    # The final word is replaced with the Gecko return branch to HOOK+4.
    return [ORIGINAL, 0x2C030000, 0x40820014,
            0x3D808026, 0x618CC984, 0x7D8903A6, 0x4E800420, 0]


def gecko_lines():
    words = payload()
    return [f'20{HOOK-0x80000000:06X} {ORIGINAL:08X}',
            f'C2{HOOK-0x80000000:06X} {len(words)//2:08X}'] + [
        f'{words[i]:08X} {words[i+1]:08X}' for i in range(0, len(words), 2)]
