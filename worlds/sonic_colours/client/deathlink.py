"""Native-death-independent, no-echo protocol state machine.

One remote event waits for safe gameplay for at most 30 seconds. DeathLink is
not exposed by the current generation profile until a native kill is verified.
"""
import hashlib
import json


class DeathLink:
    def __init__(self, journal):
        self.journal = journal
        self.state = 'GAME_NOT_READY'
        self.pending = None
        self.remote_cycle = journal.data.get('remote_cycle', False)
        if self.remote_cycle:
            self.state = 'REMOTE_DYING'
        self.alive_polls = 0

    def receive(self, event, now):
        key = hashlib.sha256(json.dumps(event, sort_keys=True).encode()).hexdigest()
        if key in self.journal.data['remote_deaths']:
            return False
        self.journal.data['remote_deaths'].append(key)
        self.journal.data['remote_deaths'] = self.journal.data['remote_deaths'][-256:]
        self.journal.save()
        # Policy: drop additional remote deaths while one is pending/in progress.
        if self.pending or self.remote_cycle:
            return False
        self.pending = now + 30
        return True

    def poll(self, *, safe, native_state, now, kill):
        if self.pending is not None and now >= self.pending:
            self.pending = None
        if not safe:
            self.alive_polls = 0
            return False
        if self.pending is not None and native_state == 'alive' and not self.remote_cycle:
            self.remote_cycle = True  # Suppress echo BEFORE native invocation.
            self.journal.data['remote_cycle'] = True
            self.journal.save()
            self.pending = None
            self.state = 'REMOTE_DYING'
            kill()  # Failure remains suppressed; do not invoke twice.
            return False
        if native_state in ('dying', 'dead'):
            local_event = self.state == 'ALIVE' and not self.remote_cycle
            self.state = 'DEAD'
            self.alive_polls = 0
            return local_event
        if native_state == 'respawning':
            self.state = 'RESPAWN_WAIT'
            self.alive_polls = 0
            return False
        if native_state == 'alive':
            if self.state == 'REMOTE_DYING':
                return False
            self.alive_polls += 1
            if self.alive_polls >= 3:
                self.state = 'ALIVE'
                self.remote_cycle = False
                if self.journal.data.get('remote_cycle'):
                    self.journal.data['remote_cycle'] = False
                    self.journal.save()
            else:
                self.state = 'COOLDOWN'
        return False
