"""Experimental native UI scan-marker registry; does not infer aura occupancy.

RVA 0x854f0 -> 0x231f60 registers AudioScan/CriminalScan/DetectiveMode.
Presence in this registry is distinct from standing inside or scanning.
"""
import math
import struct
from inventory_reader import pointer, cstring


def name_hash(name):
    value = 0x811c9dc5
    for byte in name.upper().encode('ascii'):
        value = ((value * 0x1000193) & 0xffffffff) ^ byte
    return value


SCAN_TYPES = {name_hash(name): label for name, label in (
    ('AudioScan', 'Gesprächsscan'), ('CriminalScan', 'Personen-/Kriminellenscan'),
    ('DetectiveMode', 'Detektivscan'))}


def read_auras(read, base):
    manager = pointer(read, base + 0x17EBC90)
    state = pointer(read, manager + 0x138)
    actor = pointer(read, base + 0x1C7D3E0)
    index = struct.unpack('<b', read(actor + 0x3E3, 1))[0]
    if not 0 <= index < 2:
        raise ValueError('Ungültiger lokaler Spielerindex')
    player = pointer(read, state + 0x1770 + index*8)
    # Inline accessors: +440, +288, +18, +58, then marker collection +258.
    root = player + 0x990
    if pointer(read, root) != base + 0xC7F028:
        raise ValueError('Unbekannte Scan-Markierungsverwaltung')
    head = pointer(read, root + 0x38)
    node, seen, rows, guards = head, set(), [], []
    while node:
        if node in seen or len(seen) >= 128:
            raise ValueError('Zyklische oder zu große Markierungsliste')
        seen.add(node)
        data = read(node, 0x70)
        definition = struct.unpack_from('<Q', data, 0x20)[0]
        if not definition:
            raise ValueError('Markierungsdefinition fehlt')
        # The definition begins with NuString headers, not a type hash.
        # Its second resource-name field at +0x30 has a string pointer +0x38.
        type_pointer = pointer(read, definition + 0x38)
        type_name = cstring(read, type_pointer)
        kind = name_hash(type_name)
        position = struct.unpack_from('<3f', data, 0x30)
        if not all(math.isfinite(v) for v in position):
            raise ValueError('Ungültige Markierungsposition')
        rows.append(dict(address=hex(node), type_hash=kind,
                         native_type_name=type_name,
                         type=SCAN_TYPES.get(kind, f'Markierung {kind:#x}'),
                         recognized_scan_type=kind in SCAN_TYPES,
                         native_id=struct.unpack_from('<I', data, 0x60)[0],
                         position=list(position), inside=None, locked=None,
                         evidence='native registered marker; occupancy/visibility unverified'))
        guards.append((node, data, definition, type_pointer, type_name))
        node = struct.unpack_from('<Q', data, 0x10)[0]
    if (pointer(read, root+0x38) != head or pointer(read, base+0x1C7D3E0) != actor or
            pointer(read, state+0x1770+index*8) != player or
            any(read(address, 0x70) != raw or pointer(read, definition+0x38) != type_pointer
                or cstring(read, type_pointer) != type_name
                for address, raw, definition, type_pointer, type_name in guards)):
        raise RuntimeError('Scan-Markierungen wechselten während der Aufnahme')
    return dict(status='read', markers=rows, player_index=index,
                registry=hex(root), occupancy_verified=False,
                source='native scan marker registry; experimental pending in-game comparison')


def aura_text(state):
    if state.get('status') != 'read':
        return 'Scan-Markierungen: unbekannt · ' + state.get('reason', 'nicht gelesen')
    rows = state['markers']
    if not rows:
        return 'Keine registrierten Scan-Markierungen\nAura unter Spieler: weiterhin unbestätigt'
    return ('Registrierte Markierungen (experimentell):\n' +
            '\n'.join(f"{r['type']} · ID {r['native_id']}" for r in rows) +
            '\nIn Aura / gesperrt: noch unbestätigt')


class AuraTracker:
    def __init__(self):
        self.previous = None

    def update(self, state):
        key = (state.get('status'), state.get('registry'), state.get('reason'),
               tuple(sorted((r['address'], r['type_hash'], r['native_id'])
                            for r in state.get('markers', []))))
        if key == self.previous:
            return None
        initial = self.previous is None
        self.previous = key
        return dict(kind='scan_markers_change', initial=initial, state=state,
                    automatic_check=False)
