from dataclasses import dataclass, field
from enum import Enum
import uuid
from .memory import MemoryUnavailable
from .versions import VERSION


@dataclass(frozen=True)
class Snapshot:
    session: str
    save_identity: str | None
    visible_slot: int | None
    scene: str
    actual_mission: str | None
    clicked_slot: str | None = None
    stable_polls: int = 0
    persisted_clears: frozenset = frozenset()
    persisted_rings: dict = field(default_factory=dict)
    active_rings: dict = field(default_factory=dict)
    awarded_ranks: dict = field(default_factory=dict)
    emerald_rewards: frozenset = frozenset()
    opened_capsules: frozenset = frozenset()
    discovered_wisps: frozenset = frozenset()
    death_state: str = 'unknown'
    rings_address: int | None = None
    lives_address: int | None = None
    new_game_verified: bool = False
    save_identity_verified: bool = False
    progress_verified: bool = False
    scene_verified: bool = False
    fresh_fields: tuple = ()
    new_save_selected: bool = False
    candidate_clears: frozenset = frozenset()
    evidence: dict = field(default_factory=dict)
    status: str = 'native scene/save proof pending'


class PlaythroughState(str, Enum):
    UNBOUND_BOOTSTRAP = 'UNBOUND_BOOTSTRAP'
    MANDATORY_PROLOGUE = 'MANDATORY_PROLOGUE'
    VANILLA_SAVE_SELECTION = 'VANILLA_SAVE_SELECTION'
    BOUND_PLAYTHROUGH = 'BOUND_PLAYTHROUGH'
    RESUME = 'RESUME'
    UNSAFE = 'UNSAFE_OR_SWITCHED_SAVE'
    DISCONNECTED = 'DISCONNECTED'


class SaveGuard:
    """Identity attribution is independent of operation-specific write readiness.

    A command confirms intent; only corroborated native evidence starts an epoch.
    Any vanilla save slot is allowed. Heap pointer addresses are never save IDs.
    """
    def __init__(self, journal):
        self.journal = journal
        self.armed = False
        self.session = None
        self.operator_confirmed = False
        self.state = PlaythroughState.UNBOUND_BOOTSTRAP
        self.reason = 'Choose New Game for a new seed; /sonicnewgame confirms intent.'

    def confirm_new_game(self):
        if self.journal.data['save_identity'] is not None:
            raise MemoryUnavailable('seed already bound; resume its save instead of starting another game')
        self.operator_confirmed = True
        self.reason = 'New Game confirmed; waiting for native menu/freshness corroboration.'

    def observe(self, snapshot):
        self.armed = False
        bound = self.journal.data['save_identity']
        if bound is not None:
            if not snapshot.save_identity_verified:
                self.reason = 'save_identity_proof_missing: reads retained, writes deferred'
                return
            if bound != snapshot.save_identity:
                self.state = PlaythroughState.UNSAFE
                self.reason = 'seed_save_identity_mismatch'
                return
            previous = set(self.journal.data.get('native_monotonic_clears', []))
            if snapshot.progress_verified and not previous <= snapshot.persisted_clears:
                self.state = PlaythroughState.UNSAFE
                self.reason = 'savestate_or_progress_rollback: writes and attribution paused; checks retained'
                return
            if snapshot.progress_verified and set(snapshot.persisted_clears) != previous:
                self.journal.data['native_monotonic_clears'] = sorted(snapshot.persisted_clears)
                self.journal.save()
            self.state = PlaythroughState.RESUME if self.session != snapshot.session else PlaythroughState.BOUND_PLAYTHROUGH
            self.session = snapshot.session
            self.armed = snapshot.stable_polls >= 3 and snapshot.scene_verified
            self.reason = 'bound seed/save resumed' if self.armed else 'waiting for stable scene'
            return
        bootstrap = self.journal.data.get('bootstrap')
        if bootstrap is None:
            if not (self.operator_confirmed and snapshot.new_game_verified and snapshot.scene_verified
                    and len(snapshot.fresh_fields) >= 2 and all(snapshot.fresh_fields)):
                self.reason = 'new_game_indicator_unverified: confirmation needs native menu and freshness evidence'
                return
            bootstrap = {'epoch': uuid.uuid4().hex, 'session': snapshot.session, 'checks': [],
                         'observed_missions': [], 'goal': False}
            self.journal.data['bootstrap'] = bootstrap
            self.journal.save()
            self.state = PlaythroughState.MANDATORY_PROLOGUE
        if bootstrap['session'] != snapshot.session:
            self.state = PlaythroughState.UNSAFE
            self.reason = 'unbound_prologue_session_changed: evidence retained; binding needs reconciliation'
            return
        if snapshot.scene == 'save_selection' and snapshot.scene_verified:
            self.state = PlaythroughState.VANILLA_SAVE_SELECTION
        if snapshot.save_identity_verified and snapshot.new_save_selected and snapshot.save_identity:
            if not set(bootstrap['observed_missions']) <= snapshot.persisted_clears:
                self.reason = 'bootstrap_progress_not_reconciled_with_selected_save'
                return
            self.journal.data['save_identity'] = snapshot.save_identity
            self.journal.data['native_monotonic_clears'] = sorted(snapshot.persisted_clears)
            self.journal.data['checks'] = sorted(set(self.journal.data['checks']) | set(bootstrap['checks']))
            self.journal.data['goal_observed'] = bootstrap.get('goal', False)
            self.journal.save()
            self.session = snapshot.session
            self.state = PlaythroughState.BOUND_PLAYTHROUGH
            self.armed = snapshot.stable_polls >= 3 and snapshot.scene_verified
            self.reason = 'new playthrough bound to selected vanilla slot'
        else:
            self.reason = 'prologue observed locally; awaiting verified vanilla save selection'

    def can_record(self, snapshot):
        if not snapshot.progress_verified:
            return False
        if self.journal.data['save_identity'] is not None:
            return (self.state in (PlaythroughState.BOUND_PLAYTHROUGH, PlaythroughState.RESUME)
                    and snapshot.save_identity_verified and snapshot.save_identity == self.journal.data['save_identity'])
        bootstrap = self.journal.data.get('bootstrap')
        return bool(bootstrap and bootstrap['session'] == snapshot.session and self.state in (
            PlaythroughState.MANDATORY_PROLOGUE, PlaythroughState.VANILLA_SAVE_SELECTION))

    def can_send(self, snapshot):
        return self.can_record(snapshot) and self.journal.data['save_identity'] is not None

    def arm(self, snapshot, *, operator_confirmed, fresh_evidence):
        # Kept as an explicit call for adapter integrations; no slot-number rule.
        if operator_confirmed:
            self.confirm_new_game()
        self.observe(snapshot)
        if not self.armed:
            raise MemoryUnavailable('WRITE_BLOCKED: ' + self.reason)

    def check(self, snapshot):
        if (not self.armed or not snapshot.save_identity_verified or snapshot.session != self.session
                or snapshot.save_identity != self.journal.data['save_identity']):
            self.armed = False
            raise MemoryUnavailable('WRITE_BLOCKED: save_not_bound_or_session_changed')
        if snapshot.stable_polls < 3 or not snapshot.scene_verified:
            raise MemoryUnavailable('WRITE_BLOCKED: unstable_context')
        return snapshot.session, snapshot.save_identity, snapshot.scene, snapshot.actual_mission

    def disarm(self):
        self.armed = False
        self.session = None
        self.state = PlaythroughState.DISCONNECTED


class WritePolicy:
    """Resolve context again for EVERY write; only exact validated fields allowed.

    Production capabilities are all false until a reviewed PAL live adapter is
    implemented. No CLI switch can turn this policy into an unchecked writer.
    """
    def __init__(self, memory, guard, snapshot_reader):
        self.memory, self.guard, self.snapshot_reader = memory, guard, snapshot_reader

    def __call__(self, operation, address, size):
        if not VERSION['capabilities'].get(operation, False):
            raise MemoryUnavailable(f'WRITE_BLOCKED: requires_verified_hook: {operation}')
        self.memory.verify_revision()
        snapshot = self.snapshot_reader(self.memory)
        token = self.guard.check(snapshot)
        if snapshot.scene != 'gameplay' or snapshot.death_state != 'alive':
            raise MemoryUnavailable('WRITE_BLOCKED: unsafe_scene')
        if operation == 'stats':
            allowed = {snapshot.rings_address, snapshot.lives_address}
        else:
            raise MemoryUnavailable('WRITE_BLOCKED: operation has no reviewed address allowlist')
        if size != 4 or address % 4 or address not in allowed:
            raise MemoryUnavailable('WRITE_BLOCKED: address_not_allowed')
        return token
