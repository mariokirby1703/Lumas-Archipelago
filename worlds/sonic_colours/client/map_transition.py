"""PAL optional world-map path cleanup when AP leaves the next node locked.

802693AC leaves actor+7EC null if there is no eligible outgoing path.
8026C904's -3 transition nevertheless dereferences it at 8026C93C.
Skip only the optional camera/path work, using the original cleanup at
8026C984. No save, waypoint, rank or availability state is changed here.
"""
HOOK = 0x8026C938
ORIGINAL = 0x806407EC
CLEANUP = 0x8026C984


def installed(memory):
    from .gecko import inspect_c2
    return inspect_c2(memory, HOOK, ORIGINAL,
                      {'optional_map_path_cleanup': payload()},
                      label='optional world-map path cleanup')['installed']


def payload():
    # r3 is the displaced output. CR is overwritten by the original routine
    # before its next conditional branch. r12/CTR are volatile at this ABI.
    # The final word is replaced with the Gecko return branch to HOOK+4.
    return [ORIGINAL, 0x2C030000, 0x40820014,
            0x3D808026, 0x618CC984, 0x7D8903A6, 0x4E800420, 0]


def gecko_lines():
    words = payload()
    lines = [f'20{HOOK-0x80000000:06X} {ORIGINAL:08X}',
            f'C2{HOOK-0x80000000:06X} {len(words)//2:08X}'] + [
        f'{words[i]:08X} {words[i+1]:08X}' for i in range(0, len(words), 2)]
    words = update_payload()
    return lines + [f'20{UPDATE_HOOK-0x80000000:06X} {UPDATE_ORIGINAL:08X}',
                    f'C2{UPDATE_HOOK-0x80000000:06X} {len(words)//2:08X}'] + [
        f'{words[i]:08X} {words[i+1]:08X}' for i in range(0, len(words), 2)]

# Phase 1 dereferences the same optional path during each animation tick.
UPDATE_HOOK = 0x8026CA18
UPDATE_ORIGINAL = 0x80C407EC
NEXT_STATE = 0x8026CB6C

def update_payload():
    # Before the original fcmpu: CR is subsequently overwritten. r6 is the
    # displaced output; r12/CTR are volatile. The native completed-animation
    # path advances the state and constructs the normal return event.
    return [UPDATE_ORIGINAL, 0x2C060000, 0x40820014,
            0x3D808026, 0x618CCB6C, 0x7D8903A6, 0x4E800420, 0]

def update_installed(memory):
    from .gecko import inspect_c2
    return inspect_c2(memory, UPDATE_HOOK, UPDATE_ORIGINAL,
                      {'optional_map_path_update': update_payload()},
                      label='optional world-map path update')['installed']
