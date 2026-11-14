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
from tkinter import filedialog, messagebox, ttk
from urllib.parse import urlsplit

WORLD = Path(__file__).resolve().parents[1]
ROOT = WORLD.parents[1]
SETTINGS = ROOT / 'build/lego_city_undercover/native_client_ui.json'
SAVE_SUFFIX = '.legocityundercoversavegamedata'
sys.path.insert(0, str(WORLD / 'bridge'))
from native_bridge_path import bridge_path
from test_overrides import supported


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
        self.ap_status = tk.StringVar(value='Archipelago: Nicht verbunden')
        self.game_status = tk.StringVar(value='Spiel: Nicht geladen')
        self.save_status = tk.StringVar(value='Save: Nicht gebunden')
        self.progress = tk.StringVar(value='Checks: 0 · AP-Items: 0')
        self.item_info = tk.StringVar(value='Item suchen oder auswählen.')

        catalogue = json.loads((WORLD / 'catalogue.json').read_text(encoding='utf-8'))
        self.effects = {name: dict(row, name=name) for name, row in catalogue['items'].items()}
        self.names = sorted(self.effects, key=str.casefold)

        root.title('LEGO City Undercover | Archipelago Client')
        root.geometry('1160x790')
        root.minsize(910, 620)
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

        panes = ttk.Panedwindow(main, orient='horizontal')
        panes.pack(fill='both', expand=True)
        tests = ttk.LabelFrame(panes, text='Lokale Item-Tests (keine AP-Items!)', padding=10)
        logs = ttk.LabelFrame(panes, text='Client-Log und Fehler', padding=8)
        panes.add(tests, weight=2)
        panes.add(logs, weight=3)
        self.combo = ttk.Combobox(tests, textvariable=self.item, values=self.names, state='normal')
        self.combo.pack(fill='x')
        self.item.trace_add('write', self.filter_items)
        self.matches = tk.Listbox(tests, height=8, exportselection=False, font=('Segoe UI', 10))
        self.matches.pack(fill='x', pady=7)
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
        ttk.Label(tests, wraplength=330, text=(
            'Achtung: Native Tests ändern deinen geladenen Spielstand. Autosaves können diese Änderungen '
            'dauerhaft speichern. Der Reset stellt AP-Freigaben wieder her, aber macht '
            'Währungstests nicht rückgängig. Benutze einen gesicherten Test-Slot!'
        )).pack(fill='x', pady=(0, 8))
        ttk.Label(tests, text='Aktive Testregeln').pack(anchor='w')
        self.overrides = tk.Listbox(tests, height=5, font=('Segoe UI', 9))
        self.overrides.pack(fill='both', expand=True, pady=(4, 0))
        log_frame = ttk.Frame(logs)
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
        self.filter_items()
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.after(100, self.pump)

    def browse_save(self):
        selected = filedialog.askopenfilename(parent=self.root, title='LCU-Spielstand wählen',
            filetypes=[('LEGO City Undercover Save', '*' + SAVE_SUFFIX), ('Alle Dateien', '*.*')])
        if selected:
            self.save_file.set(selected)

    def filter_items(self, *_):
        query = self.item.get().casefold()
        values = [name for name in self.names if query in name.casefold()]
        self.combo.configure(values=values[:400])
        self.matches.delete(0, 'end')
        for name in values[:250]:
            self.matches.insert('end', name)
        effect = self.effects.get(self.item.get())
        if effect:
            info = 'Native Test-Anbindung vorhanden.' if supported(effect) else 'Noch keine native Test-Anbindung.'
        else:
            info = f'{len(values)} passende Items' + (' (Liste auf 250 begrenzt)' if len(values) > 250 else '')
        self.item_info.set(info)
        self.update_buttons()

    def select_item(self, _):
        indices = self.matches.curselection()
        if indices:
            self.item.set(self.matches.get(indices[0]))

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
        self.ap_connected = self.game_connected = self.native_ready = False
        self.tests_confirmed = False
        self.stopping = False
        password = self.password.get()
        args = argparse.Namespace(connect=server, name=slot, password=password,
            native_save_file=save, enable_cutscene_skip=self.cutscene_skip.get(),
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
        self.append_log(f'INFO: Lokaler Test angefordert: {action} · {name}')

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
            elif kind == 'game_loaded':
                self.game_connected = bool(value)
            elif kind == 'save':
                self.save_status.set(value)
            elif kind == 'ready':
                self.native_ready = bool(value)
            elif kind == 'progress':
                self.progress.set(value)
            elif kind == 'overrides':
                self.overrides.delete(0, 'end')
                for row in value:
                    self.overrides.insert('end', row)
            elif kind == 'stopped':
                self.worker = None
                self.stopping = False
                self.ap_connected = self.game_connected = self.native_ready = False
                self.ap_status.set('Archipelago: Nicht verbunden')
                self.game_status.set('Spiel: Nicht geladen')
                self.save_status.set('Save: Nicht gebunden')
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
