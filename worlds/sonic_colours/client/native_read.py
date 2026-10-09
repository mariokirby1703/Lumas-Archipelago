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
        mode = memory.read_u32(context + 0x70)
        row.update(map_mode=mode, scene={2: 'global_map', 3: 'world_map', 5: 'game_land_select'}.get(mode, 'unclassified'))
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
        # Native member-function state machine, not a life-count heuristic.
        row['scene'] = ('gameplay' if handler == current == 0x8001CDB4 else
                        'results' if handler == 0x8001EDE4 else
                        'dying' if handler == 0x8001DC40 else 'unclassified')
        actor_state = memory.read_u32(stage + 0x114)
        row['actor_state'] = actor_state
        if actor_state:
            actor_state = memory.read_ptr_checked(stage + 0x114, 0x94)
            row.update(lives=memory.read_s32(actor_state + 0x3c),
                       lives_address=actor_state + 0x3c,
                       player_actor_id=memory.read_u32(actor_state + 0x38),
                       current_red_ring_mask=memory.read_u8(actor_state + 0x91) & 31)
            try:
                row['player'] = read_player(memory, stage, row['player_actor_id'])
            except MemoryUnavailable as error:
                row['player_error'] = str(error)
    if (memory.read_u32(APPLICATION_GLOBAL) != application or
            memory.read_u32(application + 4) != document or
            memory.read_u32(document + 0x1c) != module or
            memory.read_u32(module + 0x34) != context or
            memory.read_u32(context) != vtable or
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
    matches = []
    for index in range(count):
        address = vector + index * 0x118
        if memory.read_bytes(address, 16).split(b'\0', 1)[0] == mission.encode('ascii'):
            matches.append(address)
    if len(matches) != 1:
        raise MemoryUnavailable('mission_metadata_not_unique')
    data = memory.read_bytes(matches[0] + 0x10, 32)
    bgm = memory.read_bytes(matches[0] + 0xac, 32)
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


def read_player(memory, stage, actor_id):
    """Resolve the player ID through the native actor list, not RAM patterns."""
    manager = memory.read_ptr_checked(stage + 0x18, 0x20)
    count = memory.read_u32(manager + 0x14)
    if count > 4096:
        raise MemoryUnavailable('actor_count_out_of_range')
    sentinel = manager + 0x18
    node = memory.read_ptr_checked(sentinel, 8)
    seen, players = set(), []
    previous = sentinel
    while node != sentinel:
        if node in seen or len(seen) >= count:
            raise MemoryUnavailable('actor_cycle_or_count_mismatch')
        seen.add(node)
        if memory.read_u32(node + 4) != previous:
            raise MemoryUnavailable('actor_backlink_mismatch')
        actor = memory.read_ptr_checked(node + 8, 0x38)
        if memory.read_u32(actor + 0xc) == actor_id:
            if memory.read_u32(actor) != 0x8075AEF8 or memory.read_u32(actor + 0x34) != manager:
                raise MemoryUnavailable('player_type_or_owner_mismatch')
            players.append(actor)
        previous, node = node, memory.read_ptr_checked(node, 8)
    if len(seen) != count or memory.read_u32(sentinel + 4) != previous or len(players) != 1:
        raise MemoryUnavailable('player_not_unique_or_list_changed')
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
            memory.read_bytes(flags + 0x10, 64) != bank):
        raise MemoryUnavailable('saved_progress_context_changed')
    return {'physical_red_rings': rings, 'rank_records': records,
            'flag_words_hex': bank.hex(),
            'grade': 'code-derived; not live-validated; no save identity implied'}
