"""Debounce presentation only; never delay the native event scanner."""
class StatusReporter:
    def __init__(self):
        self.published = None
        self.candidate = None
        self.since = 0
        self.last_emit = -float('inf')

    def ready(self, message, now):
        if message == self.published:
            self.candidate = None
            return False
        significant = message.startswith(('wrong_game', 'unknown_revision', 'WRITE_UNCERTAIN', 'Slot rejected'))
        if self.published is None or significant:
            self.published, self.last_emit = message, now
            return True
        if message != self.candidate:
            self.candidate, self.since = message, now
            return False
        if now - self.since < .5 or now - self.last_emit < 2:
            return False
        self.published, self.last_emit = message, now
        return True
