"""PAL menu counts all 21 availability flags; native clears retain their tint.

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
            if address==0x802F0DD4 and word==0x7F64DB78:word=patched
            if word not in (original,patched):
                raise MemoryUnavailable(f'unknown_revision: Game Land menu at {address:#x}')
            observed.append(word==patched)
            data=data[:offset]+original.to_bytes(4,'big')+data[offset+4:]
    if observed and any(observed) and not all(observed) and observed not in ([True]*4+[False]*2,[True]*5+[False],[True]*3+[False,True,False]):
        raise MemoryUnavailable('unknown_revision: partially installed Game Land menu patches')
    return data


def gecko_lines():
    # Restore the native clear query: availability must not imply completion.
    # The client recolours available uncleared selection labels after the
    # native tint pass initializes their colour storage. Locked labels stay
    # transparent. The secondary records view
    # retains its original grey tint; it cannot launch a locked Act. Retain
    # recognition of the earlier transparent records patch above.
    return [f'04{address-0x80000000:06X} {(original if address==0x802F0D98 else 0x7F64DB78 if address==0x802F0DD4 else patched):08X}' for address,(original,patched) in PATCHES.items()
            if address!=0x802F0E00]
