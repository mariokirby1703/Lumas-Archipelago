"""PAL data accessors recovered from the executable, with no guest mutations.

These reads are code-derived, not a claim of live gameplay validation. In
particular, an allocated stage object is not proof that gameplay is active.
"""
from .memory import MemoryUnavailable


APPLICATION_GLOBAL = 0x808F336C  # 800116FC; r13 = 808F9520
STAGE_TABLE_GLOBAL = 0x808F34F8  # 8007EB2C
STAGE_VTABLE = 0x80759438


def read_stage_objects(memory):
    """Read the active context through the document's global module.

    800114D0/80014354 create the document and module. 800150C0 dispatches
    to module+34 (the active context); this is independent of selected saves.
    """
    application = memory.read_ptr_checked(APPLICATION_GLOBAL, 0x10)
    if memory.read_u32(application) != 0x80758DB8:
        raise MemoryUnavailable('application_vtable_mismatch')
    document = memory.read_ptr_checked(application + 4, 0x2c)
    if memory.read_u32(document) != application:
        raise MemoryUnavailable('document_owner_mismatch')
    module = memory.read_ptr_checked(document + 0x1c, 0x3c)
    if memory.read_u32(module) != 0x80758F38:
        raise MemoryUnavailable('global_module_vtable_mismatch')
    context = memory.read_u32(module + 0x34)
    if not context:
        return []
    context = memory.read_ptr_checked(module + 0x34, 4)
    vtable = memory.read_u32(context)
    row = {'context': context, 'vtable': vtable, 'application': application}
    if vtable == 0x80769D90:
        mode = memory.read_u32(context + 0x74)
        row.update(map_mode=mode, scene={2: 'global_map', 3: 'world_map', 5: 'game_land_select'}.get(mode, 'unclassified'))
        if mode == 3:
            maps = [actor for actor in read_actors(memory, context) if memory.read_u32(actor) == 0x807773F8]
            if len(maps) == 1:
                actor = maps[0]
                zone, status = memory.read_u32(actor + 0xa8), memory.read_u32(actor + 0x1f8)
                if zone <= 6 and 1 <= status <= 4:
                    row['world_map_access'] = {'actor': actor, 'zone': zone, 'first_act_status': status,
                                               'status_address': actor + 0x1f8}
    if vtable == STAGE_VTABLE:
        stage = context
        row['stage'] = stage
        name = memory.read_ptr_checked(stage + 0x4c, 16)
        mission = memory.read_bytes(name, 16).split(b'\0', 1)[0]
        if len(mission) != 6 or not mission.startswith(b'stg') or not mission[3:].isalnum():
            raise MemoryUnavailable('invalid_stage_mission_name')
        row['mission'] = mission.decode('ascii')
        try:
            row.update(read_mission_metadata(memory, name, row['mission']))
        except MemoryUnavailable as error:
            row['metadata_error'] = str(error)
        state = memory.read_bytes(stage + 0x30, 24)
        handler = int.from_bytes(state[20:24], 'big')
        current = int.from_bytes(state[8:12], 'big')
        row.update(state_handler=handler, current_handler=current,
                   death_count=memory.read_u32(stage + 0x468),
                   wisp_permissions=memory.read_u8(stage + 0x61))
        world = memory.read_ptr_checked(module + 0x38, 0x50)
        if memory.read_u32(world) != 0x8076AC7C:
            raise MemoryUnavailable('world_state_vtable_mismatch')
        row['world_lives_address'] = world + 0x4c
        # Native member-function state machine, not a life-count heuristic.
        row['scene'] = ('gameplay' if handler == current == 0x8001CDB4 else
                        'results' if handler == 0x8001EDE4 else
                        'dying' if handler == 0x8001DC40 else
                        'paused' if handler == current == 0x8001DF78 else 'unclassified')
        if row['scene'] == 'results':
            try:
                row['result'] = read_result(memory, stage, row['mission'])
            except MemoryUnavailable as error:
                row['result_error'] = str(error)
        actor_state = memory.read_u32(stage + 0x114)
        row['actor_state'] = actor_state
        if actor_state:
            actor_state = memory.read_ptr_checked(stage + 0x114, 0x94)
            if memory.read_u32(actor_state) != 0x8075A228:
                raise MemoryUnavailable('actor_state_vtable_mismatch')
            row.update(lives=memory.read_s32(actor_state + 0x3c),
                       lives_address=actor_state + 0x3c,
                       ring_mirror_address=actor_state + 0x40,
                       player_actor_id=memory.read_u32(actor_state + 0x38),
                       current_red_ring_mask=memory.read_u8(actor_state + 0x91) & 31)
            try:
                actors = read_actors(memory, stage)
                row['player'] = read_player(memory, stage, row['player_actor_id'], actors)
            except MemoryUnavailable as error:
                row['player_error'] = str(error)
            else:
                try:
                    row['capsules'] = read_capsules(memory, stage, row['mission'], actors)
                except MemoryUnavailable as error:
                    row['capsule_error'] = str(error)
    if (memory.read_u32(APPLICATION_GLOBAL) != application or
            memory.read_u32(application + 4) != document or
            memory.read_u32(document + 0x1c) != module or
            memory.read_u32(module + 0x34) != context or
            memory.read_u32(context) != vtable or
            vtable == 0x80769D90 and memory.read_u32(context + 0x74) != mode or
            vtable == STAGE_VTABLE and memory.read_u32(module + 0x38) != world or
            row.get('world_map_access') and (memory.read_u32(row['world_map_access']['actor']) != 0x807773F8
                or memory.read_u32(row['world_map_access']['actor'] + 0xa8) != row['world_map_access']['zone']) or
            vtable == STAGE_VTABLE and (memory.read_bytes(context + 0x30, 24) != state or
                                       memory.read_u32(context + 0x4c) != name or
                                       memory.read_u32(context + 0x114) != actor_state or
                                       actor_state and memory.read_u32(actor_state + 0x38) != row['player_actor_id'])):
        raise MemoryUnavailable('stage_context_changed')
    return [row]


def read_mission_metadata(memory, name_address, mission):
    from ..world_constants import STAGES
    table = memory.read_ptr_checked(STAGE_TABLE_GLOBAL, 0x6e4)
    if memory.read_u32(table) != 0x8075DB5C:
        raise MemoryUnavailable('stage_table_vtable_mismatch')
    slot = next((stage for stage in STAGES if name_address == table + stage['zone_index'] * 0x78 +
                 0x50 + (stage['slot'] - 1) * 16), None)
    vector = memory.read_ptr_checked(table + 0x30, 0x118)
    count, capacity = memory.read_u32(table + 0x34), memory.read_u32(table + 0x38)
    if not 0 < count <= capacity <= 128:
        raise MemoryUnavailable('mission_metadata_count_invalid')
    metadata = memory.read_bytes(vector, count * 0x118)
    matches = [index for index in range(count)
               if metadata[index * 0x118:index * 0x118 + 16].split(b'\0', 1)[0] == mission.encode('ascii')]
    if len(matches) != 1:
        raise MemoryUnavailable('mission_metadata_not_unique')
    record = metadata[matches[0] * 0x118:(matches[0] + 1) * 0x118]
    data, bgm = record[0x10:0x30], record[0xac:0xcc]
    if (memory.read_u32(STAGE_TABLE_GLOBAL) != table or memory.read_u32(table + 0x30) != vector or
            memory.read_u32(table + 0x34) != count):
        raise MemoryUnavailable('mission_metadata_context_changed')
    try:
        real_stage = data[:16].split(b'\0', 1)[0].decode('ascii')
        path = data[16:].split(b'\0', 1)[0].decode('ascii')
        cue = bgm.split(b'\0', 1)[0].decode('ascii')
    except UnicodeDecodeError as error:
        raise MemoryUnavailable('invalid_native_stage_data_id') from error
    return {'clicked_slot': slot['stage_slot_id'] if slot else None,
            'real_stage_id': real_stage, 'path_data_id': path, 'bgm_cue': cue}


def read_actors(memory, stage):
    """Traverse once for players and object instances, with native ownership."""
    manager = memory.read_ptr_checked(stage + 0x18, 0x20)
    count = memory.read_u32(manager + 0x14)
    if count > 4096:
        raise MemoryUnavailable('actor_count_out_of_range')
    sentinel = manager + 0x18
    node = memory.read_ptr_checked(sentinel, 8)
    seen, actors = set(), []
    previous = sentinel
    while node != sentinel:
        if node in seen or len(seen) >= count:
            raise MemoryUnavailable('actor_cycle_or_count_mismatch')
        seen.add(node)
        if memory.read_u32(node + 4) != previous:
            raise MemoryUnavailable('actor_backlink_mismatch')
        actor = memory.read_ptr_checked(node + 8, 0x38)
        if memory.read_u32(actor + 0x34) != manager:
            raise MemoryUnavailable('actor_owner_mismatch')
        actors.append(actor)
        previous, node = node, memory.read_ptr_checked(node, 8)
    if len(seen) != count or memory.read_u32(sentinel + 4) != previous or memory.read_u32(manager + 0x14) != count:
        raise MemoryUnavailable('actor_list_changed')
    return actors


def read_capsules(memory, stage, mission, actors):
    """ReleaseBoxSmall's retained opened state and native ORC instance handle.

    800D4FA8 sets actor+110 after the item-spawn call; 800D5D38 keeps the
    actor while its opening animation runs. 80072C34 binds actor+64 to the
    object wrapper; 80108B0C/80108B34/80108BE0 expose ID, instance and params.
    """
    import math
    import struct
    from ..capsules import CAPSULES_BY_NATIVE_ID
    result = []
    for actor in actors:
        if memory.read_u32(actor) != 0x80761534:
            continue
        wrapper = memory.read_ptr_checked(actor + 0x64, 0x18)
        if memory.read_u32(wrapper + 4) != actor:
            raise MemoryUnavailable('capsule_wrapper_owner_mismatch')
        record = memory.read_ptr_checked(wrapper + 8, 0x28)
        descriptor = memory.read_ptr_checked(wrapper + 0xc, 0x20)
        if (memory.read_u32(descriptor) != 0x80770FA0 or memory.read_u32(descriptor + 0x10) != record
                or memory.read_u32(descriptor + 0x1c) != wrapper):
            raise MemoryUnavailable('capsule_instance_descriptor_mismatch')
        object_id = memory.read_u32(record) & 0xfffff
        instance = memory.read_u32(descriptor + 0x14)
        count = memory.read_u32(record + 0x1c)
        if not 0 <= instance < count <= 4096:
            raise MemoryUnavailable('capsule_instance_index_invalid')
        vector = memory.read_ptr_checked(record + 0x18, count * 24)
        xyz = struct.unpack('>3f', memory.read_bytes(vector + instance * 24, 12))
        params = memory.read_bytes(record + 0x24, 3)
        capsule = CAPSULES_BY_NATIVE_ID.get((mission, object_id, instance))
        if not capsule or params[0] != capsule.raw_wisp or any(
                not math.isfinite(value) or abs(value - expected) > max(0.002, abs(expected) * 1e-6)
                for value, expected in zip(xyz, capsule.position)):
            continue  # unknown/alternate/corrupt placements cannot credit a check
        native_colour = memory.read_s32(actor + 0x114)
        opened = memory.read_u8(actor + 0x110)
        if native_colour != capsule.raw_wisp - 1 or opened not in (0, 1):
            raise MemoryUnavailable('capsule_native_subtype_or_state_mismatch')
        if (memory.read_u32(actor + 0x64) != wrapper or memory.read_u32(wrapper + 4) != actor
                or memory.read_u32(wrapper + 8) != record):
            raise MemoryUnavailable('capsule_context_changed')
        result.append({'key': capsule.key, 'actor': actor, 'actor_id': memory.read_u32(actor + 0xc),
                       'wrapper': wrapper, 'record': record, 'opened': bool(opened),
                       'native_colour': native_colour, 'instance': instance, 'object_id': object_id})
        model = memory.read_u32(actor + 0xb0)
        if model:
            model = memory.read_ptr_checked(actor + 0xb0, 0x90)
            if memory.read_u32(model) == 0x8077d12c and memory.read_u32(model + 8) == actor:
                result[-1].update(model=model, model_mode=memory.read_u32(model + 0x88),
                                  model_state=memory.read_s32(model + 0x80))
    return result


def read_player(memory, stage, actor_id, actors=None):
    """Resolve the player ID through the native actor list, not RAM patterns."""
    manager = memory.read_ptr_checked(stage + 0x18, 0x20)
    count = memory.read_u32(manager + 0x14)
    actors = read_actors(memory, stage) if actors is None else actors
    players = [actor for actor in actors if memory.read_u32(actor + 0xc) == actor_id]
    if len(players) != 1 or memory.read_u32(players[0]) != 0x8075AEF8:
        raise MemoryUnavailable('player_type_or_owner_mismatch')
    player = players[0]
    stats = memory.read_ptr_checked(player + 0x8c, 0x9c)
    if memory.read_u32(stats) != 0x8075E088:
        raise MemoryUnavailable('stats_vtable_mismatch')
    mode = memory.read_u32(stats + 0x24)
    if mode == 0:
        rings = memory.read_ptr_checked(stats + 0x2c, 0xc)
        boost = memory.read_ptr_checked(stats + 0x30, 0x1c)
    elif mode == 2:
        shared = memory.read_ptr_checked(stats + 0x98, 0x14)
        rings = memory.read_ptr_checked(shared + 4, 0xc)
        boost = memory.read_ptr_checked(shared + 0xc, 0x1c)
    else:
        raise MemoryUnavailable('unsupported_player_mode')
    if memory.read_u32(rings) != 0x8075F2A8:
        raise MemoryUnavailable('ring_object_vtable_mismatch')
    result = {'actor': player, 'stats': stats, 'mode': mode,
              'rings': memory.read_s32(rings + 8), 'rings_address': rings + 8,
              'boost': memory.read_f32(boost + 8), 'held_wisp': memory.read_s32(boost + 0x18)}
    if (memory.read_u32(stage + 0x18) != manager or
            memory.read_u32(manager + 0x14) != count or memory.read_u32(player + 0x8c) != stats):
        raise MemoryUnavailable('player_context_changed')
    return result


def read_saved_progress(memory, rows):
    """Read physical rings and raw rank records from the selected inline save.

    Ring IDs: 8015F16C/8015F18C, persisted by 8016CD1C. Rank record:
    8015F94C, indexed by the native table accessor 8007F18C, written by
    8016CCAC..8016CCC0. The raw rank byte is retained alongside score/time.
    """
    chain = memory.resolve_flags_ptr()
    selected, flags = chain[-2:]
    bank = memory.read_bytes(flags + 0x10, 64)
    table = memory.read_ptr_checked(STAGE_TABLE_GLOBAL, 0x6d8)
    if memory.read_u32(table) != 0x8075DB5C:
        raise MemoryUnavailable('stage_table_vtable_mismatch')
    rings, records, indices = {}, {}, set()
    table_rows = memory.read_bytes(table, 0x6d8)
    record_bytes = memory.read_bytes(selected + 0xac, 66 * 12)
    def profile():
        return (memory.read_bytes(selected, 12) + memory.read_bytes(selected + 0x10, 8)
                + memory.read_bytes(selected + 0x1a, 1)).hex()
    profile_hex = profile()
    for row in rows:
        zone, act = int(row['zone']), int(row['slot']) - 1
        offset = zone * 0x78
        start = int.from_bytes(table_rows[offset + 0x48:offset + 0x4c], 'big')
        count = int.from_bytes(table_rows[offset + 0x4c:offset + 0x50], 'big')
        index = start + act
        if not 0 <= act < count or not 0 <= index < 66 or index in indices:
            raise MemoryUnavailable('invalid_native_stage_index')
        indices.add(index)
        record = record_bytes[index * 12:(index + 1) * 12]
        records[row['mission']] = {'raw_rank': record[0],
                                  'score': int.from_bytes(record[4:8], 'big'),
                                  'time_raw': int.from_bytes(record[8:12], 'big'),
                                  'record_index': index}
        if zone < 6 and act < 6:
            collected = []
            for ring in range(5):
                bit = 320 + zone * 30 + act * 5 + ring
                word = int.from_bytes(bank[bit // 32 * 4:bit // 32 * 4 + 4], 'big')
                if word & (1 << (bit % 32)):
                    collected.append(ring + 1)
            rings[row['mission']] = collected
    if (memory.resolve_flags_ptr() != chain or memory.read_u32(STAGE_TABLE_GLOBAL) != table or
            memory.read_bytes(table, 0x6d8) != table_rows or
            memory.read_bytes(selected + 0xac, 66 * 12) != record_bytes or
            memory.read_bytes(flags + 0x10, 64) != bank or profile() != profile_hex):
        raise MemoryUnavailable('saved_progress_context_changed')
    return {'physical_red_rings': rings, 'rank_records': records,
            'chain': chain,
            'profile_hex': profile_hex,
            'flag_words_hex': bank.hex(),
            'grade': 'code-derived; not live-validated; no save identity implied'}


def read_result(memory, stage, mission):
    """8001EE74 owns UI at stage+9C; 8019D148 publishes native grade+124.

    UI state 7 is the completed score/rank presentation, not its initial grade.
    All reads are relative to the native owner and checked again before return.
    """
    import math
    ui = memory.read_ptr_checked(stage + 0x9c, 0x130)
    if memory.read_u32(ui) != 0x8076CAE4:
        raise MemoryUnavailable('result_ui_vtable_mismatch')
    fields = memory.read_bytes(ui + 0xdc, 0x50)
    state = int.from_bytes(fields[:4], 'big')
    score = memory.read_u32(ui + 0x120)
    grade = memory.read_u32(ui + 0x124)
    time = memory.read_f32(ui + 0xf8)
    final = (state == 7 and grade <= 4 and memory.read_u32(ui + 0x114) == score
             and math.isfinite(time) and time > 0)
    if memory.read_u32(stage + 0x9c) != ui or memory.read_bytes(ui + 0xdc, 0x50) != fields:
        raise MemoryUnavailable('result_context_changed')
    return {'mission': mission, 'grade': grade, 'final': final, 'ui': ui,
            'score': score, 'time': time, 'provenance': 'stage9C_native_UI_state7_grade124'}
