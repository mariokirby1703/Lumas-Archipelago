"""Read-only LEGO City Undercover event monitor; no AP connection or game writes."""
import argparse
import ctypes
from datetime import datetime
import json
import math
from pathlib import Path
import queue
import struct
import sys
import threading
import time

import diagnose
from inventory_reader import pointer, read_stats, read_characters
from objective_reader import read_objectives
from monitor_events import EventTracker
from monitor_report import event_evidence, export_report
from location_reader import read_location
from story_reader import read_story
from monitor_sections import SectionTracker, location_heading, story_heading
from monitor_context import ContextTracker
from interaction_reader import (read_interaction, interaction_text, InteractionTracker,
                                read_scene_fields, scene_fields_text, SceneFieldTracker)
from aura_reader import read_auras, aura_text, AuraTracker
from floor_markers import read_class_availability
from pickup_reader import read_city_pickups, PickupMemory, attach_source_identities
from actor_reader import read_context, read_actor, PLAYER_RVA
from object_activity import ObjectActivityTracker


def resources():
    return Path(__file__).resolve().parent


class Session:
    def __init__(self):
        report = diagnose.diagnose()
        valid = [p for p in report.get('processes', []) if p['status'] == 'module_header_read']
        if len(valid) != 1:
            raise RuntimeError('Kein eindeutig unterstütztes Spiel gefunden. Spiel starten und erneut verbinden.')
        p = valid[0]
        self.kernel = diagnose.bind_kernel()
        self.handle = self.kernel.OpenProcess(0x1010, False, p['pid'])
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        self.base = int(p['module_base'], 16)
        self.pid = p['pid']
        self.pickup_memory=PickupMemory()
        self.pickup_sources=json.loads((resources()/'city_pickup_sources.json').read_text(encoding='utf-8'))

    def close(self):
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None

    def read(self, address, size):
        return diagnose.read_memory(self.kernel, self.handle, address, size)

    def snapshot(self):
        objectives = read_objectives(self.read, self.base)
        stats = read_stats(self.read, self.base)
        inventory = read_characters(self.read, self.base)
        if inventory.get('status') != 'read' or stats.get('status') != 'read':
            raise RuntimeError('Spielstand noch nicht geladen')
        manager = pointer(self.read, self.base + 0x17EC808)
        if not manager:
            raise RuntimeError('Sammelspeicher noch nicht geladen')
        payload = self.read(manager + 0x120, 1600)
        if self.read(manager + 0x120, 1600) != payload:
            raise RuntimeError('Sammelzustand wechselte während der Aufnahme')
        bits = [i*8+j for i,v in enumerate(payload) for j in range(8) if v & (1<<j)]
        ability_state = diagnose.research_state(self.kernel, self.handle, self.base)
        abilities = ability_state.get('script_query_unlocked')
        if abilities is None:
            raise RuntimeError('Fähigkeiten noch nicht geladen')
        try:
            location = read_location(self.read, self.base)
        except (OSError, ValueError, RuntimeError, struct.error) as error:
            location = dict(area_status='unresolved', error=str(error))
        try:
            interaction = read_interaction(self.read, self.base)
        except (OSError, ValueError, RuntimeError, struct.error) as error:
            interaction = dict(status='unresolved', reason=str(error))
        try:
            classes = read_class_availability(self.read, self.base, inventory)
            scene_fields = read_scene_fields(self.read, self.base, classes, abilities)
        except (OSError, ValueError, RuntimeError, struct.error) as error:
            scene_fields = dict(status='unresolved', reason=str(error))
        try:
            auras = read_auras(self.read, self.base)
        except (OSError, ValueError, RuntimeError, struct.error) as error:
            auras = dict(status='unresolved', reason=str(error))
        try:
            native_pickups=read_city_pickups(self.read,self.base)
        except (OSError,ValueError,RuntimeError,struct.error) as error:
            native_pickups=dict(status='unresolved',reason=str(error))
        attach_source_identities(native_pickups,self.pickup_sources)
        pickup_memory=self.pickup_memory.update(native_pickups)
        return dict(objectives=objectives, stats=stats, location=location, interaction=interaction,
                    scene_fields=scene_fields, auras=auras,native_pickups=native_pickups,
                    pickup_memory=pickup_memory,
                    actor=read_actor(self.read, self.base),
                    story=read_story(self.read, self.base),
                    characters=inventory['characters'] + inventory['auxiliary_states'],
                    pickup_bits=bits, pickup_bytes=list(payload), pickup_address=hex(manager+0x120),
                    abilities=abilities, ability_raw=ability_state.get('named_candidate_state', {}),
                    process=dict(pid=self.pid, module_base=hex(self.base), sha256=diagnose.RESEARCH_HASH))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sample', action='store_true', help='One read-only console snapshot, no window')
    parser.add_argument('--sample-output', type=Path, help='Write a single diagnostic snapshot to JSON')
    parser.add_argument('--ui-smoke', action='store_true', help='Open and close the window automatically for build validation')
    args = parser.parse_args()
    if args.sample or args.sample_output:
        session = Session()
        try:
            snapshot = session.snapshot()
            report = json.dumps(dict(pid=session.pid, stats=snapshot['stats'], pickup_bits=snapshot['pickup_bits'],
                                    objectives=len(snapshot['objectives']['records']),
                                    interaction=snapshot['interaction'], scene_fields=snapshot['scene_fields'],
                                    auras=snapshot['auras'],native_pickups=snapshot['native_pickups'],
                                    pickup_memory=snapshot['pickup_memory'], writes_enabled=False), indent=2)
            if args.sample_output:
                args.sample_output.write_text(report, encoding='utf-8')
            else:
                print(report)
        finally:
            session.close()
        return

    import tkinter as tk
    from tkinter import ttk
    from tkinter.scrolledtext import ScrolledText
    root = tk.Tk()
    root.title('LEGO City Undercover · Live Check Monitor')
    root.geometry('1480x800')
    status = tk.StringVar(value='Nicht verbunden. Erst Spielstand laden, dann Verbinden drücken.')
    stats_line = tk.StringVar(value='Nur lesend · Keine AP-Verbindung · Keine Veränderungen am Spiel')
    ttk.Label(root, textvariable=status, wraplength=980).pack(anchor='w', padx=14, pady=(12,4))
    ttk.Label(root, textvariable=stats_line).pack(anchor='w', padx=14)
    pickup_coverage=tk.StringVar(value='Pickup-Beobachter: noch keine Aufnahme')
    ttk.Label(root,textvariable=pickup_coverage).pack(anchor='w',padx=14)
    controls = ttk.Frame(root)
    controls.pack(fill='x', padx=14, pady=10)
    panes = ttk.Panedwindow(root, orient='horizontal')
    panes.pack(fill='both', expand=True, padx=14, pady=(0,12))
    pickup_pane = ttk.Frame(panes)
    context_pane = ttk.Frame(panes)
    interaction_pane = ttk.Frame(panes)
    panes.add(pickup_pane, weight=3)
    panes.add(context_pane, weight=1)
    panes.add(interaction_pane, weight=2)
    ttk.Label(interaction_pane, text='Aktionsfelder und Auren · Diagnose').pack(anchor='w')
    interaction_tabs = ttk.Notebook(interaction_pane)
    interaction_tabs.pack(fill='both', expand=True)
    field_tab, aura_tab, history_tab = (ttk.Frame(interaction_tabs) for _ in range(3))
    interaction_tabs.add(field_tab, text='Objekte')
    interaction_tabs.add(aura_tab, text='Scan-Auren')
    interaction_tabs.add(history_tab, text='Verlauf')
    show_all_fields = tk.BooleanVar(value=False)
    latest_fields = None
    def update_field_filter():
        if latest_fields is not None:
            fields_current.set(scene_fields_text(latest_fields, limit=None, show_all=show_all_fields.get()))
            refresh_fields()
    ttk.Checkbutton(field_tab, text='Gesamte Szene anzeigen (Diagnose)', variable=show_all_fields,
                    command=update_field_filter).pack(anchor='w')
    interaction_current = tk.StringVar(value='Noch keine Aufnahme')
    fields_current = tk.StringVar(value='Szenenobjekte: noch keine Aufnahme')
    fields_view = ScrolledText(field_tab, wrap='word', width=40, font=('Consolas', 10), state='disabled')
    fields_view.pack(fill='both', expand=True)
    auras_current = tk.StringVar(value='Scan-Markierungen: noch keine Aufnahme')
    auras_view = ScrolledText(aura_tab, wrap='word', width=40, font=('Consolas', 10), state='disabled')
    auras_view.pack(fill='both', expand=True)
    interaction_output = ScrolledText(history_tab, wrap='word', width=38,
                                     font=('Consolas', 10), state='disabled')
    interaction_output.pack(fill='both', expand=True)

    def replace_view(view, text):
        if view.get('1.0', 'end-1c') == text:
            return
        position = view.yview()[0]
        view.configure(state='normal')
        view.delete('1.0', 'end')
        view.insert('1.0', text)
        view.yview_moveto(position)
        view.configure(state='disabled')

    def refresh_fields():
        replace_view(fields_view, interaction_current.get() + '\n\n' + fields_current.get())

    refresh_fields()
    replace_view(auras_view, auras_current.get())
    ttk.Label(pickup_pane, text='Funde und Aktivitäten').pack(anchor='w')
    output = ScrolledText(pickup_pane, wrap='word', font=('Consolas', 10), state='disabled')
    output.pack(fill='both', expand=True)
    context_current = tk.StringVar(value='Kontext: noch nicht gelesen')
    ttk.Label(context_pane, textvariable=context_current).pack(anchor='w')
    ttk.Label(context_pane, text='Gegenstände am Spieler · Handstatus unbestätigt').pack(anchor='w')
    items_current = tk.StringVar(value='Noch keine Aufnahme')
    ttk.Label(context_pane, textvariable=items_current, wraplength=340, justify='left').pack(anchor='w', pady=(0,8))
    context_output = ScrolledText(context_pane, wrap='word', width=34, font=('Consolas', 10), state='disabled')
    context_output.pack(fill='both', expand=True)
    messages = queue.Queue()
    captures = queue.Queue()
    report_records = []
    stop = threading.Event()
    worker = None
    labels = json.loads((resources() / 'monitor_labels.json').read_text(encoding='utf-8'))
    log_dir = (Path(sys.executable).parent if getattr(sys, 'frozen', False) else resources().parent / 'notes') / 'monitor_logs'

    def append(text):
        output.configure(state='normal')
        output.insert('end', text + '\n')
        output.see('end')
        output.configure(state='disabled')

    def run():
        session = None
        try:
            session = Session()
            tracker = EventTracker(labels)
            sections = SectionTracker()
            contexts = ContextTracker()
            interactions = InteractionTracker()
            fields_tracker = SceneFieldTracker()
            aura_tracker = AuraTracker()
            object_activities=ObjectActivityTracker()
            log_dir.mkdir(parents=True, exist_ok=True)
            with (log_dir / (datetime.now().strftime('%Y%m%d_%H%M%S_%f') + '.jsonl')).open('x', encoding='utf-8') as log:
                messages.put(('status', f'Verbunden mit PID {session.pid}. Ausgangszustand wird gelesen …'))
                failures = 0
                capture_baseline = None
                previous_items = None
                previous_pickup_identities=None
                next_snapshot = 0.0
                while not stop.is_set():
                    try:
                        actor = pointer(session.read, session.base + PLAYER_RVA)
                        if actor:
                            action = read_context(session.read, session.base, actor)
                            if pointer(session.read, session.base + PLAYER_RVA) != actor:
                                raise RuntimeError('Spieler wechselte während der Kontextaufnahme')
                            context_event = contexts.update(action)
                            if context_event:
                                context_event.update(time=datetime.now().isoformat(timespec='milliseconds'), actor=hex(actor))
                                try:
                                    vtable=pointer(session.read,actor+0x10)
                                    if pointer(session.read,vtable+0xF0)==session.base+0x49ECF0:
                                        position=struct.unpack('<3f',session.read(actor+0x1F0,12))
                                        if (all(math.isfinite(v) for v in position) and
                                                pointer(session.read,session.base+PLAYER_RVA)==actor):
                                            context_event['location']=dict(player_position=list(position),
                                                                          source='verified actor transform accessor')
                                except (OSError,ValueError,struct.error):
                                    pass
                                log.write(json.dumps(context_event, ensure_ascii=False) + '\n')
                                log.flush()
                                messages.put(('record', context_event))
                                messages.put(('context', context_event))
                        if time.monotonic() < next_snapshot:
                            stop.wait(0.1)
                            continue
                        next_snapshot = time.monotonic() + 1.0
                        snapshot = session.snapshot()
                        for observation in object_activities.update(snapshot['scene_fields']):
                            observation['time']=datetime.now().isoformat(timespec='milliseconds')
                            log.write(json.dumps(observation,ensure_ascii=False)+'\n');log.flush()
                            messages.put(('record',observation))
                            messages.put(('object_activity',observation))
                        memory=snapshot['pickup_memory']
                        messages.put(('pickup_coverage',(snapshot['native_pickups'],memory)))
                        identities=tuple(sorted((r['collection_bit'],r.get('tile_name',''),r['name'],r.get('source_key') or '')
                                                for r in memory['objects']))
                        if identities!=previous_pickup_identities:
                            observation=dict(kind='pickup_catalogue_change',time=datetime.now().isoformat(timespec='milliseconds'),
                                             automatic_check=False,state=memory)
                            log.write(json.dumps(observation,ensure_ascii=False)+'\n');log.flush()
                            messages.put(('record',observation))
                            previous_pickup_identities=identities
                        for key, observation_tracker in (('scene_fields', fields_tracker), ('auras', aura_tracker)):
                            messages.put((key, snapshot[key]))
                            observation = observation_tracker.update(snapshot[key])
                            if observation:
                                observation['time'] = datetime.now().isoformat(timespec='milliseconds')
                                log.write(json.dumps(observation, ensure_ascii=False) + '\n')
                                log.flush()
                                messages.put(('record', observation))
                                messages.put(('observation_history', observation))
                        messages.put(('interaction', snapshot['interaction']))
                        interaction_event = interactions.update(snapshot['interaction'])
                        if interaction_event:
                            interaction_event['time'] = datetime.now().isoformat(timespec='milliseconds')
                            log.write(json.dumps(interaction_event, ensure_ascii=False) + '\n')
                            log.flush()
                            messages.put(('record', interaction_event))
                            messages.put(('interaction_history', interaction_event))
                        item_names = sorted(r['definition_name'] for r in snapshot['actor']['attached_item_definitions'])
                        messages.put(('items', item_names))
                        if item_names != previous_items:
                            record = dict(kind='attached_items_change', time=datetime.now().isoformat(timespec='milliseconds'),
                                          initial=previous_items is None, before=previous_items, after=item_names,
                                          location=snapshot['location'], hand_item_verified=False,
                                          evidence='attached item definitions, not proof of hand possession')
                            log.write(json.dumps(record, ensure_ascii=False) + '\n')
                            log.flush()
                            messages.put(('record', record))
                            previous_items = item_names
                        if capture_baseline is None:
                            capture_baseline = snapshot
                        initial = tracker.previous is None
                        previous = tracker.previous
                        events = tracker.update(snapshot)
                        for section in sections.update(snapshot):
                            section['time'] = datetime.now().isoformat(timespec='seconds')
                            log.write(json.dumps(section, ensure_ascii=False) + '\n')
                            log.flush()
                            messages.put(('record', section))
                            messages.put(('event', section['text']))
                        failures = 0
                        messages.put(('status', 'Verbunden · Beobachtet neue Änderungen ab Verbindungsbeginn.'))
                        messages.put(('stats', snapshot['stats']))
                        messages.put(('area', snapshot['location']))
                        messages.put(('story_status', snapshot['story']))
                        if initial:
                            messages.put(('event', 'Ausgangszustand gesichert. Bereits vorhandene Funde werden nicht als neue Checks angezeigt.'))
                        for event in events:
                            event = event_evidence(event, previous, snapshot)
                            event['time'] = datetime.now().isoformat(timespec='seconds')
                            log.write(json.dumps(event, ensure_ascii=False) + '\n')
                            log.flush()
                            messages.put(('record', event))
                            messages.put(('event', f"{event['time'][11:]}  {event['text']}"))
                        while not captures.empty():
                            try:
                                note = captures.get_nowait()
                            except queue.Empty:
                                break
                            record = dict(kind='manual_observation', time=datetime.now().isoformat(timespec='seconds'),
                                          note=note, automatic_detection=False,
                                          mission_reader_status='Schildviertel/Held/Abschluss noch nicht automatisch erkannt',
                                          snapshot=snapshot, previous_snapshot=capture_baseline,
                                          story=read_story(session.read, session.base))
                            log.write(json.dumps(record, ensure_ascii=False) + '\n')
                            log.flush()
                            messages.put(('record', record))
                            messages.put(('event', f"Diagnoseaufnahme: {note} (manuell markiert, kein erkannter Check)"))
                            capture_baseline = snapshot
                    except (OSError, ValueError, RuntimeError, struct.error) as error:
                        failures += 1
                        messages.put(('status', f'Warte auf stabilen Spielzustand: {error}'))
                        if failures >= 10:
                            raise RuntimeError('Verbindung unterbrochen. Nach Laden/Neustart erneut verbinden.') from error
                    stop.wait(0.1)
        except Exception as error:
            messages.put(('status', str(error)))
        finally:
            if session:
                session.close()
            messages.put(('ended', None))

    def connect():
        nonlocal worker
        if worker and worker.is_alive():
            return
        stop.clear()
        worker = threading.Thread(target=run, daemon=True)
        worker.start()
        connect_button.configure(state='disabled')

    connect_button = ttk.Button(controls, text='Mit Spiel verbinden', command=connect)
    connect_button.pack(side='left')
    ttk.Button(controls, text='Trennen', command=stop.set).pack(side='left', padx=8)
    def copy_log():
        root.clipboard_clear()
        root.clipboard_append(export_report(report_records))
        root.update_idletasks()
        append(f'Log kopiert: {len(report_records)} Einträge mit IDs, Position und Rohwerten.')

    ttk.Button(controls, text='Log kopieren', command=copy_log).pack(side='left', padx=8)
    research = ttk.Frame(root)
    research.pack(fill='x', padx=14, pady=(0,8), before=panes)
    area_line = tk.StringVar(value='Gebiet: noch keine Aufnahme')
    ttk.Label(root, textvariable=area_line).pack(anchor='w', padx=14, before=research)
    story_line = tk.StringVar(value='Storyfortschritt: noch keine Aufnahme')
    ttk.Label(root, textvariable=story_line).pack(anchor='w', padx=14, before=research)
    note = tk.StringVar(value='Schildteil TL eingesammelt')
    ttk.Combobox(research, textvariable=note, width=40,
                 values=('Schildteil TL eingesammelt', 'Schildteil TR eingesammelt',
                         'Schildteil BL eingesammelt', 'Schildteil BR eingesammelt',
                         'Räuber-Verkleidung freigeschaltet', 'Gefängnis betreten',
                         'Gefängnis: Direktorenbüro erreicht',
                         'LEGO-City-Held erreicht', 'Mission abgeschlossen', 'Level betreten')).pack(side='left')
    def capture():
        if not worker or not worker.is_alive():
            append('Für eine Diagnoseaufnahme zuerst verbinden.')
            return
        captures.put(note.get()[:300])
    ttk.Button(research, text='Diagnose markieren', command=capture).pack(side='left', padx=8)
    ttk.Label(research, text='Missionsteile: manuelle Diagnose, noch keine automatische Erkennung.').pack(side='left')

    def poll():
        nonlocal latest_fields
        while True:
            try:
                kind, value = messages.get_nowait()
            except queue.Empty:
                break
            if kind == 'status': status.set(value)
            elif kind == 'stats': stats_line.set(f"Studs: {value['studs']:,}   Bausteine: {value['super_bricks']:,}   Goldsteine (Diagnose): {value['gold_bricks']}")
            elif kind == 'record': report_records.append(value)
            elif kind == 'pickup_coverage':
                current,memory=value
                pickup_coverage.set(f"Pickup-Beobachter: {current.get('components',0)} Komponenten · "
                                    f"{len(current.get('objects',[]))} geladene Objekte · "
                                    f"{len(memory['objects'])} gespeicherte Identitäten · "
                                    f"{len(memory['conflicts'])} Konflikte · teilweise Abdeckung")
            elif kind == 'interaction':
                interaction_current.set(interaction_text(value))
                refresh_fields()
            elif kind == 'scene_fields':
                latest_fields = value
                update_field_filter()
            elif kind == 'auras':
                auras_current.set(aura_text(value))
                replace_view(auras_view, auras_current.get())
            elif kind == 'observation_history':
                text = scene_fields_text(value['state']) if value['kind'] == 'scene_fields_change' else aura_text(value['state'])
                interaction_output.configure(state='normal')
                interaction_output.insert('end', value['time'][11:] + '\n' + text + '\n\n')
                interaction_output.see('end')
                interaction_output.configure(state='disabled')
            elif kind == 'object_activity':
                interaction_output.configure(state='normal')
                interaction_output.insert('end',f"{value['time'][11:]} Objektzustand (kein Check): {value['family']}\n"
                                          f"{value['name']}\n{value['changes']}\n\n")
                interaction_output.see('end')
                interaction_output.configure(state='disabled')
            elif kind == 'interaction_history':
                interaction_output.configure(state='normal')
                interaction_output.insert('end', value['time'][11:] + '\n' + interaction_text(value['state']) + '\n\n')
                interaction_output.see('end')
                interaction_output.configure(state='disabled')
            elif kind == 'items': items_current.set('\n'.join(value) if value else 'Keine Einträge · Handstatus weiterhin unbekannt')
            elif kind == 'context':
                context_current.set(f"Kontext: {value['name']} ({value['index']})")
                context_output.configure(state='normal')
                context_output.insert('end', f"{value['time'][11:]}  {value['name']} ({value['index']})\n")
                context_output.see('end')
                context_output.configure(state='disabled')
            elif kind == 'area': area_line.set(f"{location_heading(value)} · Position: {value.get('player_position', 'unbekannt')}")
            elif kind == 'story_status': story_line.set(story_heading(value))
            elif kind == 'event': append(value)
            elif kind == 'ended':
                latest_fields = None
                connect_button.configure(state='normal')
                interaction_current.set('Nicht verbunden · keine aktuelle Objektaufnahme')
                fields_current.set('Szenenobjekte: nicht verbunden')
                auras_current.set('Scan-Markierungen: nicht verbunden')
                pickup_coverage.set('Pickup-Beobachter: nicht verbunden')
                refresh_fields()
                replace_view(auras_view, auras_current.get())
        root.after(100, poll)

    def close():
        stop.set()
        root.destroy()

    root.protocol('WM_DELETE_WINDOW', close)
    poll()
    if args.ui_smoke:
        root.after(500, close)
    root.mainloop()


if __name__ == '__main__':
    main()
