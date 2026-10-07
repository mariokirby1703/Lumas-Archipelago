"""In-memory receipt and check state for one client process."""
from time import monotonic

from .constants import CURRENCY_SETTLE_SECONDS


class Journal:
    def __init__(self, _path=None):
        self.confirmation = None
        self.path = None
        self.data = {"version": 1, "cursor": 0, "checks": [], "pending": None}

    def save(self):
        pass

    def add_checks(self, checks):
        combined = sorted(set(self.data['checks']) | set(checks))
        if combined != self.data['checks']:
            self.data['checks'] = combined
            self.save()

    def advance(self, index):
        self.data['cursor'] = index + 1
        self.data['pending'] = None
        self.save()

    def reset_confirmation(self):
        self.confirmation = None

    def grant(self, memory, sub, index, offset, amount, size):
        pending = self.data['pending']
        if pending is None:
            before = memory.integer(sub + offset, size)
            pending = {"index": index, "offset": offset, "size": size,
                       "before": before,
                       "after": max(0, min((1 << (8*size)) - 1, before + amount)),
                       "amount": amount}
            self.data['pending'] = pending
            self.save()  # persist intent before touching guest memory
        if (pending['index'], pending['offset'], pending['size']) != (index, offset, size):
            raise ValueError("Receipt history differs from pending MiniGolf grant")
        current = memory.integer(sub + offset, size)
        positive = pending.get('amount', pending['after'] - pending['before']) > 0
        survived = current >= pending['after'] if positive else current == pending['after']
        if current != pending['before'] and not survived:
            raise ValueError("Interrupted coin grant has an ambiguous balance. Use /currency_recover skip "
                             "to retain the current balance, or /currency_recover apply to grant the item again.")
        key = (sub, index, pending['before'], pending['after'])
        now = monotonic()
        if survived and self.confirmation is not None:
            if self.confirmation[0] == key and now - self.confirmation[1] >= CURRENCY_SETTLE_SECONDS:
                result = pending['before'], pending['after']
                self.advance(index)
                self.reset_confirmation()
                return result
        if self.confirmation is None or self.confirmation[0] != key or not survived:
            self.confirmation = (key, now)
        if current == pending['before']:
            memory.put(sub + offset, pending['after'], size)
        memory.put(sub + 0xA1, 1)
        result = pending['before'], pending['after']
        return result
