"""PAL menu counts all 21 availability flags and tints unavailable Act nodes.

Stage columns are a contiguous prefix, matching the generated linear gates
and legacy vanilla thresholds. No clears, scores, ranks or medals are written.
"""
from .memory import MemoryUnavailable

PATCHES={
    0x802ED70C:(0x3B000001,0x3B000000), # count from Stage 1, not Stage 2
    0x802ED79C:(0x38160007,0x38160000), # no seven unconditional free entries
    0x802EDA78:(0x4BE71295,0x8077012C), # menu enabled iff available count >0
    0x802F0D98:(0x4BE6E235,0x4BE6E105), # tint unavailable nodes via bank A
    0x802F0DD4:(0x3882EB40,0x3882EB58), # native RGBA zero: transparent locked node
    0x802F0E00:(0x3882EB40,0x3882EB58), # second native view of the same node
}


def normalize(memory,data,base):
    observed=[]
    for address,(original,patched) in PATCHES.items():
        if base<=address<base+len(data):
            offset=address-base;word=int.from_bytes(data[offset:offset+4],'big')
            if word not in (original,patched):
                raise MemoryUnavailable(f'unknown_revision: Game Land menu at {address:#x}')
            observed.append(word==patched)
            data=data[:offset]+original.to_bytes(4,'big')+data[offset+4:]
    if observed and any(observed) and not all(observed) and observed not in ([True]*4+[False]*2,[True]*5+[False]):
        raise MemoryUnavailable('unknown_revision: partially installed Game Land menu patches')
    return data


def gecko_lines():
    # The selection view remains transparent. The secondary records view
    # retains its original grey tint; it cannot launch a locked Act. Retain
    # recognition of the earlier transparent records patch above.
    return [f'04{address-0x80000000:06X} {patched:08X}' for address,(_,patched) in PATCHES.items()
            if address!=0x802F0E00]
