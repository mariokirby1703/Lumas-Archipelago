"""Atomic local receipt/check journal, scoped to AP seed, team, slot and local player.

Game saves and disk writes cannot form an atomic transaction. An interrupted grant
is recovered by comparing its before/after balances; ambiguous cases fail closed.
"""
import json
import os
from pathlib import Path


class Journal:
    def __init__(self, path):
        self.path = Path(path)
        self.data = {"version": 1, "cursor": 0, "checks": [], "pending": None}
        if self.path.exists():
            self.data = json.loads(self.path.read_text(encoding='utf-8'))
            if self.data.get('version') != 1 or not isinstance(self.data.get('cursor'), int) or self.data['cursor'] < 0:
                raise ValueError("Unsupported or invalid MiniGolf journal; restore its backup")

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix('.tmp')
        with temporary.open('w', encoding='utf-8') as handle:
            json.dump(self.data, handle, sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, self.path)

    def add_checks(self, checks):
        combined = sorted(set(self.data['checks']) | set(checks))
        if combined != self.data['checks']:
            self.data['checks'] = combined
            self.save()

    def advance(self, index):
        self.data['cursor'] = index + 1
        self.data['pending'] = None
        self.save()

    def grant(self, memory, sub, index, offset, amount, size):
        pending = self.data['pending']
        if pending is None:
            before = memory.integer(sub + offset, size)
            pending = {"index": index, "offset": offset, "size": size,
                       "before": before,
                       "after": max(0, min((1 << (8*size)) - 1, before + amount))}
            self.data['pending'] = pending
            self.save()  # persist intent before touching guest memory
        if (pending['index'], pending['offset'], pending['size']) != (index, offset, size):
            raise ValueError("Receipt history differs from pending MiniGolf grant")
        current = memory.integer(sub + offset, size)
        if current not in (pending['before'], pending['after']):
            raise ValueError("Interrupted coin grant has an ambiguous balance. Use /currency_recover skip "
                             "to retain the current balance, or /currency_recover apply to grant the item again.")
        memory.put(sub + offset, pending['after'], size)
        memory.put(sub + 0xA1, 1)
        self.advance(index)
