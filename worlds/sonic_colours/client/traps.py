from .memory import MemoryUnavailable


class TemporaryTrap:
    """Restoration failure retains its original context and blocks another trap.

    Elapsed time counts only stable gameplay; pause/loading does not spend time.
    No production native swimming adapter is registered.
    """
    def __init__(self):
        self.context = None
        self.remaining = 0
        self.restore = None

    def start(self, context, duration, apply, restore):
        if self.context is not None:
            raise MemoryUnavailable('temporary_trap_requires_restoration')
        if not 5 <= duration <= 60:
            raise ValueError('temporary trap duration must be 5..60')
        self.context, self.remaining, self.restore = context, duration, restore
        apply()

    def tick(self, context, elapsed, gameplay):
        if self.context is None:
            return
        if context != self.context:
            self.cleanup()
            return
        if gameplay:
            self.remaining -= max(0, elapsed)
        if self.remaining <= 0:
            self.cleanup()

    def cleanup(self):
        if self.context is not None:
            self.restore(self.context)
            self.context, self.restore, self.remaining = None, None, 0
