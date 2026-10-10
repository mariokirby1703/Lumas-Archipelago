"""PAL ReleaseBoxSmall reconciliation, executed by Dolphin's Gecko C2 engine.

No host executable-memory writes. Dolphin installs the thunk and handles JIT
invalidation. The helper uses the original actor's model replacement and state
transition routines; it never copies actors, vtables or opened bytes.
"""
import struct
from .memory import MemoryUnavailable, valid_range

HOOK = 0x800D4824
ORIGINAL = 0x801F0128  # lwz r0,0x128(r31)
NATIVE_SIGNATURES = (
    (0x800132D8, 0x9421FFF0), (0x800132DC, 0x7C0802A6),
    (0x8003BAAC, 0x38000001), (0x8003BAB0, 0x88630090),
    (0x800D3DA4, 0x9421FF90), (0x800D3DA8, 0x7C0802A6),
    (0x800D3EB4, 0x9421FF90), (0x800D3EB8, 0x7C0802A6),
    (0x800D3FF8, 0x9421FEF0), (0x800D3FFC, 0x7C0802A6),
    (0x800D4298, 0x9421FFC0), (0x800D429C, 0x7C0802A6),
    (0x800D5490, 0x9421FFE0), (0x800D5494, 0x7C0802A6),
    (0x807613C8, 0x800D562C), (0x807613E0, 0x800D557C),
)


class PPC:
    def __init__(self):
        self.words, self.labels, self.fixups = [], {}, []
    def emit(self, word): self.words.append(word)
    def d(self, op, rt, ra, immediate): self.emit(op << 26 | rt << 21 | ra << 16 | immediate & 0xffff)
    def label(self, name): self.labels[name] = len(self.words) * 4
    def branch(self, name, condition=None):
        self.fixups.append((len(self.words), name, condition)); self.emit(0)
    def mr(self, rt, rs): self.emit(0x7C000378 | rs << 21 | rt << 16 | rs << 11)
    def call(self, address):
        self.d(15,12,0,address >> 16); self.d(24,12,12,address & 0xffff)
        self.emit(0x7D8903A6); self.emit(0x4E800421)  # mtctr r12; bctrl
    def finish(self):
        for index,name,condition in self.fixups:
            delta=self.labels[name]-index*4
            self.words[index]=(0x48000000 | delta & 0x3fffffc) if condition is None else condition | delta & 0xfffc
        return self.words


def payload_words():
    a=PPC()
    a.d(37,1,1,-0x60)  # private frame, preserve caller volatile GPRs/LR/CR/CTR
    a.emit(0x7C0802A6); a.d(36,0,1,8)
    a.emit(0x7C000026); a.d(36,0,1,12)
    a.emit(0x7C0902A6); a.d(36,0,1,16)
    for r in range(3,13): a.d(36,r,1,20+(r-3)*4)
    a.d(32,0,31,0); a.d(15,5,0,0x8076); a.d(14,5,5,0x1534)
    a.emit(0x7C002800); a.branch('end',0x40820000)
    a.d(34,0,31,0x110); a.d(11,0,0,0); a.branch('end',0x40820000)
    # Special multi/alternate capsules have different subtype/resource contracts.
    # +149 changes native use eligibility, not the model's colour contract.
    # +148/+14A use the multi-Wisp/alternate-content constructor instead.
    for offset in (0x148,0x14a):
        a.d(34,0,31,offset); a.d(11,0,0,0); a.branch('end',0x40820000)
    a.d(32,4,31,0x114); a.d(10,0,4,6); a.branch('end',0x41810000)
    a.d(32,3,31,0xb0); a.d(11,0,3,0); a.branch('end',0x41820000)
    a.d(32,0,3,0); a.d(15,5,0,0x8078); a.d(14,5,5,-0x2ed4)
    a.emit(0x7C002800); a.branch('end',0x40820000)  # cmpw r0,r5 model VT
    a.d(32,0,3,8); a.emit(0x7C00F800); a.branch('end',0x40820000)  # owner == r31
    a.d(32,3,31,0x34); a.d(11,0,3,0); a.branch('end',0x41820000)
    a.d(14,3,3,8); a.d(32,4,2,-0x7c48); a.call(0x800132D8)
    a.d(11,0,3,0); a.branch('end',0x41820000)
    a.d(32,4,31,0x114); a.call(0x8003BAAC)  # native permission query
    a.d(32,4,31,0xb0); a.d(32,0,4,0x88)  # constructor mode 0 ghost / 1 content
    a.emit(0x7C001800); a.branch('matched',0x41820000)
    a.d(10,0,0,1); a.branch('end',0x41810000)
    a.d(11,0,3,0); a.branch('lock',0x41820000)
    a.mr(3,31); a.d(32,4,31,0x34); a.d(14,5,0,1); a.call(0x800D3EB4)
    a.branch('interaction')
    a.label('matched')
    a.d(11,0,3,0); a.branch('end',0x41820000)
    a.d(32,0,31,0xb4); a.d(11,0,0,0); a.branch('end',0x40820000)
    a.label('interaction')
    # Ghosts never traverse 800D3CF8..3D08's native collision initialization.
    # Repair a previous model-only refresh too; do not duplicate body handles.
    a.d(32,0,31,0xb4); a.d(11,0,0,0); a.branch('state',0x40820000)
    a.mr(3,31); a.d(32,4,31,0x34); a.call(0x800D3FF8)
    a.label('state')
    # Constructor's default state, via the real transition function (exit/entry
    # callbacks), before native visibility/movement picks any specialized state.
    a.mr(3,31); a.d(15,4,0,0x8076); a.d(14,4,4,0x13c0); a.call(0x800D5490)
    a.mr(3,31); a.call(0x800D4298)  # select native available lifecycle state
    a.branch('end')
    a.label('lock')
    a.mr(3,31); a.call(0x800D3DA4)  # native ghost model, refcount-replace +B0
    a.mr(3,31); a.d(15,4,0,0x8076); a.d(14,4,4,0x13d8); a.call(0x800D5490)
    a.label('end')
    for r in range(3,13): a.d(32,r,1,20+(r-3)*4)
    a.d(32,0,1,16); a.emit(0x7C0903A6)
    a.d(32,0,1,12); a.emit(0x7C0FF120)
    a.d(32,0,1,8); a.emit(0x7C0803A6)
    a.d(14,1,1,0x60); a.emit(ORIGINAL)
    # Gecko patches the final zero word to branch back to HOOK+4.
    if len(a.words)%2 == 0: a.emit(0x60000000)
    a.emit(0)
    return a.finish()


def gecko_ini():
    words=payload_words()
    lines=['[Gecko]', '$AP PAL live coloured capsule refresh',
           '20000000 534E4350', '28000004 00003850', '28000006 00000000']
    lines += [f'20{address-0x80000000:06X} {word:08X}' for address,word in NATIVE_SIGNATURES]
    lines += [f'20{HOOK-0x80000000:06X} {ORIGINAL:08X}',
              f'C2{HOOK-0x80000000:06X} {len(words)//2:08X}']
    lines += [f'{words[i]:08X} {words[i+1]:08X}' for i in range(0,len(words),2)]
    lines += ['E0000000 80008000']
    from .progression_hook import gecko_lines
    lines += gecko_lines()
    lines += ['[Gecko_Enabled]', '$AP PAL live coloured capsule refresh', '$AP PAL authoritative progression']
    return '\n'.join(lines)+'\n'


def inspect_installed(memory):
    from .gecko import inspect_c2
    from ..world_constants import load_data
    variants={'current_collision_refresh':payload_words()}
    variants.update(load_data('capsule_hook_legacy.json'))
    result=inspect_c2(memory,HOOK,ORIGINAL,variants)
    memory.capsule_hook_observation=result
    return result


def installed(memory):
    return inspect_installed(memory)['installed']
