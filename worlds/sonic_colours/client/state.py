from dataclasses import dataclass, field
from .memory import MemoryUnavailable
from .versions import VERSION


@dataclass(frozen=True)
class Snapshot:
    session: str
    save_identity: str
    visible_slot: int
    scene: str
    actual_mission: str | None
    clicked_slot: str | None = None
    stable_polls: int = 0
    persisted_clears: frozenset = frozenset()
    persisted_rings: dict = field(default_factory=dict)
    awarded_ranks: dict = field(default_factory=dict)
    emerald_rewards: frozenset = frozenset()
    super_activated: bool = False
    death_state: str = 'unknown'
    rings_address: int | None = None
    lives_address: int | None = None


class SaveGuard:
    def __init__(self, journal):
        self.journal = journal
        self.armed = False
        self.session = None

    def arm(self, snapshot, *, operator_confirmed, fresh_evidence):
        self.armed = False
        if not VERSION['capabilities']['save_identity']:
            raise MemoryUnavailable('WRITE_BLOCKED: save_slot_mapping_unverified')
        if snapshot.visible_slot != 1:
            raise MemoryUnavailable('wrong_save_slot: manually create fresh visible Save Slot 1')
        if not operator_confirmed or not snapshot.save_identity:
            raise MemoryUnavailable('fresh_save_confirmation_required')
        bound = self.journal.data['save_identity']
        if bound is None:
            if len(fresh_evidence) < 2 or not all(fresh_evidence.values()):
                raise MemoryUnavailable('save_not_fresh: multiple independent fields required')
            self.journal.data['save_identity'] = snapshot.save_identity
            self.journal.save()
        elif bound != snapshot.save_identity:
            raise MemoryUnavailable('seed_save_identity_mismatch')
        self.session = snapshot.session
        self.armed = True

    def check(self, snapshot):
        if (not self.armed or snapshot.visible_slot != 1 or snapshot.session != self.session
                or snapshot.save_identity != self.journal.data['save_identity']):
            self.armed = False
            raise MemoryUnavailable('WRITE_BLOCKED: save_not_armed_or_session_changed')
        if snapshot.stable_polls < 3:
            raise MemoryUnavailable('WRITE_BLOCKED: unstable_context')
        return snapshot.session, snapshot.save_identity, snapshot.scene, snapshot.actual_mission

    def disarm(self):
        self.armed = False
        self.session = None


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
