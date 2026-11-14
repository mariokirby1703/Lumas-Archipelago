"""Durable AP transport state. Receipts never imply a native game grant."""
import hashlib
import json
import sqlite3
import logging
from pathlib import Path
from delivery_marker import binding_token


class Journal:
    def __init__(self, directory, binding):
        directory.mkdir(parents=True, exist_ok=True)
        self.directory=directory
        encoded=json.dumps(binding, sort_keys=True, separators=(',', ':'))
        self.binding_token=binding_token(binding)
        key=hashlib.sha256(encoded.encode()).hexdigest()
        self.db=sqlite3.connect(directory / (key+'.sqlite3'))
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS outgoing (location INTEGER PRIMARY KEY, acknowledged INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS receipts (server_index INTEGER PRIMARY KEY, payload TEXT NOT NULL,
                native_state TEXT NOT NULL DEFAULT 'not_applied');
            CREATE TABLE IF NOT EXISTS deliveries (server_index INTEGER PRIMARY KEY REFERENCES receipts(server_index),
                plan TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'waiting_native_backend', evidence TEXT);
        ''')
        with self.db:
            self.db.execute('INSERT OR IGNORE INTO metadata VALUES (?,?)', ('binding',encoded))
            self.db.execute('INSERT OR IGNORE INTO metadata VALUES (?,?)', ('native_save_identity','unverified'))

    def queue(self, locations):
        with self.db:
            self.db.executemany('INSERT OR IGNORE INTO outgoing(location) VALUES (?)', ((int(x),) for x in locations))

    def acknowledge(self, locations):
        with self.db:
            self.db.executemany('UPDATE outgoing SET acknowledged=1 WHERE location=?', ((int(x),) for x in locations))

    def pending(self):
        return [r[0] for r in self.db.execute('SELECT location FROM outgoing WHERE acknowledged=0 ORDER BY location')]

    def receipt(self, index, item):
        payload=json.dumps(dict(item=item.item,location=item.location,player=item.player),sort_keys=True)
        existing=self.db.execute('SELECT payload FROM receipts WHERE server_index=?',(index,)).fetchone()
        if existing and existing[0]!=payload:
            raise ValueError('Server item index changed within the same journal binding')
        if not existing:
            with self.db:
                self.db.execute('INSERT INTO receipts(server_index,payload) VALUES (?,?)',(index,payload))

    def close(self):
        self.db.close()

    def plan_delivery(self,index,plan):
        if not self.db.execute('SELECT 1 FROM receipts WHERE server_index=?',(index,)).fetchone():
            raise ValueError('Cannot deliver an unrecorded receipt')
        payload=json.dumps(plan,sort_keys=True)
        prior=self.db.execute('SELECT plan FROM deliveries WHERE server_index=?',(index,)).fetchone()
        if prior and prior[0]!=payload:raise ValueError('Delivery plan changed for an existing receipt')
        if not prior:
            with self.db:self.db.execute('INSERT INTO deliveries(server_index,plan) VALUES (?,?)',(index,payload))

    def pending_deliveries(self):
        return [dict(index=i,plan=json.loads(plan),state=state) for i,plan,state in self.db.execute(
            "SELECT server_index,plan,state FROM deliveries WHERE state!='applied' ORDER BY server_index")]

    def reconciliation_deliveries(self):
        """Include saved receipts so restoring an older native save can recover them."""
        return [dict(index=i,plan=json.loads(plan),state=state) for i,plan,state in self.db.execute(
            'SELECT server_index,plan,state FROM deliveries ORDER BY server_index')]

    def bind_native_save(self,path):
        value=json.dumps(dict(path=str(Path(path).resolve()),format='HMGR1/pinned'),sort_keys=True)
        prior=self.db.execute("SELECT value FROM metadata WHERE key='native_save_identity'").fetchone()[0]
        if prior not in ('unverified',value):raise ValueError('This AP journal is bound to a different native save file')
        with self.db:self.db.execute("UPDATE metadata SET value=? WHERE key='native_save_identity'",(value,))

    def record_saved(self,index,evidence):
        if not evidence.get('save_confirmed') or not evidence.get('native_file') or not evidence.get('sha256'):
            raise ValueError('Native disk verification required')
        with self.db:
            self.db.execute("UPDATE deliveries SET state='applied',evidence=? WHERE server_index=?",
                            (json.dumps(evidence,sort_keys=True),index))
            self.db.execute("UPDATE receipts SET native_state='applied' WHERE server_index=?",(index,))
        logging.info('Native save verified on disk: AP receipt %s',index)

    def record_memory_verification(self,index,evidence):
        if not (evidence.get('verified') or (evidence.get('found') and evidence.get('owned'))):
            raise ValueError('Native effect verification failed')
        with self.db:
            self.db.execute("UPDATE deliveries SET state='memory_verified',evidence=? WHERE server_index=?",
                            (json.dumps(evidence,sort_keys=True),index))
            self.db.execute("UPDATE receipts SET native_state='not_applied' WHERE server_index=?",(index,))
