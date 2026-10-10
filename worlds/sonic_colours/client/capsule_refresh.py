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
    (0x800D517C, 0x9421FFC0), (0x800D5180, 0x7C0802A6),
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
    # Keep save slots above the native callee's outgoing-argument home area.
    a.d(37,1,1,-0x1a0)
    a.emit(0x7C0802A6); a.d(36,0,1,0x40)
    a.emit(0x7C000026); a.d(36,0,1,0x44)
    a.emit(0x7C0902A6); a.d(36,0,1,0x48)
    for r in range(3,13): a.d(36,r,1,0x4c+(r-3)*4)
    a.emit(0x7C10E2A6); a.d(36,0,1,0x180)  # save GQR0
    a.d(14,0,0,0); a.emit(0x7C10E3A6)
    for r in range(14):
        a.d(54,r,1,0x80+r*8)  # volatile FPR double component
        a.d(60,r,1,0x100+r*8)  # both paired-single components, GQR0=float
    a.emit(0xFC00048E); a.d(54,0,1,0xf0)  # mffs f0; save FPSCR
    a.d(32,0,31,0); a.d(15,5,0,0x8076); a.d(14,5,5,0x1534)
    a.emit(0x7C002800); a.branch('end',0x40820000)
    a.d(34,0,31,0x110); a.d(11,0,0,0); a.branch('end',0x40820000)
    # Special multi/alternate capsules have different subtype/resource contracts.
    # +149 changes native use eligibility, not the model's colour contract.
    # +148/+14A use the multi-Wisp/alternate-content constructor instead.
    for offset in (0x148,0x14a):
        a.d(34,0,31,offset); a.d(11,0,0,0); a.branch('end',0x40820000)
    a.d(32,4,31,0x114); a.d(11,0,4,-1); a.branch('white',0x41820000)
    a.d(10,0,4,6); a.branch('end',0x41810000)
    a.branch('model')
    a.label('white')
    # White is signed -1; never route it through the coloured permission query.
    a.emit(0x48000005); pic_base = len(a.words)*4
    a.emit(0x7D8802A6); pic_fix = len(a.words); a.d(14,12,12,0)
    a.d(32,6,12,0); a.d(11,0,6,0); a.branch('end',0x41820000)
    a.d(34,6,6,0); a.d(32,7,12,4)
    a.emit(0x7C063800); a.branch('end',0x40820000)
    a.d(32,3,12,8); a.d(36,3,1,0x74)
    a.label('model')
    a.d(32,3,31,0xb0); a.d(11,0,3,0); a.branch('end',0x41820000)
    a.d(32,0,3,0); a.d(15,5,0,0x8078); a.d(14,5,5,-0x2ed4)
    a.emit(0x7C002800); a.branch('end',0x40820000)  # cmpw r0,r5 model VT
    a.d(32,0,3,8); a.emit(0x7C00F800); a.branch('end',0x40820000)  # owner == r31
    a.d(32,3,31,0x34); a.d(11,0,3,0); a.branch('end',0x41820000)
    a.d(14,3,3,8); a.d(32,4,2,-0x7c48); a.call(0x800132D8)
    a.d(11,0,3,0); a.branch('end',0x41820000)
    a.d(32,4,31,0x114); a.d(11,0,4,-1); a.branch('white_permission',0x41820000)
    a.call(0x8003BAAC)  # native coloured permission query
    a.branch('permission_ready')
    a.label('white_permission'); a.d(32,3,1,0x74)
    a.label('permission_ready')
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
    # Ghost entry disables EXISTING bodies through 800D517C(actor, 0).
    # Creating a body only when absent does not restore those registrations.
    # Use the native wrapper/physics registration routine, then allow native
    # lifecycle selection to apply any specialized visibility/movement gates.
    a.mr(3,31); a.d(14,4,0,1); a.call(0x800D517C)
    # Constructor's default state, via the real transition function (exit/entry
    # callbacks), before native visibility/movement picks any specialized state.
    a.mr(3,31); a.d(15,4,0,0x8076); a.d(14,4,4,0x13c0); a.call(0x800D5490)
    a.mr(3,31); a.call(0x800D4298)  # select native available lifecycle state
    a.branch('end')
    a.label('lock')
    a.mr(3,31); a.call(0x800D3DA4)  # native ghost model, refcount-replace +B0
    a.mr(3,31); a.d(15,4,0,0x8076); a.d(14,4,4,0x13d8); a.call(0x800D5490)
    a.label('end')
    a.d(14,0,0,0); a.emit(0x7C10E3A6)
    a.d(50,0,1,0xf0); a.emit(0xFDFE058E)  # restore FPSCR
    for r in range(14):
        a.d(56,r,1,0x100+r*8)
        a.d(50,r,1,0x80+r*8)
    a.d(32,0,1,0x180); a.emit(0x7C10E3A6)
    for r in range(3,13): a.d(32,r,1,0x4c+(r-3)*4)
    a.d(32,0,1,0x48); a.emit(0x7C0903A6)
    a.d(32,0,1,0x44); a.emit(0x7C0FF120)
    a.d(32,0,1,0x40); a.emit(0x7C0803A6)
    a.d(14,1,1,0x1a0); a.emit(ORIGINAL)
    a.branch('return')
    data = len(a.words)*4; a.words[pic_fix] |= (data-pic_base)&0xffff
    for _ in range(3): a.emit(0)  # owner container, selected index, White permission
    a.label('return')
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
    from .gameplay_controls import gecko_lines as control_lines
    lines += control_lines()
    from .medal_hook import gecko_lines as medal_lines
    lines += medal_lines()
    lines += ['[Gecko_Enabled]', '$AP PAL live coloured capsule refresh', '$AP PAL authoritative progression', '$AP PAL speed and White Boost gates', '$AP PAL Egg Medal pickup capture']
    return '\n'.join(lines)+'\n'


def inspect_installed(memory):
    from .gecko import inspect_c2
    from ..world_constants import load_data
    words = payload_words(); offset = data_offset(words)
    try:
        result = inspect_c2(memory,HOOK,ORIGINAL,{'current_white_collision_refresh':words}, ((offset,12),))
    except MemoryUnavailable:
        previous = load_data('capsule_white_previous.json')
        offset = data_offset(previous)
        try:
            result = inspect_c2(memory,HOOK,ORIGINAL,{'previous_white_collision_refresh':previous}, ((offset,12),))
        except MemoryUnavailable:
            result = inspect_c2(memory,HOOK,ORIGINAL,load_data('capsule_hook_legacy.json'))
    if result['installed'] and result['variant'] in ('current_white_collision_refresh','previous_white_collision_refresh'):
        result['white_data_offset'] = offset
        owner, index, allowed = struct.unpack('>3I', memory.read_bytes(result['target']+offset,12))
        if owner and not valid_range(owner,1) or index > 3 or allowed > 1:
            raise MemoryUnavailable('unknown_revision: invalid White capsule control data')
    memory.capsule_hook_observation=result
    return result


def installed(memory):
    return inspect_installed(memory)['installed']


def data_offset(words=None):
    # Embedded data follows the branch over the three zero words. The optional
    # alignment nop precedes the Gecko-patched return word.
    words = payload_words() if words is None else words
    end = len(words)-1
    if words[end-1] == 0x60000000: end -= 1
    return (end-3)*4


def installed_data(memory):
    result = inspect_installed(memory)
    if not result['installed'] or 'white_data_offset' not in result: return None
    address = result['target'] + result['white_data_offset']
    owner, index, allowed = struct.unpack('>3I', memory.read_bytes(address,12))
    if owner and not valid_range(owner,1) or index > 3 or allowed > 1:
        raise MemoryUnavailable('unknown_revision: invalid White capsule control data')
    return address


def configure(memory, snapshot, owned, slot):
    address = installed_data(memory)
    if address is None: return {'available':False, 'reason':'Update Gecko code for native White capsule projection'}
    chain = memory.resolve_flags_ptr(allow_working=True)
    desired = (chain[1], chain[2], int(not slot['options']['boost_lock'] or bool(owned['counts']['White Boost Wisp'])))
    before = struct.unpack('>3I', memory.read_bytes(address,12))
    if before != desired:
        if before[0]: memory.write_u32(address,0,expected=before[0],operation='capsule_controls')
        for i,value in enumerate(desired[1:],1):
            current = memory.read_u32(address+i*4)
            if current != value: memory.write_u32(address+i*4,value,expected=current,operation='capsule_controls')
        memory.write_u32(address,desired[0],expected=0,operation='capsule_controls')
    return {'available':True, 'white_allowed':bool(desired[2]),
            'collision_reenable_installed': memory.capsule_hook_observation['variant'] == 'current_white_collision_refresh'}
