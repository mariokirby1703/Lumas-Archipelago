"""Repair settled Game Land columns after availability changes in-place.

The native emerald_N node contains both the Emerald and its three Acts.
Its initial scale is zero. Colouring an unlocked Act alone does not unfold
that parent, and its collapsed transform puts the cursor on the Emerald.
Only settled stage selection (state 13) is eligible; intro/exit animations
retain exclusive control of the layout while they run.
"""
from .memory import MemoryUnavailable
from .native_read import read_stage_objects, read_actors


def targets(memory, flags):
    rows = read_stage_objects(memory, False)
    if len(rows) != 1 or rows[0].get('scene') != 'game_land_select':
        return {}
    actors = [a for a in read_actors(memory, rows[0]['context'])
              if memory.read_u32(a) == 0x8077E59C]
    if len(actors) != 1:
        raise MemoryUnavailable('Game Land column owner not unique')
    actor = actors[0]
    if memory.read_u32(actor + 0x9c) != 13:
        return {}
    ref = memory.read_ptr_checked(actor + 0x88, 4)
    layer = memory.read_ptr_checked(ref, 0xe0)
    layout = memory.read_ptr_checked(layer + 12, 0x34)
    count = memory.read_u32(layout + 0x2c)
    if not 21 <= count <= 512:
        raise MemoryUnavailable('Game Land column dictionary invalid')
    table = memory.read_ptr_checked(layout + 0x30, count * 12)
    graph = memory.read_ptr_checked(layer + 0x8c, 16)
    groups = memory.read_ptr_checked(memory.read_ptr_checked(graph + 12, 8) + 4, 16)
    columns = {}
    for i in range(count):
        entry = table + i * 12
        name = memory.read_bytes(memory.read_ptr_checked(entry, 16), 16).split(b'\0')[0]
        if name in tuple(f'emerald_{j}'.encode() for j in range(7)):
            group, index = memory.read_u32(entry + 4), memory.read_u32(entry + 8)
            if group != 0 or not 0 <= index < 64 or name in columns:
                raise MemoryUnavailable('Game Land column dictionary mismatch')
            columns[name] = index
    if len(columns) != 7 or memory.read_u32(groups) != 64:
        raise MemoryUnavailable('Game Land column topology mismatch')
    array = memory.read_ptr_checked(groups + 4, 64 * 0x144)
    panes = {array + i * 0x144 for i in range(64)}
    fields = {}
    for zone in range(7):
        if not any(memory.read_progress_bit(flags, 210 + zone * 3 + act) for act in range(3)):
            continue
        pane = array + columns[f'emerald_{zone}'.encode()] * 0x144
        # Do not replace an active native scale override or an intermediate
        # animation value. These are cached local properties, not matrices.
        if memory.read_u32(pane + 0x74) & 0x10:
            continue
        if memory.read_u32(pane + 0x7c) & 0x30 != 0x30:
            continue
        scale = memory.read_bytes(pane + 0x38, 8)
        if scale not in (bytes(8), bytes.fromhex('3f8000003f800000')):
            continue
        if scale != bytes(8) and (memory.read_u32(pane) or memory.read_u32(pane + 16)):
            continue
        fields[pane + 0x38] = ('column_scale', zone)
        fields[pane + 0x3c] = ('column_scale', zone)
        # Descendant world matrices must be recomputed as well. Keep all
        # local-property validity bits, including the newly restored scale.
        for child in panes:
            ancestor = child
            visited = set()
            while ancestor:
                if ancestor not in panes or ancestor in visited:
                    raise MemoryUnavailable('Game Land column parent topology invalid')
                visited.add(ancestor)
                if ancestor == pane:
                    fields[child + 0x7c] = ('dirty_matrix', None)
                    break
                ancestor = memory.read_u32(ancestor + 0x80)
        # Native 805E5310 reuses its cached local matrix when bits 4/5
        # remain valid, even after the world matrix is dirtied.
        fields[pane + 0x7c] = ('dirty_scale', None)
        ancestor = pane
        while ancestor:
            fields.setdefault(ancestor + 0x7c, ('dirty', None))
            parent = memory.read_u32(ancestor + 0x80)
            if not parent:
                root = memory.read_ptr_checked(ancestor + 0x84, 16)
                owner = memory.read_ptr_checked(root + 12, 0x3c)
                fields[root + 8] = ('zero', None)
                fields[owner + 8] = ('zero', None)
                fields[owner + 0x38] = ('one', None)
            ancestor = parent
    return fields
