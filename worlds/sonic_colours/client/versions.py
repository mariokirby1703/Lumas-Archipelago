import hashlib
from datetime import datetime, timezone
from ..world_constants import load_data

VERSION = load_data('versions.json')


def verify_revision(memory):
    disc = memory.read_bytes(0x80000000, 6)
    # DME can briefly return a zero-filled header during a coherent PAL run.
    # Bound retries; never reuse a previous executable identity for writes.
    for _ in range(2):
        if disc != b'\0' * 6:
            break
        disc = memory.read_bytes(0x80000000, 6)
    revision = memory.read_u8(0x80000007)
    memory.revision_observation = {'time_utc': datetime.now(timezone.utc).isoformat(),
                                   'disc_id': disc.decode('ascii', errors='backslashreplace'),
                                   'disc_id_hex': disc.hex(), 'revision': revision, 'verified': False}
    if disc != VERSION['disc_id'].encode('ascii'):
        raise memory.error(f'wrong_game: observed {disc!r} (hex={disc.hex()}), expected PAL SNCP8P')
    if revision != VERSION['revision']:
        raise memory.error(f'unknown_revision: observed disc revision {revision}, expected {VERSION["revision"]}')
    from .native_dol import handshake
    native=handshake(memory)
    memory.native_patch=native
    expected=getattr(memory,'required_native_seed',None)
    if expected is not None:
        if native is None:raise memory.error('Load the generated AP ISO; native patch handshake missing')
        if native['seed_digest']!=hashlib.sha256(expected.encode()).digest()[:16].hex():
            raise memory.error('Native patched ISO belongs to another seed')
    memory.revision_observation['native_patch']=native
    # Direct guest PPC experiments are NOT ordinary Gecko codes. Only
    # recognized, byte-authenticated trampoline plans may be normalized.
    from .direct_hooks import plan as direct_plan, recognize_branch
    direct_plans = [direct_plan(include_movement=False), direct_plan(include_movement=True)]
    for section in VERSION['text_sections']:
        data = memory.read_bytes(section['address'], section['size'])
        from .ap_hud_publisher import normalize as normalize_hud_publisher
        data=normalize_hud_publisher(memory,data,section['address'])
        from .hud_renderer_batch import normalize as normalize_hud_batch
        data=normalize_hud_batch(memory,data,section['address'])
        from .game_land_native_tint import normalize as normalize_initial_tint
        data=normalize_initial_tint(memory,data,section['address'])
        from .game_land_menu import normalize as normalize_game_land_menu
        data = normalize_game_land_menu(memory,data,section['address'])
        from .player_switch import normalize as normalize_player_switch
        data = normalize_player_switch(data,section['address'])
        from .speed_initial import normalize as normalize_initial_speed
        data = normalize_initial_speed(data,section['address'])
        from .stunts import normalize as normalize_stunts
        data = normalize_stunts(memory,data,section['address'])
        from .hover_ring_dash import normalize as normalize_hover_dash
        data = normalize_hover_dash(memory,data,section['address'])
        from .oneup_hook import normalize as normalize_oneup
        data = normalize_oneup(memory,data,section['address'])
        from .quick_step import normalize as normalize_quick
        data = normalize_quick(memory,data,section['address'])
        from .drill_turbo import normalize as normalize_drill
        data = normalize_drill(memory,data,section['address'])
        from .skydiving import normalize as normalize_skydiving
        data = normalize_skydiving(memory,data,section['address'])
        from .rocket_skydiving import normalize as normalize_rocket_skydiving
        data = normalize_rocket_skydiving(memory,data,section['address'])
        from .player_switch import HOOK as ASSIST_HOOK, HOOK_ORIGINAL as ASSIST_ORIGINAL, installed_data as assist_data
        if section['address']<=ASSIST_HOOK<section['address']+section['size']:
            off=ASSIST_HOOK-section['address']
            if int.from_bytes(data[off:off+4],'big')!=ASSIST_ORIGINAL and assist_data(memory) is not None:
                data=data[:off]+ASSIST_ORIGINAL.to_bytes(4,'big')+data[off+4:]
        # Only touch candidate sites not normalized as exact supported Gecko
        # hooks above. Partially installed experiments may contain a mix of
        # original and exact trampoline words; unknown branches still fail.
        for direct in direct_plans:
            for site, original, arena, code, label in direct:
                if section['address'] <= site < section['address'] + section['size']:
                    off = site - section['address']
                    word = int.from_bytes(data[off:off+4], 'big')
                    if word != original and recognize_branch(memory, site, original, (site, original, arena, code, label)):
                        data = data[:off] + original.to_bytes(4,'big') + data[off+4:]

        # Optional Dolphin-Gecko movement test group, independently verified
        # before normalizing its single patched instruction for the PAL hash.
        from .movement_gate import HOOK as MOVE_HOOK, ORIGINAL as MOVE_ORIGINAL, LEGACY_HOOK, LEGACY_ORIGINAL, installed_data as move_data, _legacy_gecko_install
        for move_hook,move_original in ((MOVE_HOOK,MOVE_ORIGINAL),(LEGACY_HOOK,LEGACY_ORIGINAL)):
            if section['address']<=move_hook<section['address']+section['size']:
                off=move_hook-section['address']
                word=int.from_bytes(data[off:off+4],'big')
                if word!=move_original:
                    verified=(_legacy_gecko_install(memory) if move_hook==LEGACY_HOOK else move_data(memory,transport='gecko'))
                    if verified is not None:data=data[:off]+move_original.to_bytes(4,'big')+data[off+4:]
        from .capsule_refresh import HOOK, ORIGINAL, installed
        if section['address'] <= HOOK < section['address'] + section['size']:
            offset = HOOK - section['address']
            instruction = int.from_bytes(data[offset:offset + 4], 'big')
            memory.revision_observation['capsule_hook_instruction'] = f'0x{instruction:08X}'
            if instruction != ORIGINAL and installed(memory):
                data = data[:offset] + ORIGINAL.to_bytes(4, 'big') + data[offset + 4:]
        from .progression_hook import HOOK as PROGRESSION_HOOK, ORIGINAL as PROGRESSION_ORIGINAL, installed_data
        if section['address'] <= PROGRESSION_HOOK < section['address'] + section['size']:
            offset = PROGRESSION_HOOK - section['address']
            word = int.from_bytes(data[offset:offset+4], 'big')
            if word != PROGRESSION_ORIGINAL and installed_data(memory) is not None:
                data = data[:offset] + PROGRESSION_ORIGINAL.to_bytes(4,'big') + data[offset+4:]
        from .gameplay_controls import HOOKS, installed as controls_installed
        for kind, (control_hook, control_original) in HOOKS.items():
            if section['address'] <= control_hook < section['address'] + section['size']:
                offset = control_hook - section['address']
                word = int.from_bytes(data[offset:offset+4], 'big')
                if word != control_original and controls_installed(memory, kind) is not None:
                    data = data[:offset] + control_original.to_bytes(4, 'big') + data[offset+4:]
        from .medal_hook import HOOK as MEDAL_HOOK, ORIGINAL as MEDAL_ORIGINAL, installed_data as medal_data
        if section['address'] <= MEDAL_HOOK < section['address'] + section['size']:
            offset = MEDAL_HOOK - section['address']
            word = int.from_bytes(data[offset:offset+4], 'big')
            if word != MEDAL_ORIGINAL and medal_data(memory) is not None:
                data = data[:offset] + MEDAL_ORIGINAL.to_bytes(4, 'big') + data[offset+4:]
        from .capsule_capture import HOOK as CAP_HOOK, ORIGINAL as CAP_ORIGINAL, installed_data as capture_data
        if getattr(memory,'native_patch',None) and section['address']<=CAP_HOOK<section['address']+section['size']:
            if capture_data(memory) is None:raise MemoryUnavailable('native capsule capture missing')
            offset=CAP_HOOK-section['address']
            data=data[:offset]+CAP_ORIGINAL.to_bytes(4,'big')+data[offset+4:]
        from .area_map_refresh import HOOK as AREA_HOOK, ORIGINAL as AREA_ORIGINAL
        if getattr(memory,'native_patch',None) and section['address']<=AREA_HOOK<section['address']+section['size']:
            offset=AREA_HOOK-section['address']
            data=data[:offset]+AREA_ORIGINAL.to_bytes(4,'big')+data[offset+4:]
        from .map_refresh import HOOK as MAP_HOOK, ORIGINAL as MAP_ORIGINAL, installed_data as map_data
        if section['address'] <= MAP_HOOK < section['address'] + section['size']:
            offset = MAP_HOOK - section['address']
            word = int.from_bytes(data[offset:offset+4], 'big')
            if word != MAP_ORIGINAL and map_data(memory) is not None:
                data = data[:offset] + MAP_ORIGINAL.to_bytes(4, 'big') + data[offset+4:]
        from .map_transition import HOOK as PATH_HOOK, ORIGINAL as PATH_ORIGINAL, installed as path_installed
        if section['address'] <= PATH_HOOK < section['address'] + section['size']:
            offset = PATH_HOOK - section['address']
            word = int.from_bytes(data[offset:offset+4], 'big')
            if word != PATH_ORIGINAL and path_installed(memory):
                data = data[:offset] + PATH_ORIGINAL.to_bytes(4, 'big') + data[offset+4:]
        from .map_transition import UPDATE_HOOK, UPDATE_ORIGINAL, update_installed
        if section['address'] <= UPDATE_HOOK < section['address'] + section['size']:
            offset = UPDATE_HOOK - section['address']
            word = int.from_bytes(data[offset:offset+4], 'big')
            if word != UPDATE_ORIGINAL and update_installed(memory):
                data = data[:offset] + UPDATE_ORIGINAL.to_bytes(4, 'big') + data[offset+4:]
        from .map_ring_display import HOOK as RING_HOOK, ORIGINAL as RING_ORIGINAL, installed as ring_installed, PREVIOUS_HOOK, PREVIOUS_ORIGINAL, previous_installed
        if section['address'] <= RING_HOOK < section['address'] + section['size']:
            offset = RING_HOOK-section['address']
            if int.from_bytes(data[offset:offset+4],'big') != RING_ORIGINAL and ring_installed(memory):
                data = data[:offset]+RING_ORIGINAL.to_bytes(4,'big')+data[offset+4:]
        if section['address'] <= PREVIOUS_HOOK < section['address'] + section['size']:
            offset = PREVIOUS_HOOK-section['address']
            if int.from_bytes(data[offset:offset+4],'big') != PREVIOUS_ORIGINAL and previous_installed(memory):
                data = data[:offset]+PREVIOUS_ORIGINAL.to_bytes(4,'big')+data[offset+4:]
        digest = hashlib.sha256(data).hexdigest()
        if digest != section['sha256']:
            raise memory.error(f'unknown_revision: text at 0x{section["address"]:08X}, '
                               f'observed SHA256 {digest}, expected {section["sha256"]}')
    memory.revision_observation.update(verified=True, dol_sha256=VERSION['dol_sha256'])
    return VERSION['dol_sha256']
