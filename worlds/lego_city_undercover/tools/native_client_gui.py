"""Native LCU client connection window and local item-test controls."""
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
from tkinter import ttk,messagebox
from urllib.parse import urlsplit

WORLD=Path(__file__).resolve().parents[1]
ROOT=WORLD.parents[1]
sys.path.insert(0,str(WORLD/'bridge'))
from test_overrides import supported


def connection_address(address,port):
    address=address.strip();port=int(port)
    if not 1<=port<=65535:raise ValueError('Port muss zwischen 1 und 65535 liegen.')
    parsed=urlsplit(address if '://' in address else '//'+address)
    if not parsed.hostname or parsed.username or parsed.password or parsed.path not in ('','/') or parsed.query or parsed.fragment:
        raise ValueError('Bitte nur eine Server-Adresse eingeben, ohne Pfad oder Zugangsdaten.')
    if parsed.scheme and parsed.scheme not in ('ws','wss'):raise ValueError('Unterstützt werden ws:// und wss://.')
    host=parsed.hostname
    if ':' in host:host='['+host+']'
    return (parsed.scheme+'://' if parsed.scheme else '')+host+':'+str(port)


class LogQueue(logging.Handler):
    def __init__(self,events,secret):super().__init__();self.events=events;self.secret=secret
    def emit(self,record):
        text=self.format(record)
        if self.secret:text=text.replace(self.secret,'[Passwort]')
        self.events.put(('log',text))


class App:
    def __init__(self,root,args):
        self.root=root;self.args=args;self.events=queue.Queue();self.commands=queue.Queue();self.thread=None;self.closing=False
        self.settings=ROOT/'build/lego_city_undercover/native_client_ui.json'
        defaults={'address':'archipelago.gg','port':'58404','name':'Luma'}
        try:defaults.update(json.loads(self.settings.read_text()))
        except (OSError,ValueError):pass
        if args.connect:
            parsed=urlsplit(args.connect if '://' in args.connect else '//'+args.connect)
            defaults['address']=parsed.hostname or args.connect
            if parsed.scheme:defaults['address']=parsed.scheme+'://'+defaults['address']
            if parsed.port:defaults['port']=str(parsed.port)
        if args.name:defaults['name']=args.name
        self.address=tk.StringVar(value=defaults['address']);self.port=tk.StringVar(value=defaults['port'])
        self.name=tk.StringVar(value=defaults['name']);self.password=tk.StringVar();self.item=tk.StringVar()
        self.ap=tk.StringVar(value='AP nicht verbunden');self.game=tk.StringVar(value='Spiel noch nicht verbunden')
        self.item_info=tk.StringVar(value='Item eintippen oder aus der Liste wählen.')
        catalogue=json.loads((WORLD/'catalogue.json').read_text())
        self.effects={name:dict(row,name=name) for name,row in catalogue['items'].items()}
        self.names=sorted(self.effects,key=str.casefold)
        root.title('LEGO City Undercover · Archipelago Client');root.geometry('1120x800');root.minsize(900,640)
        style=ttk.Style();style.theme_use('clam')
        style.configure('.',font=('Segoe UI',10));style.configure('Title.TLabel',font=('Segoe UI',19,'bold'))
        style.configure('Accent.TButton',font=('Segoe UI',10,'bold'),padding=8)
        container=ttk.Frame(root,padding=18);container.pack(fill='both',expand=True)
        ttk.Label(container,text='LEGO City Undercover',style='Title.TLabel').pack(anchor='w')
        ttk.Label(container,text='Archipelago verbinden · Spiel beobachten · Items testen').pack(anchor='w',pady=(0,14))
        form=ttk.LabelFrame(container,text='Verbindung',padding=12);form.pack(fill='x')
        for col,(label,var,width) in enumerate((('Adresse',self.address,28),('Port',self.port,8),('Slotname',self.name,19),('Passwort',self.password,19))):
            ttk.Label(form,text=label).grid(row=0,column=col,sticky='w',padx=(0,10))
            ttk.Entry(form,textvariable=var,width=width,show='•' if var is self.password else '').grid(row=1,column=col,sticky='ew',padx=(0,10),pady=(4,0))
            form.columnconfigure(col,weight=0 if col==1 else 1)
        self.connect_button=ttk.Button(form,text='Verbinden',style='Accent.TButton',command=self.connect)
        self.connect_button.grid(row=1,column=4,padx=4)
        self.disconnect_button=ttk.Button(form,text='Trennen',command=self.disconnect,state='disabled');self.disconnect_button.grid(row=1,column=5,padx=4)
        status=ttk.Frame(container);status.pack(fill='x',pady=10)
        ttk.Label(status,textvariable=self.ap).pack(side='left');ttk.Label(status,textvariable=self.game).pack(side='right')
        panes=ttk.Panedwindow(container,orient='horizontal');panes.pack(fill='both',expand=True)
        tests=ttk.LabelFrame(panes,text='Lokale Item-Tests',padding=12);logs=ttk.LabelFrame(panes,text='Client-Log und Fehler',padding=8)
        panes.add(tests,weight=2);panes.add(logs,weight=3)
        self.combo=ttk.Combobox(tests,textvariable=self.item,values=self.names,state='normal');self.combo.pack(fill='x')
        self.item.trace_add('write',self.filter_items)
        self.matches=tk.Listbox(tests,height=8,exportselection=False,font=('Segoe UI',10));self.matches.pack(fill='both',expand=False,pady=8)
        self.matches.bind('<<ListboxSelect>>',self.select_item)
        ttk.Label(tests,textvariable=self.item_info,wraplength=350).pack(fill='x',pady=(0,10))
        buttons=ttk.Frame(tests);buttons.pack(fill='x')
        self.give_button=ttk.Button(buttons,text='Geben',command=lambda:self.test('give'),state='disabled');self.give_button.pack(side='left',fill='x',expand=True,padx=(0,5))
        self.remove_button=ttk.Button(buttons,text='Nehmen',command=lambda:self.test('remove'),state='disabled');self.remove_button.pack(side='left',fill='x',expand=True)
        self.reset_button=ttk.Button(tests,text='Testfreigaben auf AP-Zustand zurücksetzen',command=lambda:self.commands.put(('reset',None)),state='disabled')
        self.reset_button.pack(fill='x',pady=8)
        ttk.Label(tests,text='Ändert das Spiel, keine AP-Empfangsliste. Bitte zu Fuß stehen bleiben. Autosaves können Teständerungen speichern. Währungsbuchungen werden beim Zurücksetzen nicht rückgängig gemacht.',wraplength=350).pack(fill='x',pady=8)
        ttk.Label(tests,text='Aktive Testregeln').pack(anchor='w')
        self.overrides=tk.Listbox(tests,height=6,font=('Segoe UI',9));self.overrides.pack(fill='both',expand=True,pady=(5,0))
        self.log=tk.Text(logs,wrap='word',state='disabled',font=('Consolas',9),bg='#12202e',fg='#e5edf5',insertbackground='white')
        scrollbar=ttk.Scrollbar(logs,command=self.log.yview);self.log.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right',fill='y');self.log.pack(fill='both',expand=True)
        self.log.tag_configure('error',foreground='#ff9b91');self.log.tag_configure('warning',foreground='#ffd28a')
        ttk.Button(container,text='Log kopieren',command=self.copy_log).pack(anchor='e',pady=(10,0))
        self.filter_items();root.protocol('WM_DELETE_WINDOW',self.close);root.after(100,self.pump)

    def filter_items(self,*_):
        text=self.item.get().casefold();values=[name for name in self.names if text in name.casefold()]
        self.combo.configure(values=values);self.matches.delete(0,'end')
        for value in values:self.matches.insert('end',value)
        effect=self.effects.get(self.item.get())
        self.item_info.set(('Native Test-Anbindung verfügbar.' if supported(effect) else 'Noch keine native Anbindung – Geben/Nehmen nicht verfügbar.') if effect else f'{len(values)} passende Items')
        self.update_buttons()

    def select_item(self,event):
        selection=self.matches.curselection()
        if selection:self.item.set(self.matches.get(selection[0]))

    def update_buttons(self):
        live=bool(self.thread and self.thread.is_alive())
        enabled=live and self.item.get() in self.effects and supported(self.effects[self.item.get()])
        for button in (self.give_button,self.remove_button):button.configure(state='normal' if enabled else 'disabled')
        self.reset_button.configure(state='normal' if live else 'disabled')

    def append_log(self,text):
        self.log.configure(state='normal');tag='error' if 'ERROR' in text or 'Traceback' in text else 'warning' if 'WARNING' in text else ''
        self.log.insert('end',text+'\n',tag)
        if int(self.log.index('end-1c').split('.')[0])>6000:self.log.delete('1.0','1000.0')
        self.log.see('end');self.log.configure(state='disabled')

    def connect(self):
        try:
            server=connection_address(self.address.get(),self.port.get());name=self.name.get().strip()
            if not name:raise ValueError('Bitte einen Slotnamen eingeben.')
        except (ValueError,TypeError) as error:self.append_log('ERROR: '+str(error));return
        self.commands=queue.Queue();secret=self.password.get()
        try:
            self.settings.parent.mkdir(parents=True,exist_ok=True)
            self.settings.write_text(json.dumps(dict(address=self.address.get(),port=self.port.get(),name=name)))
        except OSError as error:self.append_log('ERROR: Verbindungseinstellungen konnten nicht gespeichert werden: '+str(error));return
        args=argparse.Namespace(connect=server,name=name,password=secret,native_save_file=self.args.native_save_file,
            enable_cutscene_skip=True,enable_native_models=True,ui_controls=self.commands,ui_events=self.events)
        def run():
            handler=LogQueue(self.events,secret);handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s',datefmt='%H:%M:%S'))
            logger=logging.getLogger();logger.addHandler(handler);logger.setLevel(logging.INFO)
            try:
                os.environ.setdefault('SKIP_REQUIREMENTS_UPDATE','1')
                spec=importlib.util.spec_from_file_location('lcu_gui_client',WORLD/'Client.py')
                module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
                asyncio.run(module.main(args))
            except Exception:logging.exception('Client konnte nicht gestartet werden')
            finally:logger.removeHandler(handler);self.events.put(('stopped',None))
        self.connect_button.configure(state='disabled');self.disconnect_button.configure(state='normal')
        self.thread=threading.Thread(target=run,daemon=True);self.thread.start();self.update_buttons()

    def disconnect(self):
        if self.thread and self.thread.is_alive():self.commands.put(('disconnect',None));self.ap.set('Verbindung wird beendet …')

    def test(self,action):self.commands.put((action,self.item.get()))

    def copy_log(self):
        self.root.clipboard_clear();self.root.clipboard_append(self.log.get('1.0','end-1c'))

    def close(self):
        self.closing=True
        if self.thread and self.thread.is_alive():self.disconnect()
        else:self.root.destroy()

    def pump(self):
        for _ in range(300):
            try:kind,value=self.events.get_nowait()
            except queue.Empty:break
            if kind=='log':self.append_log(value)
            elif kind=='ap':self.ap.set(value)
            elif kind=='game':self.game.set(value)
            elif kind=='overrides':
                self.overrides.delete(0,'end')
                for row in value:self.overrides.insert('end',row)
            elif kind=='stopped':
                self.thread=None;self.ap.set('AP nicht verbunden');self.game.set('Spiel noch nicht verbunden')
                self.connect_button.configure(state='normal');self.disconnect_button.configure(state='disabled');self.update_buttons()
                if self.closing:self.root.destroy();return
        self.root.after(100,self.pump)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--connect');parser.add_argument('--name');parser.add_argument('--native-save-file',type=Path)
    root=tk.Tk()
    try:app=App(root,parser.parse_args());root.mainloop()
    except Exception as error:messagebox.showerror('LCU Client konnte nicht starten',str(error),parent=root);root.destroy()
