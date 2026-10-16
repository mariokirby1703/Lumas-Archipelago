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
            # New host configuration cancels outstanding old native requests.
            # Require fresh living observations before releasing suppression.
            self.state = 'RESPAWN_WAIT'
        self.alive_polls = 0
        self.sequence = None
        self.remote_request = journal.data.get('remote_request')
        self.remote_deadline = None
        self.last_action = 'idle'
        self.last_error = None
        self.remote_witnessed = False

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
        self.last_action = 'remote event queued'
        return True

    def poll(self, *, safe, native_state, now, kill, native_sequence=None, remote_ack=None, cancel=None, kill_safe=True):
        event=False
        if native_sequence is not None:
            event=self.sequence is not None and native_sequence>self.sequence
            self.sequence=native_sequence
        if self.pending is not None and now >= self.pending:
            self.pending = None
            self.last_action = 'remote event expired'
        if self.remote_deadline is not None and now >= self.remote_deadline:
            try:
                if cancel:cancel()
            except Exception as error:
                # The guest may have executed the request already. A failed
                # cancellation is not proof that it did not die later.
                self.last_error = f'cancel not verified: {error}'
                self.last_action = 'remote request cancellation uncertain'
            else:
                self.last_action = 'remote request expired/cancellation attempted'
            self.remote_deadline = None
            self.state = 'RESPAWN_WAIT'
            # remote_cycle remains sticky until a witnessed native death.
        if event:
            if self.remote_cycle:self.remote_witnessed=True
            local_event=safe and not self.remote_cycle and self.state=='ALIVE'
            self.state='DEAD';self.alive_polls=0
            self.last_action='remote death witnessed' if self.remote_cycle else 'local death witnessed'
            if local_event:return True
        if not safe:
            self.alive_polls = 0
            return False
        if (self.remote_cycle and not self.remote_witnessed and self.remote_deadline is None
                and self.remote_request is not None and native_state=='alive' and cancel):
            try:recovered=cancel() is True
            except Exception as error:
                self.last_error=f'cancel not verified: {error}'
                recovered=False
            if recovered:
                self.remote_cycle=False;self.remote_request=None
                self.journal.data['remote_cycle']=False
                self.journal.data.pop('remote_request',None)
                self.journal.save()
                self.state='COOLDOWN';self.alive_polls=0
                self.last_action='unconsumed request cancelled across native frame fence'
        if self.pending is not None and native_state == 'alive' and not self.remote_cycle and kill_safe:
            self.remote_cycle = True  # Suppress echo BEFORE native invocation.
            self.journal.data['remote_cycle'] = True
            self.journal.save()
            self.pending = None
            self.state = 'REMOTE_DYING'
            self.remote_witnessed=False
            try:
                self.remote_request=kill()
                self.journal.data['remote_request']=self.remote_request
                self.journal.save()
                self.remote_deadline=now+30
                self.last_action='native remote kill requested'
            except Exception as error:
                self.last_error=str(error);self.last_action='native request failed'
                self.state='RESPAWN_WAIT'
                raise
            return False
        if native_state in ('dying', 'dead'):
            if self.remote_cycle:self.remote_witnessed=True
            local_event = self.state == 'ALIVE' and not self.remote_cycle
            self.state = 'DEAD'
            self.alive_polls = 0
            return local_event
        if native_state == 'respawning':
            self.state = 'RESPAWN_WAIT'
            self.alive_polls = 0
            return False
        if native_state == 'alive':
            if self.remote_cycle and not self.remote_witnessed:
                # ACK / timeout / three alive polls do NOT prove that an
                # interrupted native death request cannot execute later.
                # Fail closed until a native death sequence is observed.
                self.alive_polls = 0
                return False
            self.alive_polls += 1
            if self.alive_polls >= 3:
                self.state = 'ALIVE'
                self.remote_cycle = False
                self.remote_deadline = None
                self.remote_request = None
                if self.journal.data.get('remote_cycle'):
                    self.journal.data['remote_cycle'] = False
                    self.journal.data.pop('remote_request',None)
                    self.journal.save()
            else:
                self.state = 'COOLDOWN'
        return False

    def status(self):
        return {'state':self.state,'pending_deadline':self.pending,'remote_cycle':self.remote_cycle,
                'local_sequence':self.sequence,'remote_request':self.remote_request,
                'remote_deadline':self.remote_deadline,'last_action':self.last_action,'last_error':self.last_error}
