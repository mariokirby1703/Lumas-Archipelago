"""PAL flag-setter interception; ownership data is outside the Wii save.

Gecko installs code. DME writes only its declared data words after attribution.
Native discovery/clear events accumulate monotonically; the host never clears
guest event words while their owner is enabled.
"""
import struct
import hashlib
import json
from .capsule_refresh import PPC
from .memory import MemoryUnavailable, valid_range

HOOK = 0x8015ECC0
ORIGINAL = 0x2C050000  # cmpwi r5,0


def payload():
    a=PPC()
    a.d(37,1,1,-0x50)
    a.emit(0x7C0802A6); a.d(36,0,1,8)
    a.emit(0x7C000026); a.d(36,0,1,12)
    for r in range(6,13):a.d(36,r,1,16+(r-6)*4)
    a.emit(0x48000005)  # bl .+4, position-independent data base
    base=len(a.words)*4
    a.emit(0x7D8802A6)  # mflr r12
    fix=len(a.words); a.d(14,12,12,0)
    a.d(32,6,3,0); a.d(32,7,12,0)
    a.emit(0x7C063800); a.branch('end',0x40820000)  # cmpw r6,r7
    a.d(11,0,7,0); a.branch('end',0x41820000)
    a.d(10,0,4,7); a.branch('colour',0x40810000)  # ble unsigned
    a.d(10,0,4,20); a.branch('clears',0x41800000)
    a.d(10,0,4,26); a.branch('clears',0x41810000)
    a.d(32,7,12,4); a.branch('permission')
    a.label('colour')
    a.d(11,0,5,0); a.branch('colour_mask',0x41820000)
    a.d(10,0,4,6); a.branch('colour_mask',0x41810000)
    a.d(14,7,0,1); a.emit(0x7CE72030)  # slw r7,r7,r4
    a.d(32,6,12,12); a.emit(0x7CC63B78); a.d(36,6,12,12)  # or discoveries
    a.label('colour_mask'); a.d(32,7,12,8)
    a.label('permission')
    a.d(14,6,0,1); a.emit(0x7CC62030)  # slw r6,r6,r4
    a.emit(0x7CE73038)  # and r7,r7,r6
    a.d(14,5,0,0); a.d(11,0,7,0); a.branch('end',0x41820000)
    a.d(14,5,0,1); a.branch('end')
    a.label('clears')
    a.d(11,0,5,0); a.branch('end',0x41820000)
    a.d(10,0,4,252); a.branch('end',0x41800000)
    a.d(10,0,4,272); a.branch('end',0x41810000)
    a.d(14,8,4,-252); a.d(14,7,0,1); a.emit(0x7CE74030)  # slw r7,r7,r8
    a.d(32,6,12,16); a.emit(0x7CC63B78); a.d(36,6,12,16)
    a.label('end')
    for r in range(6,13):a.d(32,r,1,16+(r-6)*4)
    a.d(32,0,1,12); a.emit(0x7C0FF120)
    a.d(32,0,1,8); a.emit(0x7C0803A6)
    a.d(14,1,1,0x50); a.emit(ORIGINAL)
    a.branch('return')
    data=len(a.words)*4
    a.words[fix] |= (data-base)&0xffff
    for _ in range(6):a.emit(0)  # owner, world mask, colours/super, two event masks, seed tag
    a.label('return')
    if len(a.words)%2==0:a.emit(0x60000000)
    a.emit(0)
    return a.finish(), data


def installed_data(memory):
    instruction=memory.read_u32(HOOK)
    if instruction==ORIGINAL:return None
    if instruction&0xFC000003!=0x48000000:
        raise MemoryUnavailable(f'unknown_revision: progression hook 0x{HOOK:08X} observed 0x{instruction:08X}')
    delta=instruction&0x03fffffc
    if delta&0x02000000:delta-=0x04000000
    target=HOOK+delta
    words,offset=payload()
    if not valid_range(target,len(words)*4):raise MemoryUnavailable('unknown_revision: progression hook range')
    actual=bytearray(memory.read_bytes(target,len(words)*4))
    owner,world,colours,discoveries,clears,seed_tag=struct.unpack('>6I',actual[offset:offset+24])
    if (owner and not valid_range(owner,0x50) or world & ~0x07f00000 or colours & ~0xff
            or discoveries & ~0x7f or clears & ~0x1fffff):
        raise MemoryUnavailable('unknown_revision: progression hook data is invalid')
    actual[offset:offset+24]=bytes(24)
    back=int.from_bytes(actual[-4:],'big');delta=back&0x03fffffc
    if delta&0x02000000:delta-=0x04000000
    if (actual[:-4]!=struct.pack('>'+'I'*(len(words)-1),*words[:-1])
            or back&0xFC000003!=0x48000000 or target+len(actual)-4+delta!=HOOK+4):
        raise MemoryUnavailable('unknown_revision: progression hook payload/return differs')
    return target+offset


def identity_tag(identity):
    value = int.from_bytes(hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).digest()[:4],'big')
    return value or 1


def configure(memory, snapshot, inventory, slot, journal=None):
    from ..Items import WORLD_ITEMS
    address=installed_data(memory)
    if address is None:
        return {'available':False,'reason':'Enable AP PAL authoritative progression for native event capture and immediate vanilla-grant suppression.'}
    chain=memory.resolve_flags_ptr(allow_working=True)
    flags=chain[-1]
    world=sum(1 << (20+i) for i,item in enumerate(WORLD_ITEMS)
              if i == slot['starting_world'] or inventory['counts'][item])
    from ..Items import WISP_ITEMS
    if slot['starting_world'] != 6 and not (inventory['counts'][WORLD_ITEMS[6]] and
                                          all(inventory['counts'][w] for w in WISP_ITEMS)):
        world &= ~(1 << 26)
    if snapshot.save_identity is None:
        world=1<<20  # only the original mandatory introduction until first save
    colours=('Yellow Drill','Cyan Laser','Blue Cube','Green Hover','Purple Frenzy','Orange Rocket','Pink Spikes')
    mask=sum(1<<i for i,name in enumerate(colours) if inventory['counts'][name+' Wisp'])
    mask |= 0x80 if inventory['super_sonic_allowed'] else 0
    # Disable interception before resetting seed-owned event data. The seed tag
    # also prevents a snapshot from crediting another seed using the same buffer.
    tag = identity_tag(journal.identity) if journal is not None else 1
    old = memory.read_u32(address)
    changed_seed = memory.read_u32(address+20) != tag
    if old and (old != flags or changed_seed):
        memory.write_u32(address,0,expected=old,operation='progression_data')
    if changed_seed:
        for field in (12,16):
            before = memory.read_u32(address+field)
            if before:
                memory.write_u32(address+field,0,expected=before,operation='progression_reset')
        before = memory.read_u32(address+20)
        memory.write_u32(address+20,tag,expected=before,operation='progression_data')
    if journal is not None and (changed_seed or 'native_event_baseline' not in journal.data):
        journal.data['native_event_baseline'] = {'discoveries':0,'game_land_clears':0}
        journal.save()
    for field,value in ((4,world),(8,mask)):
        before=memory.read_u32(address+field)
        if before!=value:memory.write_u32(address+field,value,expected=before,operation='progression_data')
    before=memory.read_u32(address)
    if before!=flags:memory.write_u32(address,flags,expected=before,operation='progression_data')
    return {'available':True,'reason':'verified native setter; AP World/Wisp/Super ownership enforced'}


def events(memory):
    address=installed_data(memory)
    if address is None:return None
    return {'owner':memory.read_u32(address),'discoveries':memory.read_u32(address+12),
            'game_land_clears':memory.read_u32(address+16),'seed_tag':memory.read_u32(address+20)}


def gecko_lines():
    words,_=payload()
    lines=['$AP PAL authoritative progression','20000000 534E4350','28000004 00003850',
           '28000006 00000000',f'20{HOOK-0x80000000:06X} {ORIGINAL:08X}',
           f'C2{HOOK-0x80000000:06X} {len(words)//2:08X}']
    lines += [f'{words[i]:08X} {words[i+1]:08X}' for i in range(0,len(words),2)]
    return lines+['E0000000 80008000']
