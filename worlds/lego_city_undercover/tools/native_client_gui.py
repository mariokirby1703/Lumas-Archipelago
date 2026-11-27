"""Native LEGO City Undercover Archipelago GUI.

The Tk thread owns widgets. A worker thread owns the AP asyncio loop. Communication
uses queues exclusively. Local item tests are deliberately opt-in and do not
modify Archipelago receipts or location checks.
"""
from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import logging
import os
from pathlib import Path
import queue
import sys
import threading
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox, ttk
from urllib.parse import urlsplit

WORLD = Path(__file__).resolve().parents[1]
ROOT = WORLD.parents[1]
SETTINGS = ROOT / 'build/lego_city_undercover/native_client_ui.json'
SAVE_SUFFIX = '.legocityundercoversavegamedata'
sys.path.insert(0, str(WORLD / 'bridge'))
from native_bridge_path import bridge_path
from native_build_integrity import bridge_health
from test_overrides import supported
from test_catalogue import test_catalogue,normalize_search
from capabilities import ITEM_ALIASES


def connection_address(address: str, port: str | int) -> str:
    """Return HOST:PORT or ws(s)://HOST:PORT, rejecting embedded credentials."""
    address = address.strip()
    try:
        number = int(port)
    except (TypeError, ValueError):
        raise ValueError('Der Port muss eine Zahl sein.') from None
    if not 1 <= number <= 65535:
        raise ValueError('Port muss zwischen 1 und 65535 liegen.')
    if not address:
        raise ValueError('Bitte eine Server-Adresse eingeben.')
    try:
        parsed = urlsplit(address if '://' in address else '//' + address)
        embedded_port = parsed.port
    except ValueError:
        raise ValueError('Ungültige Server-Adresse.') from None
    if (not parsed.hostname or parsed.username or parsed.password or
            parsed.path not in ('', '/') or parsed.query or parsed.fragment):
        raise ValueError('Bitte nur eine Server-Adresse eingeben, ohne Pfad oder Zugangsdaten.')
    if parsed.scheme and parsed.scheme not in ('ws', 'wss'):
        raise ValueError('Unterstützt werden nur ws:// und wss://.')
    if embedded_port is not None:
        raise ValueError('Den Port bitte ausschließlich im separaten Port-Feld eingeben.')
    host = parsed.hostname
    if ':' in host:
        host = '[' + host + ']'
    return (parsed.scheme + '://' if parsed.scheme else '') + host + ':' + str(number)


def load_settings(path: Path = SETTINGS) -> dict:
    """Whitelist benign settings; passwords and AP item data are never stored."""
    defaults = dict(address='archipelago.gg', port='58404', name='', save_file='',
                    native=True, cutscene_skip=True)
    try:
        parsed = json.loads(Path(path).read_text(encoding='utf-8'))
        if isinstance(parsed, dict):
            for key, value in defaults.items():
                if key in parsed and type(parsed[key]) is type(value):
                    defaults[key] = parsed[key]
    except (OSError, ValueError):
        pass
    return defaults


def validate_start(native_enabled: bool, save_file: str, *, root: Path = ROOT,
                   platform: str = sys.platform, bits: int = sys.maxsize.bit_length()) -> Path | None:
    """Check native prerequisites without touching the game or its save."""
    if native_enabled:
        if platform != 'win32' or bits <= 32:
            raise ValueError('Native Item-Änderungen benötigen 64-Bit-Python auf Windows.')
        dll = bridge_path(root)
        if not dll.is_file():
            raise ValueError('Die native DLL fehlt: ' + str(dll) +
                             '\nBitte tools/build_item_bridge.py ausführen oder Native Items deaktivieren.')
    if save_file:
        path = Path(save_file).expanduser()
        if not path.is_file() or not path.name.endswith(SAVE_SUFFIX):
            raise ValueError('Die ausgewählte Spielstanddatei existiert nicht oder hat das falsche Format.')
        return path.resolve()
    return None


class EventLogHandler(logging.Handler):
    def __init__(self, events: queue.Queue, password: str):
        super().__init__()
        self.events = events
        self.password = password

    def emit(self, record: logging.LogRecord) -> None:
        try:
            line = self.format(record)
            if self.password:
                line = line.replace(self.password, '[Passwort]')
            self.events.put(('log', line))
        except Exception:
            self.handleError(record)


class App:
    def __init__(self, root: tk.Tk, args: argparse.Namespace):
        self.root = root
        self.args = args
        self.events: queue.Queue = queue.Queue()
        self.commands: queue.Queue = queue.Queue()
        self.worker: threading.Thread | None = None
        self.closing = False
        self.stopping = False
        self.ap_connected = False
        self.game_connected = False
        self.native_ready = False
        self.tests_confirmed = False
        self.item_states={};self.history_rows=[];self._selecting=False
        self.history_session=datetime.now().isoformat(timespec='microseconds')
        self.history_path=ROOT/'build/lego_city_undercover/native_test_history.json'
        self.only_missing=tk.BooleanVar(value=False)
        self.show_popups=tk.BooleanVar(value=True)
        self.only_supported=tk.BooleanVar(value=True)
        self.result_count=tk.StringVar()
        self.settings_path = SETTINGS

        settings = load_settings(self.settings_path)
        if args.connect:
            parsed = urlsplit(args.connect if '://' in args.connect else '//' + args.connect)
            settings['address'] = (parsed.scheme + '://' if parsed.scheme else '') + (parsed.hostname or args.connect)
            if parsed.port:
                settings['port'] = str(parsed.port)
        if args.name:
            settings['name'] = args.name
        if args.native_save_file:
            settings['save_file'] = str(args.native_save_file)

        self.address = tk.StringVar(value=settings['address'])
        self.port = tk.StringVar(value=settings['port'])
        self.name = tk.StringVar(value=settings['name'])
        self.password = tk.StringVar()
        self.save_file = tk.StringVar(value=settings['save_file'])
        self.use_native = tk.BooleanVar(value=settings['native'])
        self.cutscene_skip = tk.BooleanVar(value=settings['cutscene_skip'])
        self.item = tk.StringVar()
        self.item_category = tk.StringVar(value='Alle Item-Kategorien')
        self.ap_status = tk.StringVar(value='Archipelago: Nicht verbunden')
        self.game_status = tk.StringVar(value='Spiel: Nicht geladen')
        self.area_status = tk.StringVar(value='Gebietssperre: nicht aktiv')
        self.pickup_binding_status=tk.StringVar(value='Supersteine: noch keine Aufnahme')
        self.seed_status=tk.StringVar(value='Seed: nicht verbunden')
        self.collectible_evidence={}
        self.area_evidence={}
        self.save_status = tk.StringVar(value='Save: Nicht gebunden')
        self.pause_menu_status = tk.StringVar(value='Pausemenü: warte auf Verbindung und geladenes Spiel')
        self.progress = tk.StringVar(value='Checks: 0 · AP-Items: 0')
        self.item_info = tk.StringVar(value='Item suchen oder auswählen.')

        catalogue = json.loads((WORLD / 'catalogue.json').read_text(encoding='utf-8'))
        self.effects = test_catalogue(catalogue,json.loads((WORLD/'bridge/collection_manifest.json').read_text(encoding='utf-8')))
        self.names = sorted(self.effects, key=str.casefold)

        version=json.loads((WORLD/'archipelago.json').read_text(encoding='utf-8'))['world_version']
        root.title(f'LEGO City Undercover | Archipelago Client {version}')
        root.geometry('1380x920')
        root.minsize(1080, 780)
        style = ttk.Style()
        if 'clam' in style.theme_names():
            style.theme_use('clam')
        style.configure('.', font=('Segoe UI', 10))
        style.configure('Title.TLabel', font=('Segoe UI', 19, 'bold'))
        style.configure('Primary.TButton', font=('Segoe UI', 10, 'bold'), padding=7)

        main = ttk.Frame(root, padding=15)
        main.pack(fill='both', expand=True)
        ttk.Label(main, text='LEGO City Undercover', style='Title.TLabel').pack(anchor='w')
        ttk.Label(main, text='Archipelago verbinden  ·  Fortschritt beobachten  ·  Items lokal testen').pack(anchor='w', pady=(0, 10))
        connection = ttk.LabelFrame(main, text='Verbindung', padding=10)
        connection.pack(fill='x')
        for column, (caption, var, width) in enumerate((
            ('Server', self.address, 27), ('Port', self.port, 8),
            ('Slotname', self.name, 18), ('Passwort (optional)', self.password, 17)
        )):
            ttk.Label(connection, text=caption).grid(row=0, column=column, sticky='w', padx=(0, 8))
            ttk.Entry(connection, textvariable=var, width=width,
                      show='•' if var is self.password else '').grid(row=1, column=column, sticky='ew', padx=(0, 8))
            connection.columnconfigure(column, weight=0 if column == 1 else 1)
        self.connect_button = ttk.Button(connection, text='Verbinden', style='Primary.TButton', command=self.connect)
        self.connect_button.grid(row=1, column=4, padx=(3, 4))
        self.disconnect_button = ttk.Button(connection, text='Trennen', state='disabled', command=self.disconnect)
        self.disconnect_button.grid(row=1, column=5, padx=(3, 0))

        save_frame = ttk.Frame(connection)
        save_frame.grid(row=2, column=0, columnspan=6, sticky='ew', pady=(11, 2))
        ttk.Label(save_frame, text='Save-Datei (leer = automatisch):').pack(side='left')
        ttk.Entry(save_frame, textvariable=self.save_file).pack(side='left', fill='x', expand=True, padx=7)
        ttk.Button(save_frame, text='Durchsuchen …', command=self.browse_save).pack(side='left', padx=(0, 5))
        ttk.Button(save_frame, text='Auto', command=lambda: self.save_file.set('')).pack(side='left')

        switches = ttk.Frame(connection)
        switches.grid(row=3, column=0, columnspan=6, sticky='w', pady=(9, 0))
        ttk.Checkbutton(switches, text='Native Items und Save-Änderungen',
                        variable=self.use_native, command=self.update_buttons).pack(side='left', padx=(0, 20))
        ttk.Checkbutton(switches, text='Cutscene-Skip (nur bei aktiviertem Seed)',
                        variable=self.cutscene_skip).pack(side='left')
        ttk.Checkbutton(switches, text='Item-Popups im Spiel',
                        variable=self.show_popups,
                        command=lambda: self.commands.put(('popups_enabled',self.show_popups.get()))).pack(side='left', padx=15)

        status = ttk.LabelFrame(main, text='Live-Status', padding=9)
        status.pack(fill='x', pady=10)
        top = ttk.Frame(status)
        top.pack(fill='x')
        ttk.Label(top, textvariable=self.ap_status).pack(side='left')
        ttk.Label(top, textvariable=self.game_status).pack(side='right')
        bottom = ttk.Frame(status)
        bottom.pack(fill='x', pady=(5, 0))
        ttk.Label(bottom, textvariable=self.save_status).pack(side='left')
        ttk.Label(bottom, textvariable=self.progress).pack(side='right')
        ttk.Label(status,textvariable=self.area_status).pack(anchor='w',pady=(5,0))
        ttk.Button(status,text='Gebiet-Diagnose kopieren',command=self.copy_area_evidence).pack(anchor='e')
        ttk.Label(status,textvariable=self.pickup_binding_status).pack(anchor='w')
        ttk.Label(status,textvariable=self.seed_status).pack(anchor='w')
        ttk.Label(status,textvariable=self.pause_menu_status).pack(anchor='w')
        ttk.Button(status,text='Sammeldiagnose kopieren',command=self.copy_collectible_evidence).pack(anchor='e')

        panes = ttk.Panedwindow(main, orient='horizontal')
        panes.pack(fill='both', expand=True)
        test_pages=ttk.Notebook(panes)
        tests = ttk.Frame(test_pages,padding=10)
        rules=ttk.Frame(test_pages,padding=10)
        test_pages.add(tests,text='Item-Auswahl');test_pages.add(rules,text='Aktive Testregeln')
        logs = ttk.Notebook(panes)
        history_page=ttk.Frame(logs,padding=8)
        log_page=ttk.Frame(logs,padding=8)
        logs.add(history_page,text='Test-Historie');logs.add(log_page,text='Client-Log und Fehler')
        missions=ttk.Frame(logs,padding=8)
        logs.add(missions,text='Missionszugang')
        ttk.Label(missions,text='AP-Berechtigungen aus gespeicherten Receipts. Native Eintrittssperre noch nicht implementiert.',wraplength=700).pack(anchor='w',pady=(0,8))
        self.assignment_view=ttk.Treeview(missions,columns=('mission','policy','received','native'),show='headings',height=15)
        for key,label,width in (('mission','Mission',200),('policy','Verwaltung',120),('received','AP-Item',120),('native','Native Sperre',160)):
            self.assignment_view.heading(key,text=label);self.assignment_view.column(key,width=width)
        self.assignment_view.pack(fill='both',expand=True)
        filters=ttk.Frame(history_page);filters.pack(fill='x',pady=(0,8))
        ttk.Label(filters,text='Anforderung → Spiel-RAM → Save-Datei').pack(side='left')
        ttk.Button(filters,text='Historie exportieren',command=self.export_history).pack(side='right')
        columns=('time','action','item','ram','save','detail')
        self.history_view=ttk.Treeview(history_page,columns=columns,show='headings',selectmode='browse')
        for key,label,width in (('time','Zeit',75),('action','Aktion',65),('item','Item',270),('ram','Spiel-RAM',120),('save','Save-Datei',120),('detail','Details',250)):
            self.history_view.heading(key,text=label);self.history_view.column(key,width=width,minwidth=60,stretch=key in ('item','detail'))
        hscroll=ttk.Scrollbar(history_page,orient='horizontal',command=self.history_view.xview)
        vscroll=ttk.Scrollbar(history_page,orient='vertical',command=self.history_view.yview)
        self.history_view.configure(xscrollcommand=hscroll.set,yscrollcommand=vscroll.set)
        hscroll.pack(side='bottom',fill='x');vscroll.pack(side='right',fill='y');self.history_view.pack(fill='both',expand=True)
        self.history_view.tag_configure('saved',foreground='#187044');self.history_view.tag_configure('error',foreground='#ad3025')
        panes.add(test_pages, weight=2)
        panes.add(logs, weight=3)
        self.category_combo = ttk.Combobox(tests, textvariable=self.item_category, state='readonly',
            values=('Alle Item-Kategorien', 'Rote Steine / Cheats', 'Fähigkeiten', 'Charaktere', 'Fahrzeuge', 'Währungen'), height=7)
        self.category_combo.pack(fill='x', pady=(0, 6))
        self.item_category.trace_add('write', self.filter_items)
        self.combo = ttk.Combobox(tests, textvariable=self.item, values=self.names, state='normal')
        self.combo.pack(fill='x')
        self.combo.bind('<<ComboboxSelected>>',lambda _:self.show_item_info())
        self.item.trace_add('write', self.filter_items)
        search_options=ttk.Frame(tests);search_options.pack(fill='x',pady=(5,0))
        ttk.Checkbutton(search_options,text='Nur native Items',variable=self.only_supported,command=self.filter_items).pack(side='left')
        ttk.Checkbutton(search_options,text='Nur fehlende',variable=self.only_missing,command=self.filter_items).pack(side='left',padx=8)
        ttk.Button(search_options,text='Suche leeren',command=lambda:self.item.set('')).pack(side='right')
        ttk.Label(tests,textvariable=self.result_count).pack(anchor='w',pady=(4,0))
        results=ttk.Frame(tests);results.pack(fill='both',expand=True,pady=7)
        self.matches = tk.Listbox(results, height=10, exportselection=False, font=('Segoe UI', 10))
        rscroll=ttk.Scrollbar(results,command=self.matches.yview);self.matches.configure(yscrollcommand=rscroll.set)
        rscroll.pack(side='right',fill='y');self.matches.pack(fill='both',expand=True)
        self.matches.bind('<<ListboxSelect>>', self.select_item)
        ttk.Label(tests, textvariable=self.item_info, wraplength=320).pack(fill='x', pady=(0, 8))
        buttons = ttk.Frame(tests)
        buttons.pack(fill='x')
        self.give_button = ttk.Button(buttons, text='Geben', state='disabled', command=lambda: self.test_item('give'))
        self.give_button.pack(side='left', fill='x', expand=True, padx=(0, 5))
        self.remove_button = ttk.Button(buttons, text='Nehmen', state='disabled', command=lambda: self.test_item('remove'))
        self.remove_button.pack(side='left', fill='x', expand=True)
        self.reset_button = ttk.Button(tests, text='Testfreigaben auf AP-Zustand zurücksetzen',
                                       state='disabled', command=self.reset_tests)
        self.reset_button.pack(fill='x', pady=8)
        popup_buttons=ttk.LabelFrame(tests,text='HUD-Vorschau (ohne Item-Vergabe)',padding=5)
        popup_buttons.pack(fill='x',pady=(0,8))
        self.popup_buttons=[]
        for label,kind in (('Progression','progression'),('Useful','useful'),('Filler','filler')):
            button=ttk.Button(popup_buttons,text=label,state='disabled',
                command=lambda value=kind: self.commands.put(('popup',value)))
            button.pack(side='left',fill='x',expand=True)
            self.popup_buttons.append(button)
        ttk.Label(tests, wraplength=330, text=(
            'Achtung: Native Tests ändern deinen geladenen Spielstand. Autosaves können diese Änderungen '
            'dauerhaft speichern. Der Reset stellt AP-Freigaben wieder her, aber macht '
            'Währungstests nicht rückgängig. Benutze einen gesicherten Test-Slot!'
        )).pack(fill='x', pady=(0, 8))
        ttk.Label(rules, text='Gewünschte Testfreigaben und Prüfergebnisse').pack(anchor='w')
        self.overrides = tk.Listbox(rules, height=5, font=('Segoe UI', 9))
        self.overrides.pack(fill='both', expand=True, pady=(4, 0))
        log_frame = ttk.Frame(log_page)
        log_frame.pack(fill='both', expand=True)
        self.log = tk.Text(log_frame, wrap='word', state='disabled', font=('Consolas', 9),
                           bg='#12202e', fg='#e5edf5', insertbackground='white')
        scroller = ttk.Scrollbar(log_frame, command=self.log.yview)
        self.log.configure(yscrollcommand=scroller.set)
        scroller.pack(side='right', fill='y')
        self.log.pack(fill='both', expand=True)
        self.log.tag_configure('error', foreground='#ff9b91')
        self.log.tag_configure('warning', foreground='#ffd28a')
        bottom_buttons = ttk.Frame(main)
        bottom_buttons.pack(fill='x', pady=(8, 0))
        ttk.Button(bottom_buttons, text='Log kopieren', command=self.copy_log).pack(side='right')
        ttk.Button(bottom_buttons, text='Log leeren', command=self.clear_log).pack(side='right', padx=8)
        try:
            previous=json.loads(self.history_path.read_text(encoding='utf-8'))
            if isinstance(previous,list):self.history_rows=[row for row in previous if isinstance(row,dict) and 'ui_id' in row][-1000:]
            self.update_history([])
        except (OSError,ValueError,KeyError,TypeError):pass
        self.filter_items()
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.after(100, self.pump)

    def browse_save(self):
        selected = filedialog.askopenfilename(parent=self.root, title='LCU-Spielstand wählen',
            filetypes=[('LEGO City Undercover Save', '*' + SAVE_SUFFIX), ('Alle Dateien', '*.*')])
        if selected:
            self.save_file.set(selected)

    def filter_items(self, *_):
        if self._selecting or (self.item.get() in self.effects and _ and _[0]==str(self.item)):
            self.show_item_info();return
        query = '' if self.item.get() in self.effects else normalize_search(self.item.get().strip())
        query={'detektivscan':'detective scan','kriminellenscan':'scanner','personenscan':'scanner'}.get(query,query)
        query={'polizei':'police','polizist':'police','minenarbeiter':'miner','r?uber':'robber','feuerwehr':'firefighter','bauarbeiter':'construction'}.get(query,query)
        if query in ('red bricks', 'redbrick', 'rote steine', 'rotsteine', 'rote steinchen'):
            query = 'red brick'
        selected = self.item_category.get()
        def category_matches(name):
            item = self.effects[name]
            kind = item.get('category')
            if selected == 'Rote Steine / Cheats': return kind == 'cheat'
            if selected == 'Fähigkeiten': return kind == 'ability'
            if selected == 'Charaktere': return kind == 'character'
            if selected == 'Fahrzeuge': return kind == 'vehicle'
            if selected == 'Währungen': return item.get('effect') in ('add_studs', 'add_bricks')
            return True
        values = [name for name in self.names if all(word in normalize_search(name) for word in query.split()) and category_matches(name)
                  and (not self.only_supported.get() or supported(self.effects[name]))
                  and (not self.only_missing.get() or self.item_states.get(name,{}).get('owned') is False)]
        self.combo.configure(values=values)
        self.result_count.set(f'{len(values)} von {len(self.names)} Items ? Auswahl bleibt beim Anklicken erhalten')
        self.matches.delete(0, 'end')
        for name in values:
            self.matches.insert('end', name)
        effect = self.effects.get(self.item.get())
        if effect:
            info = 'Native Test-Anbindung vorhanden.' if supported(effect) else 'Noch keine native Test-Anbindung.'
            if effect.get('category') == 'cheat':
                info += ' Freischalten ist nicht gleich sichtbar aktivieren; ggf. Extras im Spiel prüfen.'
            if self.item.get() in ('Ability: Police', 'Character: COP'):
                info += ' Police wird freigeschaltet, nicht automatisch angezogen.'
        else:
            info = f'{len(values)} passende Items' + (' (Liste auf 250 begrenzt)' if len(values) > 250 else '')
            if selected == 'Rote Steine / Cheats':
                info += ' · Das sind Cheat-Freischaltungen, keine Fundort-Checks.'
        self.item_info.set(info)
        self.update_buttons()

    def select_item(self, _):
        indices = self.matches.curselection()
        if indices:
            self._selecting=True
            try:self.item.set(self.matches.get(indices[0]))
            finally:self._selecting=False
            self.show_item_info()

    def show_item_info(self):
        name=self.item.get();effect=self.effects.get(name)
        if effect is None:return
        state=self.item_states.get(name,{})
        flag=lambda value:'Ja' if value is True else 'Nein' if value is False else 'Noch nicht gelesen'
        lines=[name,'Native Anbindung: '+('Verfügbar' if supported(effect) else 'Nicht implementiert'),
               'Freigeschaltet im Spiel: '+flag(state.get('owned')),
               'Freigeschaltet im Save: '+flag(state.get('saved'))]
        if name=='Ability: Detective Scan':
            lines[-1]='Persistenz: AP-Empfangsjournal; kein natives Save-Flag'
            lines.append('Nach Geben die Detektiv-Aura einmal verlassen und erneut betreten.')
        if name=='Ability: Criminal Scan':
            lines.append('Kriminellen-/Personenscan an Scanpunkten; benötigt Police Stufe 1.')
            lines.append('Interner Spielname: Scanner. Kein Detektivscan und kein DataScanner.')
        if state.get('index') is not None:lines.append('Native ID: '+str(state['index']))
        if state.get('found') is not None:lines.append('Originalfund registriert: '+flag(state['found']))
        if state.get('saved_found') is not None:lines.append('Originalfund im Save: '+flag(state['saved_found']))
        if state.get('pending') is not None:lines.append('Native Freigabe ausstehend: '+flag(state['pending']))
        if state.get('active') is not None:lines.append('Cheat im Extras-Menü aktiv: '+flag(state['active']))
        if effect.get('test_only'):lines.append('Zusätzliches natives Testmodell, kein AP-Pool-Item.')
        self.item_info.set('\n'.join(lines));self.update_buttons()

    def update_history(self,rows):
        stored={row['ui_id']:row for row in self.history_rows}
        for row in rows:
            row=dict(row,ui_id=self.history_session+':'+str(row['id']))
            row['item']=ITEM_ALIASES.get(row.get('item'),row.get('item',''))
            stored[row['ui_id']]=row
        self.history_rows=list(stored.values())[-1000:]
        visible={row['ui_id'] for row in self.history_rows}
        for ident in self.history_view.get_children():
            if ident not in visible:self.history_view.delete(ident)
        for row in self.history_rows:
            ident=row['ui_id'];values=tuple(row.get(key,'') for key in ('time','action','item','ram','save','detail'))
            tags=('error',) if 'Fehler' in row.get('ram','') else ('saved',) if row.get('save')=='Bestätigt' else ()
            if self.history_view.exists(ident):self.history_view.item(ident,values=values,tags=tags)
            else:self.history_view.insert('',0,iid=ident,values=values,tags=tags)
        try:
            self.history_path.parent.mkdir(parents=True,exist_ok=True)
            temporary=self.history_path.with_suffix('.tmp')
            temporary.write_text(json.dumps(self.history_rows,ensure_ascii=False,indent=2),encoding='utf-8');temporary.replace(self.history_path)
        except OSError as error:self.append_log('WARNING: Historie konnte nicht gespeichert werden: '+str(error))

    def export_history(self):
        path=filedialog.asksaveasfilename(parent=self.root,title='Test-Historie exportieren',defaultextension='.json',filetypes=[('JSON','*.json')])
        if path:
            try:Path(path).write_text(json.dumps(dict(format='LCU local test history',version=1,operations=self.history_rows),indent=2,ensure_ascii=False),encoding='utf-8')
            except OSError as error:self.append_log('ERROR: Historie konnte nicht exportiert werden: '+str(error))

    def update_buttons(self):
        running = bool(self.worker and self.worker.is_alive() and not self.stopping)
        ready = (running and self.use_native.get() and self.ap_connected and
                 self.game_connected and self.native_ready)
        effect = self.effects.get(self.item.get())
        allowed = ready and effect is not None and supported(effect)
        self.give_button.configure(state='normal' if allowed else 'disabled')
        locked_start = bool(effect and effect.get('native_name') in
                            ('CIVILIAN_CHASEMCCAIN', 'CIVILIAN_CHASEMCCAIN_ALT'))
        self.remove_button.configure(state='normal' if allowed and not locked_start else 'disabled')
        self.reset_button.configure(state='normal' if ready else 'disabled')
        for button in self.popup_buttons:
            button.configure(state='normal' if running and self.use_native.get() and
                             self.ap_connected and self.game_connected else 'disabled')

    def append_log(self, line: str):
        self.log.configure(state='normal')
        tag = 'error' if 'ERROR' in line or 'Traceback' in line else ('warning' if 'WARNING' in line else '')
        self.log.insert('end', line + '\n', tag)
        if int(self.log.index('end-1c').split('.')[0]) > 4000:
            self.log.delete('1.0', '1000.0')
        self.log.see('end')
        self.log.configure(state='disabled')

    def clear_log(self):
        self.log.configure(state='normal')
        self.log.delete('1.0', 'end')
        self.log.configure(state='disabled')

    def connect(self):
        if self.closing or self.stopping or (self.worker and self.worker.is_alive()):
            return
        try:
            server = connection_address(self.address.get(), self.port.get())
            slot = self.name.get().strip()
            if not slot:
                raise ValueError('Bitte den Slotnamen aus dem Archipelago-Raum eingeben.')
            save = validate_start(self.use_native.get(), self.save_file.get().strip())
            if self.use_native.get():
                problem = bridge_health(ROOT)
                if problem:
                    raise ValueError(problem)
        except (ValueError, TypeError, OSError) as error:
            self.append_log('ERROR: ' + str(error))
            return
        try:
            self.settings_path.parent.mkdir(parents=True, exist_ok=True)
            self.settings_path.write_text(json.dumps(dict(
                address=self.address.get(), port=self.port.get(), name=slot,
                save_file=str(save) if save else '', native=self.use_native.get(),
                cutscene_skip=self.cutscene_skip.get()), indent=2), encoding='utf-8')
        except OSError as error:
            self.append_log('WARNING: Einstellungen konnten nicht gespeichert werden: ' + str(error))

        self.commands = queue.Queue()
        self.history_session=datetime.now().isoformat(timespec='microseconds')
        self.ap_connected = self.game_connected = self.native_ready = False
        self.tests_confirmed = False
        self.stopping = False
        password = self.password.get()
        args = argparse.Namespace(connect=server, name=slot, password=password,
            native_save_file=save, enable_cutscene_skip=self.cutscene_skip.get(),
            disable_item_popups=not self.show_popups.get(),
            enable_native_models=self.use_native.get(), ui_controls=self.commands, ui_events=self.events)

        def worker():
            handler = EventLogHandler(self.events, password)
            handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s', datefmt='%H:%M:%S'))
            logger = logging.getLogger()
            old_level = logger.level
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
            try:
                os.environ.setdefault('SKIP_REQUIREMENTS_UPDATE', '1')
                spec = importlib.util.spec_from_file_location('lcu_gui_client', WORLD / 'Client.py')
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                asyncio.run(module.main(args))
            except Exception:
                logging.exception('Client konnte nicht gestartet werden')
            finally:
                logger.removeHandler(handler)
                logger.setLevel(old_level)
                self.events.put(('stopped', None))

        self.ap_status.set('Archipelago: Verbindung wird hergestellt …')
        self.game_status.set('Spiel: Suche läuft …')
        self.save_status.set('Save: Nicht gebunden')
        self.progress.set('Checks: 0 · AP-Items: 0')
        self.connect_button.configure(state='disabled')
        self.disconnect_button.configure(state='normal')
        self.worker = threading.Thread(target=worker, name='LCU-AP-Client', daemon=True)
        self.worker.start()
        self.update_buttons()

    def disconnect(self):
        if self.stopping or not self.worker or not self.worker.is_alive():
            return
        self.stopping = True
        self.commands.put(('disconnect', None))
        self.ap_status.set('Archipelago: Wird beendet …')
        self.disconnect_button.configure(state='disabled')
        self.update_buttons()

    def test_item(self, action):
        button = self.give_button if action == 'give' else self.remove_button
        if action not in ('give', 'remove') or button.instate(['disabled']) or not self.native_ready:
            return
        name = self.item.get()
        effect = self.effects.get(name)
        if effect is None or not supported(effect):
            return
        if not self.tests_confirmed:
            accepted = messagebox.askyesno('Native Teständerungen',
                'Native Tests verändern das laufende Spiel und können in deinem Save landen.\n'
                'Test-Währungen lassen sich nicht automatisch zurücksetzen.\n\n'
                'Hast du einen gesicherten Test-Spielstand und möchtest fortfahren?', parent=self.root)
            if not accepted:
                return
            self.tests_confirmed = True
        self.commands.put((action, name))
        self.append_log(f'INFO: Lokaler Test angefordert: {action} · {name} (noch NICHT bestätigt)')

    def reset_tests(self):
        if self.reset_button.instate(['disabled']):
            return
        self.commands.put(('reset', None))
        self.append_log('INFO: Testfreigaben auf AP-Zustand zurücksetzen angefordert.')

    def copy_log(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(self.log.get('1.0', 'end-1c'))

    def close(self):
        if self.closing:
            return
        self.closing = True
        if self.worker and self.worker.is_alive():
            self.disconnect()
            # Keep polling until the worker reports 'stopped'. Never destroy Tk
            # while a worker could still be queueing UI events.
        else:
            self.root.destroy()

    def copy_area_evidence(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(json.dumps(self.area_evidence,indent=2,ensure_ascii=False))

    def copy_collectible_evidence(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(json.dumps(self.collectible_evidence,indent=2,ensure_ascii=False))
        self.append_log('Gebietsdiagnose kopiert (begrenzte Ereignishistorie; keine Save-Datei).')

    def pump(self):
        for _ in range(300):
            try:
                kind, value = self.events.get_nowait()
            except queue.Empty:
                break
            if kind == 'log':
                self.append_log(value)
            elif kind == 'ap':
                self.ap_status.set(value)
            elif kind == 'connection':
                self.ap_connected = bool(value)
            elif kind == 'game':
                self.game_status.set(value)
            elif kind == 'area_gate':
                labels={'waiting_for_save_backup':'warte auf Save-Zuordnung und Backup',
                    'disembark_requested':'Ausstieg angefordert; warte auf freie Spielfigur',
                    'locked_area_without_foot_checkpoint':'kein erlaubter Fußgänger-Checkpoint; erst dort zu Fuß stehen',
                    'disembark_not_observed':'Ausstieg nicht bestätigt; manuell aussteigen und Gebiet-Diagnose kopieren',
                    'checkpoint_recorded':'Rückkehrpunkt gespeichert','allowed':'Gebiet freigeschaltet',
                    'locked_area_without_checkpoint':'gesperrtes Gebiet, aber kein sicherer Rückkehrpunkt',
                    'checkpoint_unavailable':'Rückkehrpunkt nicht verifiziert; Diagnose prüfen',
                    'return_requested':'Rücksetzung angefordert; Positionsbeobachtung ausstehend',
                    'return_waiting_for_observation':'warte auf Positionsbeobachtung; keine erneute Teleportation',
                    'return_uncertain':'Rücksetzung unklar; automatische Wiederholung gestoppt',
                    'return_rejected_safe':'Rücksetzung sicher abgelehnt; keine automatische Wiederholung',
                    'deferred_scene_or_context':'ruht während Szene oder Interaktion','deferred_player_busy':'Spieler beschäftigt'}
                self.area_status.set('Gebietssperre (experimentell): '+labels.get(value,str(value)))
            elif kind == 'area_evidence':
                self.area_evidence=value
            elif kind == 'pickup_binding_status':
                self.pickup_binding_status.set(f"Supersteine: {value['verified']} genaue Zuordnungen · {value['blocked']} gesperrte Bit-Konflikte")
            elif kind == 'seed':
                self.seed_status.set('Seed: '+value)
                self.assignment_view.delete(*self.assignment_view.get_children())
            elif kind == 'assignment_policy':
                self.assignment_view.delete(*self.assignment_view.get_children())
                for row in value['entries']:
                    self.assignment_view.insert('','end',values=(row['assignment'],
                        'Archipelago' if row['managed'] else 'Vanilla',
                        'Empfangen' if row['received'] else 'Nicht empfangen',
                        'Nicht implementiert'))
            elif kind == 'collectible_evidence':
                self.collectible_evidence=value
            elif kind == 'game_loaded':
                self.game_connected = bool(value)
                if not self.game_connected:
                    self.pause_menu_status.set('Pausemenü: warte auf geladenes Spiel')
            elif kind == 'save':
                self.save_status.set(value)
            elif kind == 'pause_menu':
                self.pause_menu_status.set(value)
            elif kind == 'ready':
                self.native_ready = bool(value)
            elif kind == 'progress':
                self.progress.set(value)
            elif kind == 'overrides':
                self.overrides.delete(0, 'end')
                for row in value:
                    self.overrides.insert('end', row)
            elif kind=='history':self.update_history(value)
            elif kind=='item_states':
                self.item_states=value;self.show_item_info()
            elif kind == 'stopped':
                self.assignment_view.delete(*self.assignment_view.get_children())
                self.area_status.set('Gebietssperre: nicht aktiv (Client gestoppt)')
                self.worker = None
                self.stopping = False
                self.ap_connected = self.game_connected = self.native_ready = False
                self.ap_status.set('Archipelago: Nicht verbunden')
                self.game_status.set('Spiel: Nicht geladen')
                self.save_status.set('Save: Nicht gebunden')
                self.pause_menu_status.set('Pausemenü: Client getrennt · Installation nicht geprüft')
                self.connect_button.configure(state='normal')
                self.disconnect_button.configure(state='disabled')
                self.update_buttons()
                if self.closing:
                    self.root.destroy()
                    return
        self.update_buttons()
        self.root.after(100, self.pump)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--connect')
    parser.add_argument('--name')
    parser.add_argument('--native-save-file', type=Path)
    args = parser.parse_args(argv)
    root = tk.Tk()
    try:
        App(root, args)
        root.mainloop()
    except Exception as error:
        messagebox.showerror('LCU Client konnte nicht starten', str(error), parent=root)
        root.destroy()


if __name__ == '__main__':
    main()
