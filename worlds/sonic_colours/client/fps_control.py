import hashlib

from .memory import MemoryUnavailable

FRAME_INTERVAL=0x808F2D94
FRAME_DELTA=0x808F2D98
FRAME_OWNER=0x8090DB00
OWNER_INTERVAL=FRAME_OWNER+8


def address(memory):
    if not (getattr(memory, 'native_patch', None) or {}).get('fps_control'):
        raise MemoryUnavailable('Repatch this seed with the current APWorld to use /sonicfps')
    from .oneup_hook import installed_data
    base = installed_data(memory)
    if base is None:
        raise MemoryUnavailable('Native FPS control is unavailable')
    return base + 8


def apply(runtime, memory):
    interval = getattr(runtime, 'fps_interval', None)
    if interval is None:
        return
    if interval == 2 and not (getattr(memory, 'native_patch', None) or {}).get('correct_fps_setter'):
        raise MemoryUnavailable('Repatch this ISO: its old FPS control slows gameplay at 30 FPS')
    target = address(memory)
    before = memory.read_u32(target)
    native_switch = bool(memory.native_patch.get('native_fps_switch'))
    if (before & 0xffff if native_switch else before) != interval:
        runtime._fps_native_restore_done=False
        memory._fps_interval = interval
        try:
            memory.write_u32(target, interval, expected=before, operation='fps_control')
        finally:
            memory._fps_interval = None
    if interval==2 and native_switch and not getattr(runtime,'_fps_native_restore_done',False):
        memory._fps_interval=interval
        try:
            # The 60-FPS override changed both copies of the frame interval.
            # Restore both: restoring just one lets the other copy overwrite it.
            for field in (FRAME_INTERVAL,OWNER_INTERVAL):
                old=memory.read_u32(field)
                if old!=2:
                    memory.write_u32(field,2,expected=old,operation='fps_native_restore')
        finally:
            memory._fps_interval=None
        runtime._fps_native_restore_done=(memory.read_u32(FRAME_INTERVAL)==2
            and memory.read_u32(OWNER_INTERVAL)==2
            and abs(memory.read_f32(FRAME_DELTA)-1/30)<.00001)
    observed = memory.read_u32(FRAME_INTERVAL)
    vi = memory.read_u8(0x8090DB0B)
    packet = memory.read_u32(target)
    applied = (bool(packet & 0x10000) and packet & 0xffff == interval
               and 1 <= observed <= 255 and vi == observed
               and (interval == 2 or observed == 1)) if native_switch else observed == interval and vi == interval
    if native_switch and interval==2:
        applied=applied and getattr(runtime,'_fps_native_restore_done',False)
    return {'interval': interval, 'applied': applied,
            'native_timing': native_switch and interval == 2,
            'observed_interval': observed, 'status': 'Awaiting the next game frame'}


def authorize(memory, guard, target, size, restore=False):
    native = getattr(memory, 'native_patch', None) or {}
    journal = getattr(guard, 'journal', None)
    seed = getattr(journal, 'identity', {}).get('seed')
    if (not isinstance(seed, str) or
            hashlib.sha256(seed.encode()).digest()[:16].hex() != native.get('seed_digest')):
        raise MemoryUnavailable('WRITE_BLOCKED: FPS control requires the connected seed ISO')
    interval = getattr(memory, '_fps_interval', None)
    if restore:
        if (not native.get('native_fps_switch') or interval!=2 or size!=4
                or target not in (FRAME_INTERVAL,OWNER_INTERVAL)
                or memory.read_u32(address(memory))&0xffff!=2
                or memory.read_u32(0x808F336C)!=FRAME_OWNER
                or memory.read_u32(FRAME_OWNER)!=0x80758DB8):
            raise MemoryUnavailable('WRITE_BLOCKED: invalid native FPS restoration')
        return ('fps_native_restore',native['seed_digest'],native.get('code_sha256'),target)
    if interval == 2 and not native.get('correct_fps_setter'):
        raise MemoryUnavailable('WRITE_BLOCKED: old FPS control requires a repatched ISO')
    if size != 4 or target != address(memory) or interval not in (1, 2):
        raise MemoryUnavailable('WRITE_BLOCKED: invalid FPS control')
    # FPS is a graphics/clock setting, not save progression. This deliberately
    # works before the initial save selection and in menus or paused gameplay.
    return ('fps_control', native['seed_digest'], native.get('code_sha256'), target, interval)
