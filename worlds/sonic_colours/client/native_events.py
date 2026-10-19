"""PAL game-thread death, jump-policy and cue-preparation boundaries.

Code is boot-patched into audited, unreferenced function alignment padding.
Only the initialized native DOL mailbox is writable at runtime.
"""
import struct
from functools import lru_cache
from .capsule_refresh import PPC
from .memory import MemoryUnavailable

MAGIC=0x41504532
SIZE=128
HOOKS={'frame':(0x8001CE60,0x800400A4),'death':(0x8001D2B8,0x2C1A0000),
       'jump_state':(0x800395B4,0x7C0802A6),
       'music_loop':(0x80125004,0x3803FFFF),'music':(0x80125378,0x981E0029),'jump':(0x80056CA0,0x5484103A)}
# Mailbox offsets. A coherent host publication disables ENABLE before changing
# ownership. Sequence/ack fields and remaining time are game-thread owned.
ENABLE,STAGE,PLAYER,SERIAL,REQUEST,ACK,DEATH_SEQ,DEATH_STAGE,DEATH_COUNT=4,8,12,16,20,24,28,32,36
REMAINING,TRAP_REQUEST,TRAP_ACK,INPUT,MUSIC_SEQ,CHANNEL,CUE,NAME=40,44,48,52,60,64,68,72
JUMP_TABLE=112
LOOP_CUE=104  # host-authenticated finite donor destination, zero disables
FRAME_FENCE=56  # completed native frame callbacks, including disabled frames
JUMP_STATES=(5,6,7,8,9,11,12,18,19,29,30,36,37,39,40,46,47,58,80,106,107,115)


def program(kind,control):
    a=PPC()
    def const(r,v):a.d(15,r,0,v>>16);a.d(24,r,r,v&65535)
    def cmp(r,v):a.d(11,0,r,v)
    def br(label,cond=0x48000000):a.branch(label,cond)
    def equal(lhs,rhs):a.emit(0x7C000000|lhs<<16|rhs<<11)
    def call(address):const(12,address);a.emit(0x7D8903A6);a.emit(0x4E800421)
    # Full GPR/CR/LR/CTR preservation; calls may also clobber volatile FPRs.
    a.d(37,1,1,-0x120);a.d(47,0,1,16)
    for word,off in ((0x7C000026,144),(0x7C0802A6,148),(0x7C0902A6,152)):
        a.emit(word);a.d(36,0,1,off)
    if kind in ('frame','music_loop'):
        for f in range(14):a.d(54,f,1,160+f*8)
    const(31,control)
    if kind=='death':
        # After native life loss for message 5003, BEFORE the Game Land
        # Assist branch skips the normal stage-death score counter increment.
        a.d(32,3,31,DEATH_SEQ);a.d(14,3,3,1);a.d(36,3,31,DEATH_SEQ)
        a.d(36,29,31,DEATH_STAGE);a.d(32,4,29,0x468);a.d(36,4,31,DEATH_COUNT)
        a.d(36,27,31,108)  # native deceased actor ID (normal Sonic or Assist)
        a.d(14,3,3,1);a.emit(0x7C0004AC);a.d(36,3,31,DEATH_SEQ)
    elif kind=='music_loop':
        # Native channel update: r3 is the resolved CRI status, r30 the
        # still-owned channel. Status 4 is stopped (not playing/paused/error).
        a.d(32,4,31,LOOP_CUE);a.d(28,4,7,0xffff);cmp(7,0);br('done',0x41820000)
        # A Wisp/jingle can stop an old channel before the host sees its new
        # successful-start event. Only the current native playback owner may
        # arm/replay. Matching the cue alone also matches stale cached handles.
        a.d(32,5,31,CHANNEL);equal(5,30);br('done',0x40820000)
        a.d(32,5,31,CUE);equal(5,7);br('done',0x40820000)
        a.d(32,5,30,0);cmp(5,0);br('done',0x40810000) # native owners remain
        a.d(34,5,30,0x29);cmp(5,1);br('done',0x40820000) # successful start
        a.d(34,5,30,0x28);cmp(5,0);br('done',0x40820000) # no stop/fade/pause
        a.d(32,6,30,8);cmp(6,0);br('done',0x41820000)
        a.d(32,5,6,0);equal(7,5);br('done',0x40820000)
        cmp(3,2);br('loop_running',0x41820000)
        cmp(3,3);br('done',0x41820000)  # pause is not evidence of playback
        cmp(3,4);br('done',0x40820000)
        const(8,0x10000)
        a.emit(31<<26|4<<21|8<<16|8<<11|28<<1|1) # and. armed bit
        br('done',0x41820000)
        # Consume before Start: a preparing/stopped player cannot retrigger.
        a.d(36,7,31,LOOP_CUE)
        # Original opening/credits cue IDs are never eligible host policies.
        # Restart the existing descriptor/player through the original wrapper.
        # 80600470..80600494 deliberately reuse an identical cached cue,
        # including a finished one. Native Stop releases that instance first.
        a.mr(29,6);a.mr(3,30);a.d(14,4,0,0);call(0x801251EC)
        a.mr(3,30);a.mr(4,29);call(0x80125310)
        # 80123830 prepares the cue; the handle's separate Play wrapper at
        # 80123714 calls 80125390. Preparation alone never starts the stream.
        a.mr(3,30);a.d(14,4,0,0);a.d(48,1,2,-0x615c);call(0x80125390)
        br('done')
        a.label('loop_running');const(8,0x10000)
        a.emit(31<<26|7<<21|8<<16|8<<11|444<<1) # or r8,r7,r8
        a.d(36,8,31,LOOP_CUE)
    elif kind=='music':
        # 80125360 prepares the CRI cue; this is NOT proof of audible playback.
        # The separate Play request is 80125390. Native
        # status at stack+8 must be zero to reach this successful-start site.
        # r31 is the cue descriptor, preceded by the tree's 32-byte cue key.
        a.d(32,3,1,16+31*4)  # original r31, before using it as control
        a.d(32,4,3,-32);const(5,0x62676D5F);equal(4,5);br('done',0x40820000)
        # A new native start invalidates any end latch from the previous
        # playback. Never inherit its armed flag across temporary music.
        a.d(32,4,31,LOOP_CUE);a.d(28,4,4,0xffff);a.d(36,4,31,LOOP_CUE)
        a.d(32,4,31,MUSIC_SEQ);a.d(14,4,4,1);a.d(36,4,31,MUSIC_SEQ)
        a.d(32,4,1,16+30*4);a.d(36,4,31,CHANNEL)
        a.d(32,4,3,0);a.d(36,4,31,CUE)
        for i in range(8):a.d(32,4,3,-32+i*4);a.d(36,4,31,NAME+i*4)
        a.d(32,3,31,MUSIC_SEQ);a.d(14,3,3,1);a.emit(0x7C0004AC);a.d(36,3,31,MUSIC_SEQ)
    elif kind in ('jump','jump_state'):
        if kind=='jump':
            cmp(5,0);br('done',0x40820000)  # Jump action; other actions unchanged
        else:
            cmp(4,0);br('done',0x41800000);cmp(4,127);br('done',0x41810000)
            a.emit(0x5486D97E);a.emit(0x54C6103A);a.d(14,6,6,JUMP_TABLE)
            a.emit(31<<26|6<<21|31<<16|6<<11|23<<1)  # lwzx r6,r31,r6
            a.d(28,4,8,31);a.d(14,7,0,1);a.emit(31<<26|7<<21|7<<16|8<<11|24<<1)
            a.emit(31<<26|6<<21|6<<16|7<<11|28<<1|1);br('done',0x41820000)
        a.d(32,6,31,ENABLE);cmp(6,1);br('done',0x40820000)
        if kind=='jump':
            a.d(32,6,31,INPUT);equal(3,6);br('done',0x40820000)
        a.d(32,6,31,REMAINING);cmp(6,0);br('done',0x40810000)
        # Only the attributed living gameplay context can suppress input.
        const(7,0x808F336C);a.d(32,7,7,0);a.d(32,7,7,4);a.d(32,7,7,0x1c);a.d(32,7,7,0x34)
        a.d(32,6,31,STAGE);equal(6,7);br('done',0x40820000)
        a.d(32,8,31,PLAYER);cmp(8,0);br('done',0x41820000)
        a.d(32,9,8,0);const(10,0x8075AEF8);equal(9,10);br('done',0x40820000)
        a.d(32,9,8,12);a.d(32,10,31,SERIAL);equal(9,10);br('done',0x40820000)
        a.d(32,10,7,0x114);cmp(10,0);br('done',0x41820000)
        a.d(32,10,10,0x38);equal(9,10);br('done',0x40820000)
        if kind=='jump':
            a.d(32,8,8,0x88);equal(3,8);br('done',0x40820000)
        else:
            a.d(32,8,8,0x70);cmp(8,0);br('done',0x41820000)
            a.d(32,8,8,8);a.d(14,8,8,0x14);equal(3,8);br('done',0x40820000)
        a.d(32,6,7,0x44);const(7,0x8001CDB4);equal(6,7);br('done',0x40820000)
        # Early boolean false return, before native held/pressed/released test.
        if kind=='jump':a.d(14,3,0,0);a.d(36,3,1,16+3*4)
        br('blocked')
    else:
        a.d(32,3,31,ENABLE);cmp(3,1);br('done',0x40820000)
        a.d(32,3,31,STAGE);equal(3,29);br('done',0x40820000)
        a.d(32,3,29,0xa4);a.d(28,3,3,0xc00);br('done',0x40820000)
        a.d(32,30,31,PLAYER);cmp(30,0);br('done',0x41820000)
        a.d(32,3,30,0);const(4,0x8075AEF8);equal(3,4);br('done',0x40820000)
        a.d(32,3,30,12);a.d(32,4,31,SERIAL);equal(3,4);br('done',0x40820000)
        a.d(32,4,29,0x114);cmp(4,0);br('done',0x41820000)
        a.d(32,4,4,0x38);equal(3,4);br('done',0x40820000)
        # Native frame delta; countdown never advances in menus/pause/loading.
        a.d(32,4,1,16+30*4)  # original r30 is the stage event, not player
        a.d(48,1,4,4);a.d(48,0,31,REMAINING);a.emit(0xEC000828)  # fsubs f0,f0,f1
        a.d(48,2,2,-0x6580);a.emit(0xFC001040);br('positive',0x41810000)
        a.emit(0xFC001090)  # fmr f0,f2 (native zero)
        a.label('positive');a.d(52,0,31,REMAINING)
        a.d(32,3,31,TRAP_REQUEST);a.d(36,3,31,TRAP_ACK)
        # A remote kill is accepted only for a stable normal-Sonic state.
        a.d(32,3,31,REQUEST);a.d(32,4,31,ACK);equal(3,4);br('done',0x41820000)
        a.d(32,4,30,0x70);cmp(4,0);br('done',0x41820000)
        a.d(32,4,4,8);cmp(4,0);br('done',0x41820000)
        a.d(32,5,4,0);const(6,0x8075A0F8);equal(5,6);br('done',0x40820000)
        a.d(32,5,4,0x28);equal(5,30);br('done',0x40820000)
        a.d(32,5,4,0x1c);cmp(5,0);br('done',0x41800000);cmp(5,63);br('done',0x41810000)
        cmp(5,24);br('done',0x41820000);cmp(5,25);br('done',0x41820000);cmp(5,26);br('done',0x41820000)
        # Consume BEFORE invoking the ordinary forced state transition. 24 is
        # registered as CStateDead at 80034460, with entry at 800685DC.
        a.d(36,3,31,ACK);a.mr(3,4);a.d(14,4,0,24);call(0x800338E8)
    a.label('done')
    if kind=='frame':
        a.d(32,3,31,FRAME_FENCE);a.d(14,3,3,1);a.emit(0x7C0004AC);a.d(36,3,31,FRAME_FENCE)
    if kind in ('frame','music_loop'):
        for f in range(14):a.d(50,f,1,160+f*8)
    def restore():
        for word,off in ((0x7C0FF120,144),(0x7C0803A6,148),(0x7C0903A6,152)):
            a.d(32,0,1,off);a.emit(word)
        a.d(46,2,1,24);a.d(32,0,1,16);a.d(14,1,1,0x120)
    restore();a.emit(HOOKS[kind][1]);br('return')
    if kind in ('jump','jump_state'):
        a.label('blocked');restore()
        if kind=='jump_state':a.d(14,1,1,0xc0)  # unwind native dispatcher's displaced prologue
        a.emit(0x4E800020)
    a.label('return');a.emit(0)
    return a.finish()


def scatter(words,sites,return_to):
    """One instruction per 12-byte site; conditional long branches stay local."""
    from .native_dol import branch
    if len(words)>len(sites):raise ValueError('native event padding exhausted')
    result=[]
    for i,word in enumerate(words):
        address=sites[i]['address'];next_address=sites[i+1]['address'] if i+1<len(words) else return_to
        if i==len(words)-1:chunk=[branch(address,return_to),0x60000000,0x60000000]
        elif word>>26 in (16,18):
            op=word>>26;mask=0xfffc if op==16 else 0x3fffffc;sign=0x8000 if op==16 else 0x2000000
            delta=word&mask
            if delta&sign:delta-=2*sign
            target=sites[i+delta//4]['address']
            if op==16:chunk=[(word&0xffff0000)^0x01000000|8,branch(address+4,target),branch(address+8,next_address)]
            else:chunk=[branch(address,target)|(word&1),0x60000000,0x60000000]
        else:chunk=[word,branch(address+4,next_address),0x60000000]
        result.append((address,bytes(12),struct.pack('>3I',*chunk)))
    return result


@lru_cache(maxsize=1)
def patches(control):
    from ..world_constants import load_data
    from .native_dol import branch
    from .ap_hud_publisher import patches as hud_patches
    # The publisher may grow into previously unused audited padding. Keep
    # native event allocation disjoint rather than relying on old list order.
    occupied={address for address,_,_ in hud_patches(native_registry=True)}
    sites=[s for s in load_data('native_event_sites.json') if s['address'] not in occupied]
    result=[];used=0
    for kind,(hook,old) in HOOKS.items():
        words=program(kind,control)
        selected=(load_data('native_music_loop_sites.json') if kind=='music_loop' else sites[used:])
        entry=selected[0]['address']
        result.append((hook,old.to_bytes(4,'big'),branch(hook,entry).to_bytes(4,'big')))
        result.extend(scatter(words,selected,hook+4))
        if kind!='music_loop':used+=len(words)
    return result


def address(memory):
    from .native_dol import plan,ARENA
    if not getattr(memory,'native_patch',None):raise MemoryUnavailable('Native event ISO required')
    base=ARENA+len(plan()[1])-SIZE
    if memory.read_u32(base)!=MAGIC:raise MemoryUnavailable('Native event mailbox signature differs')
    expected=struct.pack('>4I',*(sum(1<<(s%32) for s in JUMP_STATES if s//32==i) for i in range(4)))
    if memory.read_bytes(base+JUMP_TABLE,16)!=expected:raise MemoryUnavailable('Native Jump policy table differs')
    return base


def status(memory):
    base=address(memory)
    for _ in range(3):
        raw=memory.read_bytes(base,SIZE)
        death,music=struct.unpack_from('>I',raw,DEATH_SEQ)[0],struct.unpack_from('>I',raw,MUSIC_SEQ)[0]
        if not (death&1 or music&1) and memory.read_u32(base+DEATH_SEQ)==death and memory.read_u32(base+MUSIC_SEQ)==music:break
    else:raise MemoryUnavailable('Native event publication in progress')
    return {'installed':True,'address':base,'death_sequence':struct.unpack_from('>I',raw,DEATH_SEQ)[0],
            'death_stage':struct.unpack_from('>I',raw,DEATH_STAGE)[0],
            'death_count':struct.unpack_from('>I',raw,DEATH_COUNT)[0],
            'remote_request':struct.unpack_from('>I',raw,REQUEST)[0],
            'remote_ack':struct.unpack_from('>I',raw,ACK)[0],
            'frame_fence':struct.unpack_from('>I',raw,FRAME_FENCE)[0],
            'trap_request':struct.unpack_from('>I',raw,TRAP_REQUEST)[0],
            'trap_ack':struct.unpack_from('>I',raw,TRAP_ACK)[0],
            'remaining':max(0.,struct.unpack_from('>f',raw,REMAINING)[0]),
            'finite_loop_cue':struct.unpack_from('>I',raw,LOOP_CUE)[0]&0xffff,
            'finite_loop_armed':bool(struct.unpack_from('>I',raw,LOOP_CUE)[0]&0x10000),
            'music_sequence':struct.unpack_from('>I',raw,MUSIC_SEQ)[0],
            'music_channel':struct.unpack_from('>I',raw,CHANNEL)[0],
            'cue_id':struct.unpack_from('>I',raw,CUE)[0],
            'cue_name':raw[NAME:NAME+32].split(b'\0')[0].decode('ascii',errors='replace')}
