"""Read active player model and attached item definitions, never invoke engine methods.

The list also includes PDA tools: presence is not synonymous with holding in a hand.
"""
from __future__ import annotations

import struct

from inventory_reader import Read, cstring, pointer, MODELS_RVA

PLAYER_RVA = 0x1C7D3E0
CHIEF_KEY = "M02_Dspot_key_item"
CONTEXT_MANAGER_RVA = 0x17EC090


def parse_item_node(data: bytes) -> tuple[int, int]:
    if len(data) != 0x18:
        raise ValueError("Incomplete attached-item node")
    next_node, definition = struct.unpack_from("<QQ", data, 8)
    if not definition:
        raise ValueError("Missing item definition")
    return next_node, definition


def read_context(read: Read, base: int, actor: int) -> dict:
    """Reproduce the observed InContext string lookup without calling the engine."""
    state = read(actor + 0x6B0, 0x18)
    if len(state) != 0x18:
        raise ValueError("Incomplete actor context state")
    current, secondary = struct.unpack_from("<i4xi", state)
    action = struct.unpack_from("<Q", state, 0x10)[0]
    if not action:
        return dict(status="no_action")
    if current == secondary:
        current = struct.unpack("<h", read(action + 0x11E, 2))[0]
    manager = pointer(read, base + CONTEXT_MANAGER_RVA)
    if not manager:
        return dict(status="not_initialized")
    count = struct.unpack("<I", read(manager + 0x8F0, 4))[0]
    if not 0 <= current < count <= 256:
        return dict(status="unresolved_index", index=current, count=count)
    definition = pointer(read, manager + 0xF0 + current * 8)
    name = cstring(read, pointer(read, definition + 8))
    if (read(actor + 0x6B0, 0x18) != state
            or pointer(read, base + CONTEXT_MANAGER_RVA) != manager):
        raise RuntimeError("Actor context changed during snapshot; retry")
    return dict(status="read", index=current, name=name)


def read_actor(read: Read, base: int) -> dict:
    actor = pointer(read, base + PLAYER_RVA)
    if not actor:
        return dict(status="not_initialized")
    flags = struct.unpack("<I", read(actor + 0xD4, 4))[0]
    if not flags & 0x1000:
        raise ValueError("Active player has unexpected character type flags")
    model = pointer(read, actor + 0x650)
    metadata = read(model, 0x38)
    if len(metadata) != 0x38:
        raise ValueError("Incomplete active model metadata")
    model_id = struct.unpack_from("<h", metadata, 8)[0]
    models = pointer(read, base + MODELS_RVA)
    count = struct.unpack("<I", read(models + 0xE0, 4))[0]
    if not 0 <= model_id < count <= 1024:
        raise ValueError("Active model id exceeds table bounds")
    table = pointer(read, models + 0x118)
    if pointer(read, table + model_id * 8) != model:
        raise ValueError("Active model does not match registered metadata")
    name = cstring(read, struct.unpack_from("<Q", metadata, 0x30)[0])
    items = pointer(read, actor + 0x8A0)
    head = pointer(read, items + 0x90) if items else 0
    node = head
    seen = set()
    rows = []
    links = []
    while node:
        if node in seen or len(rows) >= 128:
            raise ValueError("Cyclic or over-limit attached-item list")
        seen.add(node)
        data = read(node, 0x18)
        next_node, definition = parse_item_node(data)
        item_name = cstring(read, definition + 0x58)
        rows.append(dict(definition_name=item_name))
        links.append((node, data))
        node = next_node
    if (pointer(read, base + PLAYER_RVA) != actor or pointer(read, actor + 0x650) != model
            or pointer(read, actor + 0x8A0) != items
            or (items and pointer(read, items + 0x90) != head)
            or any(read(address, 0x18) != data for address, data in links)):
        raise RuntimeError("Actor/item state changed during snapshot; retry")
    return dict(status="read", equipped_model_id=model_id, equipped_internal_name=name,
                attached_item_definitions=rows,
                chief_office_key_present=any(row["definition_name"] == CHIEF_KEY for row in rows),
                held_in_hand_independently_verified=False, context=read_context(read, base, actor))
