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
            CREATE TABLE IF NOT EXISTS item_popups (server_index INTEGER PRIMARY KEY,
                text TEXT NOT NULL, progression INTEGER NOT NULL, state TEXT NOT NULL DEFAULT 'queued');
            CREATE TABLE IF NOT EXISTS sent_popups (event_key TEXT PRIMARY KEY,
                text TEXT NOT NULL, classification TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'queued');
            CREATE TABLE IF NOT EXISTS pickup_bindings (source TEXT PRIMARY KEY, bit INTEGER UNIQUE NOT NULL, proof TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS pickup_conflicts (bit INTEGER PRIMARY KEY, evidence TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS diagnostic_events (id INTEGER PRIMARY KEY AUTOINCREMENT, payload TEXT NOT NULL);
        ''')
        columns={row[1] for row in self.db.execute('PRAGMA table_info(item_popups)')}
        if 'classification' not in columns:
            with self.db:
                self.db.execute("ALTER TABLE item_popups ADD COLUMN classification TEXT NOT NULL DEFAULT 'filler'")
                self.db.execute("UPDATE item_popups SET classification='progression' WHERE progression=1")
        with self.db:
            self.db.execute('INSERT OR IGNORE INTO metadata VALUES (?,?)', ('binding',encoded))
            self.db.execute('INSERT OR IGNORE INTO metadata VALUES (?,?)', ('native_save_identity','unverified'))

    def queue(self, locations):
        with self.db:
            self.db.executemany('INSERT OR IGNORE INTO outgoing(location) VALUES (?)', ((int(x),) for x in locations))

    def pickup_conflict(self,bit,sources,reason):
        evidence=json.dumps(dict(sources=sorted(sources),reason=reason,verification='unsupported',mutation=False),sort_keys=True)
        with self.db:self.db.execute('INSERT OR IGNORE INTO pickup_conflicts VALUES (?,?)',(bit,evidence))

    def diagnostic(self,event):
        from datetime import datetime,timezone
        event=dict(event,timestamp=datetime.now(timezone.utc).isoformat())
        with self.db:
            self.db.execute('INSERT INTO diagnostic_events(payload) VALUES (?)',(json.dumps(event,sort_keys=True),))
            self.db.execute('DELETE FROM diagnostic_events WHERE id <= (SELECT COALESCE(MAX(id),0)-1000 FROM diagnostic_events)')

    def diagnostics(self,limit=200):
        return [json.loads(row[0]) for row in self.db.execute('SELECT payload FROM diagnostic_events ORDER BY id DESC LIMIT ?',
                                                           (max(0,min(int(limit),1000)),))]

    def diagnostic_revision(self):
        return self.db.execute('SELECT COALESCE(MAX(id),0) FROM diagnostic_events').fetchone()[0]

    def collectible_report(self):
        return dict(format='LCU collectible evidence',version=1,game_writes=False,
                    bindings=self.pickup_bindings(),blocked_bits=sorted(self.pickup_conflicts()),events=self.diagnostics())

    def pickup_conflicts(self):
        return {row[0] for row in self.db.execute('SELECT bit FROM pickup_conflicts')}

    def pickup_bindings(self):
        return [json.loads(row[0]) for row in self.db.execute('SELECT proof FROM pickup_bindings ORDER BY source')]

    def store_pickup_binding(self,proof):
        source=proof['source_key'];bit=proof['bit']
        if proof.get('verification')!='native_binding_verified':raise ValueError('Verified structural proof required')
        existing=self.db.execute('SELECT source,bit,proof FROM pickup_bindings WHERE source=? OR bit=?',(source,bit)).fetchall()
        if any(s!=source or b!=bit for s,b,_ in existing):
            self.pickup_conflict(bit,{source,*(r[0] for r in existing)},'journal source/bit collision')
            for _,old_bit,_ in existing:self.pickup_conflict(old_bit,{source},'journal source/bit collision')
            return True
        if bit in self.pickup_conflicts():return False
        if existing:
            old=json.loads(existing[0][2])
            upgrade=proof.get('proof_version',1)>old.get('proof_version',1)
            upgrade=upgrade or (proof.get('writer_enabled') is True and old.get('writer_enabled') is not True)
            transition=proof.get('collection_transition_observed') and not old.get('collection_transition_observed')
            if upgrade or transition:
                # Preserve actual collection evidence when refreshing metadata.
                refreshed=dict(proof)
                if old.get('collection_transition_observed'):
                    refreshed.update(collection_transition_observed=True,before_collected=old.get('before_collected'),
                                     after_collected=old.get('after_collected'))
                with self.db:self.db.execute('UPDATE pickup_bindings SET proof=? WHERE source=?',(json.dumps(refreshed,sort_keys=True),source))
                self.diagnostic(dict(kind='pickup_binding_refresh',verification='native_binding_verified',mutation=False,proof=refreshed))
            return bool(upgrade or transition)
        with self.db:self.db.execute('INSERT INTO pickup_bindings VALUES (?,?,?)',(source,bit,json.dumps(proof,sort_keys=True)))
        self.diagnostic(dict(kind='pickup_binding',verification='native_binding_verified',mutation=False,proof=proof))
        return True

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

    def assignment_policy(self,slot_data):
        """Reconstruct diagnostic permissions across reconnect; not native enforcement."""
        from assignment_policy import build_policy
        receipts=[json.loads(row[0]) for row in self.db.execute('SELECT payload FROM receipts ORDER BY server_index')]
        return build_policy(slot_data,receipts,self.binding_token.hex())

    def queue_popup(self,index,effect,text=None):
        # Existing saved receipts are history, not a new flood on first upgrade.
        # Already queued notifications survive reconnects and process restarts.
        row=self.db.execute('SELECT state FROM deliveries WHERE server_index=?',(index,)).fetchone()
        if not row:return
        name=effect.get('name','AP Item')
        classification=effect.get('classification','filler')
        if classification=='progression_skip_balancing':classification='progression'
        if classification not in ('progression','useful','filler','trap'):classification='filler'
        with self.db:
            if row[0]!='applied':
                self.db.execute('INSERT OR IGNORE INTO item_popups(server_index,text,progression,classification) VALUES (?,?,?,?)',
                    (index,text or name+' erhalten',int(classification=='progression'),classification))
            # Upgrade still-waiting v1 notifications without replaying old displays.
            self.db.execute("UPDATE item_popups SET classification=? WHERE server_index=? AND state='queued'",
                            (classification,index))
            if text:
                self.db.execute("UPDATE item_popups SET text=? WHERE server_index=? AND state='queued'",(text,index))

    def queue_sent_popup(self,event):
        with self.db:
            self.db.execute('INSERT OR IGNORE INTO sent_popups(event_key,text,classification) VALUES (?,?,?)',
                (event['key'],event['text'],event['classification']))

    def next_popup(self):
        sent=self.db.execute("SELECT event_key,text,classification FROM sent_popups WHERE state='queued' ORDER BY rowid LIMIT 1").fetchone()
        if sent:return dict(index=sent[0],text=sent[1],classification=sent[2],progression=sent[2]=='progression')
        # "You received" confirms the AP receipt, not a native grant or autosave.
        # Native delivery can wait for a safe context/save without blocking text.
        row=self.db.execute("""SELECT p.server_index,p.text,p.classification FROM item_popups p
            JOIN deliveries d ON d.server_index=p.server_index
            WHERE p.state='queued'
            ORDER BY p.server_index LIMIT 1""").fetchone()
        return dict(index=row[0],text=row[1],classification=row[2],progression=row[2]=='progression') if row else None

    def popup_state(self,index,state):
        if state not in ('queued','dispatching','submitted','uncertain'):
            raise ValueError('Invalid popup state')
        with self.db:
            if isinstance(index,str):
                self.db.execute('UPDATE sent_popups SET state=? WHERE event_key=?',(state,index))
            else:self.db.execute('UPDATE item_popups SET state=? WHERE server_index=?',(state,index))

    def plan_delivery(self,index,plan):
        if not self.db.execute('SELECT 1 FROM receipts WHERE server_index=?',(index,)).fetchone():
            raise ValueError('Cannot deliver an unrecorded receipt')
        payload=json.dumps(plan,sort_keys=True)
        prior=self.db.execute('SELECT plan,state FROM deliveries WHERE server_index=?',(index,)).fetchone()
        if prior and prior[0]!=payload:
            old=json.loads(prior[0])
            safe_rex_migration=(old==dict(kind='ability_unlock',ability='Rex Fury') and
                plan==dict(kind='model_unlock',native_name='ROBBER_REXFURY') and prior[1]=='waiting_native_backend')
            if not safe_rex_migration:raise ValueError('Delivery plan changed for an existing receipt')
            with self.db:self.db.execute('UPDATE deliveries SET plan=? WHERE server_index=?',(payload,index))
            logging.info('Migrated unbound Rex Fury receipt %s to roster-backed model grant',index)
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
        self.diagnostic(dict(kind='native_save_confirmation',receipt=index,verification='native_binding_verified',
                             mutation=False,proof=evidence))

    def record_memory_verification(self,index,evidence):
        if not (evidence.get('verified') or (evidence.get('found') and evidence.get('owned'))):
            raise ValueError('Native effect verification failed')
        with self.db:
            self.db.execute("UPDATE deliveries SET state='memory_verified',evidence=? WHERE server_index=?",
                            (json.dumps(evidence,sort_keys=True),index))
            self.db.execute("UPDATE receipts SET native_state='not_applied' WHERE server_index=?",(index,))
        self.diagnostic(dict(kind='native_grant_observed',receipt=index,verification='native_binding_verified',
                             mutation=False,save_confirmed=False,proof=evidence))

    def record_runtime_verification(self,index,evidence):
        if not evidence.get('verified') or evidence.get('native_save_flag') is not False:
            raise ValueError('Verified runtime gate evidence required')
        with self.db:
            self.db.execute("UPDATE deliveries SET state='runtime_verified',evidence=? WHERE server_index=?",
                            (json.dumps(evidence,sort_keys=True),index))
            self.db.execute("UPDATE receipts SET native_state='runtime_verified' WHERE server_index=?",(index,))
