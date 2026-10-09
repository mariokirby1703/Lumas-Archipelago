"""Atomic, fsynced receipt journal with exclusive process ownership.

Prepared effects are uncertain after a crash. Never automatically replay them:
guest memory and a host file cannot participate in one atomic transaction.
"""
import hashlib
import json
import os
from pathlib import Path
import tempfile


class Journal:
    def __init__(self, directory, identity):
        self.identity = dict(identity)
        for key in ('seed', 'team', 'slot', 'revision'):
            if key not in identity:
                raise ValueError(f'journal identity missing {key}')
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
        self.path = directory / (digest + '.json')
        self.lock = open(directory / (digest + '.lock'), 'a+b')
        self.closed = False
        self.persistence_pending = False
        try:
            self.lock.seek(0)
            if self.lock.read(1) == b'':
                self.lock.write(b'0')
                self.lock.flush()
            self.lock.seek(0)
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(self.lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.data = (json.loads(self.path.read_text(encoding='utf-8')) if self.path.exists() else
                         {'version': 2, 'identity': identity, 'save_identity': None, 'receipts': [],
                          'effects': {}, 'checks': [], 'remote_deaths': [], 'remote_cycle': False})
            if self.data.get('identity') != self.identity or self.data.get('version') not in (1, 2):
                raise ValueError('journal identity/schema mismatch')
            self.data['version'] = 2
            self.data.setdefault('pickup_events', [])
            self.data.setdefault('ever_collected_mask', {})
            self.data.setdefault('pickup_checks', [])
            self.data.setdefault('acknowledged_locations', [])
            if any(type(mask) is not int or not 0 <= mask <= 31
                   for mask in self.data['ever_collected_mask'].values()):
                raise ValueError('corrupt pickup mask')
        except Exception:
            self.lock.close()
            self.closed = True
            raise

    def save(self):
        if self.closed:
            raise RuntimeError('journal closed')
        self.persistence_pending = True
        fd, temporary = tempfile.mkstemp(prefix=self.path.stem, suffix='.tmp', dir=self.path.parent)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as handle:
                json.dump(self.data, handle, sort_keys=True)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
            if os.name != 'nt':
                descriptor = os.open(self.path.parent, os.O_RDONLY)
                try:
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        self.persistence_pending = False

    def record_history(self, item_ids):
        previous = self.data['receipts']
        common = min(len(previous), len(item_ids))
        if previous[:common] != item_ids[:common]:
            raise ValueError('received_history_mismatch: refusing replay')
        if len(item_ids) < len(previous):
            raise ValueError('received_history_truncated: refusing inventory rollback')
        if len(item_ids) > len(previous):
            self.data['receipts'] = list(item_ids)
            self.save()

    def prepare(self, index, item, context, before, after):
        key = str(index)
        if key in self.data['effects']:
            raise ValueError('effect_already_recorded_or_uncertain')
        self.data['effects'][key] = {'state': 'prepared', 'item': item,
                                     'context': context, 'before': before, 'after': after}
        self.save()

    def confirm(self, index):
        effect = self.data['effects'][str(index)]
        if effect['state'] not in ('prepared', 'verifying'):
            raise ValueError('effect_not_prepared')
        effect['state'] = 'confirmed'
        self.save()

    def recover_skip(self, index):
        effect = self.data['effects'][str(index)]
        if effect['state'] not in ('prepared', 'verifying', 'uncertain'):
            raise ValueError('effect_not_uncertain')
        effect['state'] = 'skipped_by_operator'
        self.save()

    def add_checks(self, checks):
        updated = sorted(set(self.data['checks']) | set(checks))
        if updated != self.data['checks']:
            self.data['checks'] = updated
            self.save()

    def record_pickups(self, events, masks, checks):
        """One durable transaction before any network send; never Wii-save scoped."""
        checks = set(checks)
        self.data['pickup_events'].extend(events)
        self.data['ever_collected_mask'].update(masks)
        self.data['pickup_checks'] = sorted(set(self.data['pickup_checks']) | checks)
        self.data['checks'] = sorted(set(self.data['checks']) | checks)
        self.save()

    def acknowledge(self, locations):
        confirmed = set(locations) & set(self.data['checks'])
        updated = set(self.data['acknowledged_locations']) | confirmed
        if updated != set(self.data['acknowledged_locations']):
            self.data['acknowledged_locations'] = sorted(updated)
            self.save()

    def close(self):
        if not self.closed:
            self.closed = True
            self.lock.close()

    def __enter__(self): return self
    def __exit__(self, *args): self.close()
