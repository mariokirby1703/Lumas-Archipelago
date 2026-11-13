"""Bounded read-only GizSwitch candidate reader for the pinned executable.

The selection slot may retain a previous target. Proximity is reported, never
promoted to proof of standing on a field, usability, or completion.
"""
import math
import struct

from inventory_reader import pointer
from scene_reader import player_scene, scene_component
from floor_markers import predict_floor_marker


def immediate_proximity(position, player):
    """Conservative display filter, not the engine's interaction radius."""
    return (math.hypot(position[0]-player[0], position[2]-player[2]) <= 0.75
            and abs(position[1]-player[1]) <= 0.35)


def field_family(name):
    for token, label in (('BNE_STEELDOOR', 'Brechstangentür'),
                         ('ATM_SMASH', 'Geldautomat zerstören'),
                         ('ATM_USE', 'Geldautomat benutzen'),
                         ('Flower_Bed', 'Blumen gießen'),
                         ('Mini_Fishing', 'Angeln'),
                         ('Fish_Throw', 'Fisch abgeben'),
                         ('FUSE_BOX', 'Sicherungskasten'),
                         ('MusicSwitch', 'Musik-/Schallplatten-Schalter'),
                         ('SAFE_', 'Tresor / Stethoskop'),
                         ('DETECTIVE_', 'Detektivstelle'),
                         ('Axe_', 'Axtfeld'), ('KEYPAD', 'Tastenfeld'),
                         ('Locker_Robber', 'Räuber-Verkleidung'),
                         ('scannercrime', 'Kriminellenscan-Stelle')):
        if token.lower() in name.lower():
            return label
    return 'Interaktionsobjekt (Typ offen)'


def read_scene_fields(read, base, classes=None, abilities=None):
    scene = player_scene(read, base)
    player = struct.unpack('<3f', read(scene['actor'] + 0x1F0, 12))
    if not all(math.isfinite(v) for v in player):
        raise ValueError('Ungültige Spielerposition')
    groups, guards = [], []
    for global_rva, component_vtable, object_vtable, system in (
            (0x17EC098, 0xC34ED8, 0xC34578, 'GizSwitch'),
            (0x17EC940, 0xC36198, 0xC35A98, 'Techno')):
        component = scene_component(read, base, scene, global_rva)
        if not component:
            continue
        if pointer(read, component) != base + component_vtable:
            raise ValueError(f'Unbekanntes {system}-Szenensystem')
        head = pointer(read, component + 0xE0)
        node, seen, rows = head, set(), []
        while node:
            if node in seen or len(seen) >= 1024:
                raise ValueError('Zyklische oder zu große Szenenliste')
            seen.add(node)
            size = 0x400 if system == 'GizSwitch' else 0x190
            data = read(node, size)
            if struct.unpack_from('<Q', data)[0] != base + object_vtable:
                raise ValueError(f'Unbekanntes {system}-Objektlayout')
            if struct.unpack_from('<Q', data, 0x48)[0] != component:
                raise ValueError('Objekt gehört nicht zur ermittelten Szene')
            name = data[0x58:0x78].split(b'\0')[0].decode('ascii')
            position = struct.unpack_from('<3f', data, 0x22C if system == 'GizSwitch' else 0x78)
            if not all(math.isfinite(v) for v in position):
                raise ValueError('Ungültige Aktionsobjektposition')
            row = dict(address=hex(node), name=name, system=system,
                       family=field_family(name), position=list(position),
                       distance=math.dist(position, player), locked=None,
                       immediate_proximity=immediate_proximity(position, player),
                       under_player_verified=False,
                       classification_evidence='native object name; tool label not a decoded permission result')
            if system == 'GizSwitch':
                flags = struct.unpack_from('<I', data, 0x24C)[0]
                row.update(requirement_flags=hex(flags),
                           state_flags=hex(struct.unpack_from('<I', data, 0x278)[0]),
                           object_flags=hex(struct.unpack_from('<H', data, 0x8A)[0]),
                           marker=predict_floor_marker(flags, classes, abilities,
                                                       struct.unpack_from('<h', data, 0x3FA)[0]))
            rows.append(row)
            next_node = struct.unpack_from('<Q', data, 0x28)[0]
            guards.append((node, component, next_node))
            node = next_node
        groups.append(dict(system=system, component=component, head=head, fields=rows))
    if any(pointer(read, address+0x48) != owner or pointer(read, address+0x28) != next_node
           for address, owner, next_node in guards):
        raise RuntimeError('Aktionsobjektliste wechselte während der Aufnahme')
    check = player_scene(read, base)
    if check != scene or any(pointer(read, g['component']+0xE0) != g['head'] for g in groups):
        raise RuntimeError('Szene wechselte während der Aufnahme')
    fields = sorted((r for g in groups for r in g['fields']), key=lambda r: r['distance'])
    return dict(status='read', fields=fields, level=hex(scene['level']),
                player_position=list(player),
                scope='loaded GizSwitch and Techno objects; not every game interaction system',
                proximity_is_not_activation=True)


def scene_fields_text(state, limit=6, show_all=False):
    if state.get('status') != 'read':
        return 'Szenenobjekte: unbekannt · ' + state.get('reason', 'nicht gelesen')
    all_rows = state['fields']
    rows = all_rows if show_all else [r for r in all_rows if r.get('immediate_proximity')]
    heading = 'Gesamte Szene · auch entfernte/andere Etagen' if show_all else 'Unmittelbare Nähe · gleiche Höhe'
    return (f"{heading}: {len(rows)}\n" +
            '\n'.join(f"{r['distance']:.2f} · {r['family']}\n  {r['name']}\n  " +
                      (r.get('marker', {}).get('predicted_marker') or 'Marker unbekannt').replace('Hotspot_Ability_Floor_', '')
                      for r in rows[:limit]) +
            f'\n{len(all_rows)-len(rows)} weitere Objekte ausgeblendet' +
            '\nNähefilter ≠ nachgewiesene Feldgrenze.\nMarker abgeleitet · Benutzbarkeit unbestätigt')


def read_interaction(read, base):
    manager = pointer(read, base + 0x17EC098)
    if not manager or pointer(read, manager) != base + 0xC34AE8:
        return dict(status='unresolved', reason='GizSwitch-System nicht verfügbar')
    selection = read(manager + 0x110, 0x10)
    target, native_distance_squared, native_result = struct.unpack('<Qfi', selection)
    if not target:
        return dict(status='no_candidate')
    if not math.isfinite(native_distance_squared):
        raise ValueError('Ungültiger nativer Auswahlabstand')
    data = read(target, 0x250)
    if struct.unpack_from('<Q', data)[0] != base + 0xC34578:
        return dict(status='unresolved', reason='Objekttyp noch nicht unterstützt')
    name = data[0x58:0x78].split(b'\0')[0].decode('ascii')
    origin = struct.unpack_from('<3f', data, 0x78)
    position = struct.unpack_from('<3f', data, 0x22C)
    flags = struct.unpack_from('<I', data, 0x24C)[0]
    actor = pointer(read, base + 0x1C7D3E0)
    player = struct.unpack('<3f', read(actor + 0x1F0, 12))
    if not all(math.isfinite(v) for v in (*origin, *position, *player)):
        raise ValueError('Invalid interaction coordinates')
    if (pointer(read, manager + 0x110) != target or
            struct.unpack('<i', read(manager + 0x11C, 4))[0] != native_result or
            pointer(read, base + 0x1C7D3E0) != actor or read(target, 0x250) != data):
        raise RuntimeError('Interaktionsziel wechselte während der Aufnahme')
    distance = math.dist(position, player)
    return dict(status='candidate', address=hex(target), name=name,
                family=field_family(name),
                object_origin=list(origin), interaction_position=list(position),
                player_position=list(player), distance=distance, nearby=distance <= 2.0,
                immediate_proximity=immediate_proximity(position, player),
                requirement_flags=hex(flags), explicit_crowbar_item_bit=bool(flags & 0x80000),
                robber_class_requirement_bit=bool(flags & 0x100),
                native_selection_result=native_result,
                native_selection_distance_squared=native_distance_squared,
                locked=None, field_under_player_verified=False,
                source='GizSwitch manager +0x110; selection/retention semantics unverified')


def interaction_text(state):
    if state['status'] != 'candidate':
        return ('Aktionsfeld: nicht bestimmt\n' + state.get('reason', 'Kein GizSwitch-Kandidat') +
                '\nScan-Aura: noch nicht auslesbar\nSperrzustand: unbekannt')
    if not state.get('immediate_proximity'):
        return ('Kein ausgewähltes Feld in unmittelbarer Nähe.\n'
                'Die native Auswahl verweist auf ein weiter entferntes Objekt; Details stehen im Log.')
    proximity = 'nah' if state['nearby'] else 'entfernt / möglicherweise altes Ziel'
    return (f"Objektkandidat: {state['family']}\n{state['name']}\n"
            f"Abstand: {state['distance']:.2f} ({proximity})\n"
            f"Flags: {state['requirement_flags']}\n"
            f"Nativer Prüfwert: {state.get('native_selection_result', 'unbekannt')} (Bedeutung im Test prüfen)\n"
            f"Brechstangen-Itemprüfung: {'gesetzt' if state['explicit_crowbar_item_bit'] else 'nicht gesetzt'}\n"
            f"Räuber-Prüfungsbit: {'gesetzt' if state['robber_class_requirement_bit'] else 'nicht gesetzt'}\n"
            'Aktionsfeld unter Spieler: unbestätigt\nSperrzustand: unbekannt\n'
            'Scan-Aura: noch nicht auslesbar')


class InteractionTracker:
    def __init__(self):
        self.previous = None

    def update(self, state):
        key = tuple(state.get(k) for k in ('status', 'address', 'name', 'requirement_flags',
                                         'native_selection_result', 'nearby', 'immediate_proximity', 'reason'))
        if key == self.previous:
            return None
        initial = self.previous is None
        self.previous = key
        return dict(kind='interaction_target_change', initial=initial, state=state,
                    automatic_check=False)


class SceneFieldTracker:
    def __init__(self):
        self.previous = None

    def update(self, state):
        key = (state.get('status'), state.get('level'), state.get('reason'),
               tuple(sorted((r['address'], r['name'], r.get('requirement_flags'),
                             r.get('state_flags'), r.get('object_flags'), r.get('immediate_proximity'),
                             r.get('marker', {}).get('predicted_marker'))
                            for r in state.get('fields', []))))
        if key == self.previous:
            return None
        initial = self.previous is None
        self.previous = key
        return dict(kind='scene_fields_change', initial=initial, state=state,
                    automatic_check=False)
