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
    stage_epoch: str | None = None
    pickup_verified: bool = False
    current_result: dict = field(default_factory=dict)
    awarded_ranks: dict = field(default_factory=dict)
    emerald_rewards: frozenset = frozenset()
    opened_capsules: frozenset = frozenset()
    discovered_wisps: frozenset = frozenset()
    death_state: str = 'unknown'
    ring_mirror_address: int | None = None
    world_lives_address: int | None = None
    rings_address: int | None = None
    lives_address: int | None = None
    boost_address: int | None = None
    boost_max_address: int | None = None
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
        self.reason = 'Choose New Game for a new seed; native intro detection is automatic.'

    def confirm_new_game(self):
        if self.journal.data['save_identity'] is not None:
            raise MemoryUnavailable('seed already bound; resume its save instead of starting another game')
        self.operator_confirmed = True
        self.reason = 'New Game confirmed; waiting for native menu/freshness corroboration.'

    def required_polls(self,snapshot):
        # Resuming an already bound, independently verified save on a native
        # map needs no extra scene debounce. WritePolicy re-resolves the save
        # chain and map actor/address for every permission/refresh write.
        if (snapshot.scene in ('global_map','world_map','game_land_select')
                and snapshot.scene_verified and snapshot.save_identity_verified
                and self.journal.data['save_identity'] is not None
                and snapshot.save_identity==self.journal.data['save_identity']):
            return 1
        return 3

    def observe(self, snapshot):
        self.armed = False
        bound = self.journal.data['save_identity']
        fresh_restart = (bound is not None and snapshot.new_game_verified
            and snapshot.scene_verified and snapshot.scene == 'gameplay'
            and snapshot.actual_mission == 'stg110' and snapshot.stable_polls >= 3
            and snapshot.save_identity is None and not snapshot.save_identity_verified
            and len(snapshot.fresh_fields) >= 2 and all(snapshot.fresh_fields))
        if fresh_restart:
            # Same authenticated seed journal, new native playthrough. Preserve
            # AP checks/receipts and archive the old native binding, not the save.
            keys = ('save_identity','native_binding','native_monotonic_clears',
                    'bootstrap','native_event_baseline')
            self.journal.data.setdefault('prior_playthroughs', []).append(
                {key:self.journal.data[key] for key in keys if key in self.journal.data})
            for key in keys:
                self.journal.data.pop(key, None)
            self.journal.data['save_identity'] = None
            self.journal.save()
            self.session = None
            self.state = PlaythroughState.UNBOUND_BOOTSTRAP
            bound = None
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
            self.armed = snapshot.stable_polls >= self.required_polls(snapshot) and snapshot.scene_verified
            self.reason = 'bound seed/save resumed' if self.armed else 'waiting for stable scene'
            return
        bootstrap = self.journal.data.get('bootstrap')
        # An unbound journal may outlive a client/Dolphin session or an aborted
        # intro. Only fresh, independently native-verified Act 1 can rebase it.
        fresh_intro=(snapshot.new_game_verified and snapshot.scene_verified
            and snapshot.scene=='gameplay' and snapshot.actual_mission=='stg110'
            and snapshot.stable_polls>=3 and snapshot.save_identity is None
            and not snapshot.save_identity_verified
            and len(snapshot.fresh_fields)>=2 and all(snapshot.fresh_fields))
        if (bootstrap is not None and fresh_intro and
                (bootstrap['session']!=snapshot.session or
                 bootstrap.get('intro_stage_epoch',snapshot.stage_epoch)!=snapshot.stage_epoch)):
            self.journal.data.setdefault('prior_prologues',[]).append(dict(bootstrap))
            self.journal.data['checks']=sorted(set(self.journal.data['checks'])|set(bootstrap.get('checks',[])))
            self.journal.data.pop('bootstrap',None)
            self.journal.data.pop('native_event_baseline',None)
            bootstrap=None
            self.session=None
            self.state=PlaythroughState.UNBOUND_BOOTSTRAP
        if bootstrap is None:
            if not (snapshot.new_game_verified and snapshot.scene_verified
                    and snapshot.actual_mission == 'stg110'
                    and len(snapshot.fresh_fields) >= 2 and all(snapshot.fresh_fields)):
                self.reason = 'new_game_indicator_unverified: waiting for native intro and freshness evidence'
                return
            bootstrap = {'epoch': uuid.uuid4().hex, 'session': snapshot.session, 'checks': [],
                         'observed_missions': [], 'goal': False, 'intro_stage_epoch':snapshot.stage_epoch,
                         'intro_proof': ('native_unselected_intro_v1' if
                                         snapshot.evidence.get('native_intro_without_selected_slot')
                                         else 'native_factory_save_v1')}
            self.journal.data['bootstrap'] = bootstrap
            self.journal.save()
            self.state = PlaythroughState.MANDATORY_PROLOGUE
        binding = self.journal.data.get('native_binding', {})
        recovered_first_save = (snapshot.save_identity_verified and snapshot.new_save_selected
                                and snapshot.save_identity == binding.get('id')
                                and bootstrap['epoch'] == binding.get('bootstrap_epoch'))
        if bootstrap['session'] != snapshot.session and not recovered_first_save:
            self.state = PlaythroughState.UNSAFE
            self.reason = 'unbound_prologue_session_changed: evidence retained; binding needs reconciliation'
            return
        if (bootstrap['session'] == snapshot.session and snapshot.scene_verified
                and snapshot.pickup_verified and snapshot.actual_mission in ('stg110', 'stg130')
                and snapshot.candidate_clears <= frozenset({'stg110', 'stg130'})):
            self.state = PlaythroughState.MANDATORY_PROLOGUE
        if snapshot.scene == 'save_selection' and snapshot.scene_verified:
            self.state = PlaythroughState.VANILLA_SAVE_SELECTION
        if snapshot.scene in ('global_map', 'world_map', 'game_land_select') and snapshot.scene_verified:
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
        if self.journal.data['save_identity'] is not None:
            if not snapshot.progress_verified:
                return False
            return (self.state in (PlaythroughState.BOUND_PLAYTHROUGH, PlaythroughState.RESUME)
                    and snapshot.save_identity_verified and snapshot.save_identity == self.journal.data['save_identity'])
        bootstrap = self.journal.data.get('bootstrap')
        if not (bootstrap and bootstrap['session'] == snapshot.session):
            return False
        if snapshot.progress_verified:
            return (self.state in (PlaythroughState.MANDATORY_PROLOGUE, PlaythroughState.VANILLA_SAVE_SELECTION)
                    and snapshot.candidate_clears <= frozenset({'stg110','stg130'}))
        # Without an actual selected slot, only first-party scene-local result
        # and pickup evidence from the two *mandatory* intro acts is recordable.
        return (self.state == PlaythroughState.MANDATORY_PROLOGUE
                and snapshot.scene_verified and snapshot.pickup_verified
                and snapshot.stage_epoch is not None
                and snapshot.actual_mission in ('stg110', 'stg130')
                and not snapshot.candidate_clears)

    def can_send(self, snapshot):
        # Server checks are AP-seed-scoped, not Wii-save-scoped. Allow ONLY the
        # corroborated mandatory intro to send its own native results/pickups
        # before slot selection. Persistent world writes still need check().
        if self.journal.data['save_identity'] is None:
            return self.can_record(snapshot)
        return self.can_record(snapshot)

    def can_record_pickups(self, snapshot):
        if not snapshot.scene_verified or not snapshot.pickup_verified or not snapshot.stage_epoch:
            return False
        if self.journal.data['save_identity'] is not None:
            return (self.state in (PlaythroughState.BOUND_PLAYTHROUGH, PlaythroughState.RESUME)
                    and snapshot.save_identity_verified and snapshot.save_identity == self.journal.data['save_identity'])
        bootstrap = self.journal.data.get('bootstrap')
        # Before native save attribution, only the two observed mandatory intro
        # acts are authorized. Loading another save must never inherit this grant.
        return bool(bootstrap and bootstrap['session'] == snapshot.session
                    and self.state == PlaythroughState.MANDATORY_PROLOGUE
                    and snapshot.actual_mission in ('stg110', 'stg130')
                    and snapshot.candidate_clears <= frozenset({'stg110', 'stg130'}))

    def can_send_pickups(self, snapshot):
        return self.can_record_pickups(snapshot)

    def check_stats(self, snapshot):
        # Runtime stats belong to the current living actor, not the save bank.
        # A verified seeded intro is sufficient to deliver filler to that actor;
        # persistent progression writes still require check()'s stronger binding.
        if (not self.can_record_pickups(snapshot) or snapshot.stable_polls < 3
                or snapshot.scene != 'gameplay' or snapshot.death_state != 'alive'
                or snapshot.rings_address is None or snapshot.lives_address is None):
            raise MemoryUnavailable('WRITE_BLOCKED: stats require a stable attributed living actor')
        return snapshot.session, snapshot.stage_epoch, snapshot.actual_mission, snapshot.rings_address, snapshot.lives_address

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
        if snapshot.stable_polls < self.required_polls(snapshot) or not snapshot.scene_verified:
            raise MemoryUnavailable('WRITE_BLOCKED: unstable_context')
        return snapshot.session, snapshot.save_identity, snapshot.scene, snapshot.actual_mission

    def disarm(self):
        self.armed = False
        self.session = None
        self.state = PlaythroughState.DISCONNECTED

    def suspend(self):
        """Stop writes for this observation without destroying attribution."""
        self.armed = False


def live_control_profile(memory, snapshot, guard):
    """Read-only Gecko owner/index pair for a proven seed-local New Game intro.

    Never synthesize a selected save pointer when the native index is invalid.
    Only the exact owner/index equality check in transient C2 controls may use
    this pair; NOT progression, flags, stage records or actual save writes.
    """
    try:
        return memory.resolve_flags_ptr(allow_working=True)
    except MemoryUnavailable:
        trace = snapshot.evidence.get('save_chain_trace', {})
        failure = trace.get('first_failure', {})
        if (failure.get('step') != 'selected_index' or failure.get('reason') != 'index_out_of_range'
                or snapshot.scene != 'gameplay' or snapshot.death_state != 'alive'
                or not snapshot.scene_verified or snapshot.stable_polls < 3
                or guard is None or not guard.can_record_pickups(snapshot)):
            raise MemoryUnavailable('WRITE_BLOCKED: no verified live Gecko intro profile')
        manager, container = memory.resolve_save_container()
        index = memory.read_u8(container)
        step = next((item for item in trace.get('steps', []) if item.get('step') == 'selected_index'), {})
        # PAL can expose different out-of-range transient indices before the
        # first save selection.  Preserve the *actual* native byte, never
        # replace it with a guessed 0xFF and never interpret it as a save slot.
        # A second read must agree with the independent snapshot's chain trace
        # or this particular write is refused (scene/index transition).
        if (not 4 <= index <= 0xFF or step.get('raw') != f'0x{index:02X}'
                or trace.get('chain') is not None):
            raise MemoryUnavailable('WRITE_BLOCKED: no-slot native index changed')
        return (manager, container, index, None, None)


class WritePolicy:
    """Resolve context again for EVERY write; only exact validated fields allowed.

    Production stats and selected permission words have explicit allowlists.
    No CLI switch can turn this policy into an unchecked writer.
    """
    def __init__(self, memory, guard, snapshot_reader):
        self.memory, self.guard, self.snapshot_reader = memory, guard, snapshot_reader

    def __call__(self, operation, address, size):
        if not VERSION['capabilities'].get(operation, False):
            raise MemoryUnavailable(f'WRITE_BLOCKED: requires_verified_hook: {operation}')
        if operation=='native_event_controls':
            self.memory.verify_revision()
            from . import native_events as events
            from .event_controls import owner
            base=events.address(self.memory)
            tx=getattr(self.memory,'_event_transaction',None)
            if not tx or tx['allowed'].get(address)!=size:
                raise MemoryUnavailable('WRITE_BLOCKED: no native event transaction')
            if tx.get('music_loop'):
                from .live_music import finite_loop_policy
                if (address!=base+events.LOOP_CUE or size!=4
                        or tx['value']!=finite_loop_policy(self.memory)):
                    raise MemoryUnavailable('WRITE_BLOCKED: finite music destination changed')
                return ('verified_finite_music_destination',base,tx['value'])
            if tx['disable']:
                if address!=base+events.ENABLE or size!=4 or tx['values'].get(events.ENABLE)!=bytes(4):
                    raise MemoryUnavailable('WRITE_BLOCKED: native event disarm range')
                return ('disarm',base)
            if tx.get('cancel'):
                if address!=base+events.REQUEST or size!=4 or tx['values'].get(events.REQUEST)!=self.memory.read_bytes(base+events.ACK,4):
                    raise MemoryUnavailable('WRITE_BLOCKED: invalid native request cancellation')
                return ('cancel',base)
            snapshot=self.snapshot_reader(self.memory)
            self.guard.check_stats(snapshot);row,player=owner(snapshot)
            context=(snapshot.session,snapshot.stage_epoch,row['stage'],player['actor'],row['player_actor_id'])
            expected={base+events.STAGE:12,base+events.REQUEST:4,base+events.INPUT:4,
                      base+events.ENABLE:4,base+events.REMAINING:4,base+events.TRAP_REQUEST:4}
            if context!=tx['context'] or expected.get(address)!=size:
                raise MemoryUnavailable('WRITE_BLOCKED: native event ownership changed')
            return context
        if operation=='hud_mailbox':
            from .ap_hud_connected import validate
            from .ap_hud_publisher import HOOK
            tx=getattr(self.memory,'_hud_transaction',None)
            if not isinstance(tx,dict) or tx['allowed'].get(address)!=size:
                raise MemoryUnavailable('WRITE_BLOCKED: no authenticated HUD transaction')
            validate(self.memory,tx['owner'])
            if self.memory.read_bytes(HOOK,4)!=tx['hook']:
                raise MemoryUnavailable('WRITE_BLOCKED: HUD publisher changed')
            return (*tx['identity'],tx['owner']['layer'],tx['owner']['handle'],tx['owner']['control'])
        ui_batch=getattr(self.memory,'_game_land_ui_batch',None) if operation=='game_land_ui' else None
        if ui_batch is None:
            verifier=getattr(self.memory,'verify_for_write',None)
            if verifier is None:self.memory.verify_revision()
            else:verifier(operation)
        else:
            from .game_land_ui import validate_batch
            validate_batch(self.memory,ui_batch)
        # The production reader normally verifies the whole executable itself.
        # This policy has JUST done that; use its lean scene/profile snapshot
        # without hashing the same 7 MB twice or rescanning collectible actors.
        # Custom readers retain the ordinary path and full policy verification.
        from .hooks import NativeHooks
        owner = getattr(self.snapshot_reader, '__self__', None)
        if isinstance(owner, NativeHooks) and getattr(self.snapshot_reader, '__func__', None) is NativeHooks.snapshot:
            snapshot = owner._snapshot_after_revision(self.memory)
        else:
            snapshot = self.snapshot_reader(self.memory)
        if operation == 'one_up_controls':
            from .oneup_hook import installed_data
            base=installed_data(self.memory)
            if base is None or base!=getattr(self.memory,'_oneup_allowed',None) or size!=4 or address not in range(base,base+24,4):
                raise MemoryUnavailable('WRITE_BLOCKED: unverified 1-Up control field')
            if self.guard.can_record_pickups(snapshot):
                return snapshot.session,snapshot.stage_epoch,base
            return self.guard.check(snapshot),base
        if operation == 'score_reset':
            from .score_reset import sources
            self.guard.check_stats(snapshot)
            actor,fields,total=sources(self.memory,snapshot)
            tx=getattr(self.memory,'_score_reset_transaction',None)
            context=(snapshot.session,snapshot.stage_epoch,actor)
            if not tx or tx[0]!=context or tx[1].get(address)!=size or address not in fields or len(fields[address])!=size:
                raise MemoryUnavailable('WRITE_BLOCKED: unverified current-stage score transaction')
            return context
        if operation == 'capsule_event_controls':
            from .capsule_capture import installed_data as capture_data,control_context
            tx=getattr(self.memory,'_capsule_event_transaction',None)
            if not tx:raise MemoryUnavailable('WRITE_BLOCKED: no capsule control transaction')
            if tx[0]!=capture_data(self.memory):raise MemoryUnavailable('WRITE_BLOCKED: capsule queue unavailable')
            base,token,fields=tx
            if size!=4 or address-base not in fields:raise MemoryUnavailable('WRITE_BLOCKED: capsule control range')
            if token is None:
                if address!=base+8 or fields[8]!=bytes(4):raise MemoryUnavailable('WRITE_BLOCKED: capsule disarm only')
                return base,None
            if token!=control_context(self.memory,snapshot,self.guard):raise MemoryUnavailable('WRITE_BLOCKED: capsule profile changed')
            return base,token
        if operation == 'oxygen_controls':
            from .oxygen_native import address as oxygen_address,context as oxygen_context
            tx=getattr(self.memory,'_oxygen_transaction',None)
            if not tx or tx[0]!=oxygen_address(self.memory):raise MemoryUnavailable('WRITE_BLOCKED: oxygen mailbox unavailable')
            base,token,fields=tx
            off=address-base
            if off not in fields or len(fields[off])!=size:raise MemoryUnavailable('WRITE_BLOCKED: oxygen policy field')
            if token is None:
                if off!=4 or fields[off]!=bytes(4):raise MemoryUnavailable('WRITE_BLOCKED: oxygen disable only')
                return base,None
            if token!=oxygen_context(self.memory,snapshot,self.guard):raise MemoryUnavailable('WRITE_BLOCKED: oxygen save changed')
            return base,token
        if operation == 'breath_timer':
            from .water_native import target
            player,clock=target(self.memory,snapshot,self.guard)
            tx=getattr(self.memory,'_breath_transaction',None)
            if tx is None or size!=4 or (player,clock['plugin'])!=tx[:2] or address!=clock['elapsed_address']:
                raise MemoryUnavailable('WRITE_BLOCKED: oxygen plugin ownership changed')
            return snapshot.session,snapshot.stage_epoch,player,clock['plugin']
        if operation == 'game_land_notice':
            from .game_land_notice import owner
            self.guard.check(snapshot)
            tx=getattr(self.memory,'_game_land_notice_transaction',None)
            if tx is None or size!=4 or address not in tx[3]:
                raise MemoryUnavailable('WRITE_BLOCKED: no bounded Game Land event transaction')
            context,count=owner(self.memory,snapshot)
            if context!=tx[0] or self.memory.resolve_flags_ptr()!=tx[1] or count not in (tx[2],tx[2]+1):
                raise MemoryUnavailable('WRITE_BLOCKED: Game Land event owner changed')
            return (context,tx[1],tx[2],tuple(tx[3].items()))
        if operation == 'physical_ring_collection':
            from .physical_rings import targets
            allowed, context = targets(self.memory, snapshot, self.guard)
            if address not in allowed or size != allowed[address][0]:
                raise MemoryUnavailable('WRITE_BLOCKED: no witnessed physical ring at this address')
            return context, allowed[address][1]
        if operation == 'experimental_code':
            # ONLY reachable through the explicit, dangerous --experimental-direct-hooks
            # launcher switch, with a complete exact-address write plan.
            txn = getattr(self.memory, '_direct_hook_transaction', None)
            if not isinstance(txn, dict) or address not in txn:
                raise MemoryUnavailable('WRITE_BLOCKED: no explicit experimental PPC plan')
            before, after = txn[address]
            if size != len(before) or len(before) != len(after):
                raise MemoryUnavailable('WRITE_BLOCKED: experimental PPC size mismatch')
            return 'opt_in_experimental_ppc', address, len(before)
        if operation == 'music_bank':
            import hashlib
            from .live_music import ORIGINAL_SIZE, probe_bank
            txn = getattr(self.memory, '_music_bank_transaction', None)
            if not isinstance(txn, tuple) or len(txn) != 3:
                raise MemoryUnavailable('WRITE_BLOCKED: no authenticated CSB transaction')
            bank, current, expected = txn
            if address != bank or size != ORIGINAL_SIZE or size % 4:
                raise MemoryUnavailable('WRITE_BLOCKED: CSB write range not authorized')
            observed_bank, raw, _ = probe_bank(self.memory)
            if observed_bank != bank or hashlib.sha256(raw).hexdigest() not in (current, expected):
                raise MemoryUnavailable('WRITE_BLOCKED: native CSB bank changed during transaction')
            return 'verified_native_pal_music_bank', bank, current, expected
        if operation == 'intro_box_placement':
            from .intro_box import locate
            if (snapshot.stable_polls < 3 or not self.guard.can_record_pickups(snapshot)):
                raise MemoryUnavailable('WRITE_BLOCKED: intro box playthrough not attributed')
            base, target, actors = locate(self.memory, snapshot)
            if size != 4 or address != target or actors:
                raise MemoryUnavailable('WRITE_BLOCKED: intro box must precede native construction')
            return snapshot.session, snapshot.stage_epoch, base, target
        if operation in ('emerald_ui','game_land_ui'):
            from .emerald_ui import targets
            if snapshot.scene!='game_land_select' or not snapshot.scene_verified:
                raise MemoryUnavailable('WRITE_BLOCKED: Emerald UI requires verified Game Land menu')
            token=self.guard.check(snapshot)
            fields=ui_batch['fields'] if ui_batch is not None else (targets(self.memory,stages=True) if operation=='game_land_ui' else targets(self.memory))
            if size!=4 or address not in fields:
                raise MemoryUnavailable('WRITE_BLOCKED: unowned Emerald UI field')
            return token,address,fields[address]
        if operation in ('stunts','drill_turbo','hover_ring_dash'):
            if operation=='hover_ring_dash':
                from .hover_ring_dash import installed_data
            elif operation=='drill_turbo':
                from .drill_turbo import installed_data
            else:
                from .stunts import installed_data
            base=installed_data(self.memory)
            if base is None or size!=4 or address!=base:
                raise MemoryUnavailable('WRITE_BLOCKED: unverified Stunts permission data')
            # Same ephemeral gameplay authority as Movement: the mandatory
            # prologue has a verified living Sonic before persistent save bind.
            if (snapshot.scene=='gameplay' and snapshot.scene_verified
                    and snapshot.death_state=='alive' and snapshot.stable_polls>=1
                    and self.guard.can_record_pickups(snapshot)):
                from .movement_gate import observed
                stage=next(iter(snapshot.evidence.get('native_data',{}).get('stage_objects',[])),{})
                player=stage.get('player',{}).get('actor')
                if player is None:raise MemoryUnavailable('WRITE_BLOCKED: Stunts actor unavailable')
                machine=observed(self.memory,player)['request_machine']
                return ('verified ephemeral Stunts owner; no persistent save writes',snapshot.session,snapshot.stage_epoch,machine,base)
            return self.guard.check(snapshot),base
        if operation == 'wisp_inventory':
            from .wisp_inventory import owner
            tx=getattr(self.memory,'_wisp_inventory_transaction',None)
            context=owner(self.memory,snapshot,self.guard)
            if (not tx or tx['owner']!=context or (address,size) not in
                    ((context[4]+0xc,0x1c),(context[4]+0x60,4))):
                raise MemoryUnavailable('WRITE_BLOCKED: Wisp inventory owner/address changed')
            return context
        if operation == 'assist_change':
            from .player_switch import installed_data
            base=installed_data(self.memory)
            if base is None or size!=4 or address!=base:
                raise MemoryUnavailable('WRITE_BLOCKED: unverified Assist Change data')
            token=self.guard.check(snapshot)
            return token,base
        if operation in ('movement_controls','skydiving','quick_step'):
            from .movement_gate import installed_data, observed
            if operation == 'quick_step':
                from .quick_step import installed_data as quick_data
                address_base=quick_data(self.memory)
                match=(address_base,'Gecko') if address_base is not None else None
            elif operation == 'skydiving':
                from .skydiving import installed_data as sky_data
                address_base=sky_data(self.memory)
                match=(address_base,'Gecko') if address_base is not None else None
            else:
                match = installed_data(self.memory)
            if match is None:
                raise MemoryUnavailable('WRITE_BLOCKED: movement hook missing')
            base, transport = match
            if size != 4 or address not in ((base,) if operation in ('skydiving','quick_step') else (base, base + 4)):
                raise MemoryUnavailable('WRITE_BLOCKED: unverified movement data word')
            if (snapshot.scene in ('world_map','global_map','game_land_select')
                    and snapshot.scene_verified and snapshot.stable_polls>=1):
                # Actor-free permission words only. Persistent binding must
                # match this snapshot; a cached save or unknown scene cannot
                # authorize menu preloading. Guest verifies the next owner.
                return self.guard.check(snapshot), snapshot.session, base
            if (snapshot.scene != 'gameplay' or snapshot.death_state != 'alive'
                    or not snapshot.scene_verified or snapshot.stable_polls < 1
                    or not (snapshot.progress_verified or self.guard.can_record_pickups(snapshot))):
                raise MemoryUnavailable('WRITE_BLOCKED: movement gate requires attributed living player')
            stage = next(iter(snapshot.evidence.get('native_data',{}).get('stage_objects',[])),{})
            player = stage.get('player',{}).get('actor')
            if player is None:
                raise MemoryUnavailable('WRITE_BLOCKED: movement actor unavailable')
            ctrl = observed(self.memory, player)['request_machine']
            return ('verified ephemeral PAL Sonic movement owner; no persistent save writes', ctrl, base)
        if operation in ('progression_data','progression_reset','gameplay_controls','capsule_controls') and snapshot.save_identity is None:
            token = self.guard.check_stats(snapshot)
        else:
            token = self.guard.check_stats(snapshot) if operation in ('stats', 'boost_stats', 'colour_permissions') else self.guard.check(snapshot)
        if operation not in ('global_map_refresh', 'permission_bits', 'map_availability', 'map_lock', 'music_cues', 'progression_data', 'progression_reset', 'gameplay_controls', 'egg_medal_controls', 'capsule_controls') and (snapshot.scene != 'gameplay' or snapshot.death_state != 'alive'):
            raise MemoryUnavailable('WRITE_BLOCKED: unsafe_scene')
        if operation == 'global_map_refresh':
            from .map_refresh import installed_data
            from .native_read import read_actors
            if snapshot.scene != 'global_map':
                raise MemoryUnavailable('WRITE_BLOCKED: refresh requires Grand World Map')
            data = installed_data(self.memory)
            context = snapshot.evidence['native_data']['stage_objects'][0]['context']
            actors = tuple(p for p in read_actors(self.memory, context) if self.memory.read_u32(p) == 0x80777000)
            if len(actors) != 1 or data is None or size != 4 or address not in range(data, data+16, 4):
                raise MemoryUnavailable('WRITE_BLOCKED: map refresh owner/address changed')
            chain = self.memory.resolve_flags_ptr()
            if tuple(snapshot.evidence.get('chain', ())) != chain:
                raise MemoryUnavailable('WRITE_BLOCKED: map refresh save changed')
            return token, data, actors, chain
        elif operation == 'stats':
            allowed = {snapshot.rings_address, snapshot.lives_address, snapshot.ring_mirror_address, snapshot.world_lives_address}
        elif operation == 'boost_stats':
            allowed = {snapshot.boost_address} - {None}
            if (snapshot.boost_address is None or snapshot.boost_max_address != snapshot.boost_address + 12
                    or self.memory.read_u32(snapshot.boost_address - 8) != 0x80763A18):
                raise MemoryUnavailable('WRITE_BLOCKED: boost model changed')
            token = (*token, snapshot.boost_address, snapshot.boost_max_address,
                     self.memory.read_u32(snapshot.boost_max_address))
        elif operation == 'capsule_controls':
            from .capsule_refresh import installed_data
            data = installed_data(self.memory)
            chain = live_control_profile(self.memory, snapshot, self.guard)
            if (snapshot.evidence.get('chain') is not None
                    and tuple(snapshot.evidence['chain']) != chain) or data is None:
                raise MemoryUnavailable('WRITE_BLOCKED: White capsule control profile changed')
            if size != 4 or address not in range(data, data+12, 4):
                raise MemoryUnavailable('WRITE_BLOCKED: White capsule control address not allowed')
            return token, chain, data
        elif operation == 'egg_medal_controls':
            from .medal_hook import installed_data
            data = installed_data(self.memory)
            chain = self.memory.resolve_flags_ptr()
            if tuple(snapshot.evidence.get('chain', ())) != chain or data is None:
                raise MemoryUnavailable('WRITE_BLOCKED: medal capture profile changed')
            if size != 4 or address not in range(data, data+self.memory.medal_data_size, 4):
                raise MemoryUnavailable('WRITE_BLOCKED: medal capture address not allowed')
            return token, chain, data
        elif operation == 'gameplay_controls':
            from .gameplay_controls import HOOKS, installed
            chain = live_control_profile(self.memory, snapshot, self.guard)
            if (snapshot.evidence.get('chain') is not None
                    and tuple(snapshot.evidence['chain']) != chain):
                raise MemoryUnavailable('WRITE_BLOCKED: gameplay control profile changed')
            data = [installed(self.memory, kind) for kind in HOOKS]
            if size != 4 or not any(d is not None and address in range(d, d+self.memory.gameplay_data_sizes.get(d,20), 4) for d in data):
                raise MemoryUnavailable('WRITE_BLOCKED: gameplay control address not allowed')
            return token, chain, tuple(data)
        elif operation in ('progression_data','progression_reset'):
            from .progression_hook import installed_data
            data = installed_data(self.memory)
            chain = self.memory.resolve_flags_ptr(allow_working=True)
            if operation == 'progression_reset':
                allowed_data = (data+12,data+16) if data is not None and self.memory.read_u32(data)==0 else ()
            else:
                allowed_data = ((data,data+4,data+8,data+20) + ((data+24,data+28) if self.memory.story_permissions_installed else ())) if data is not None else ()
            if data is None or size != 4 or address not in allowed_data:
                raise MemoryUnavailable('WRITE_BLOCKED: progression data address not allowed')
            if tuple(snapshot.evidence.get('chain',())) != chain:
                raise MemoryUnavailable('WRITE_BLOCKED: progression data save owner changed')
            return token, data, chain
        elif operation == 'music_cues':
            if snapshot.scene not in ('world_map','global_map','game_land_select'):
                raise MemoryUnavailable('WRITE_BLOCKED: music redirects require a stable stage-selection scene')
            from .music import cue_records
            table, vector, count, records = cue_records(self.memory)
            if size != 32 or address not in records.values():
                raise MemoryUnavailable('WRITE_BLOCKED: music cue address not allowed')
            return token, table, vector, count
        elif operation == 'colour_permissions':
            stage = snapshot.evidence.get('native_data', {}).get('stage_objects', [{}])[0]
            allowed = {stage.get('stage', 0) + 0x61, stage.get('actor_state', 0) + 0x90}
            if size != 1 or address not in allowed:
                raise MemoryUnavailable('WRITE_BLOCKED: colour_permission_address_not_allowed')
            return token
        elif operation in ('map_availability','map_lock'):
            if snapshot.scene != 'world_map':
                raise MemoryUnavailable('WRITE_BLOCKED: map availability requires world map')
            access = snapshot.evidence.get('native_data', {}).get('stage_objects', [{}])[0].get('world_map_access', {})
            allowed = {access.get('status_address')} | {node['address'] for node in access.get('nodes', ())}
            if operation == 'map_lock':
                flags = self.memory.resolve_flags_ptr()[-1]
                from ..world_constants import STAGES, load_data
                node = next((n for n in access.get('nodes', ()) if n['address'] == address), None)
                if node:
                    stage = next(s for s in STAGES if s['zone_index'] == access['zone'] and s['slot'] == node['slot'])
                    bit = int(next(r['bank_A'] for r in load_data('progress_bits.json') if r['mission'] == stage['mission_id']))
                    authorized = self.memory.read_progress_bit(flags, bit)
                else:
                    authorized = self.memory.read_progress_bit(flags,20+access['zone']) if access else True
                if not access or authorized:
                    raise MemoryUnavailable('WRITE_BLOCKED: cannot lock an authorized world')
        elif operation == 'permission_bits':
            from ..world_progression import verified_result_clear
            if (snapshot.scene not in ('gameplay', 'world_map', 'global_map', 'game_land_select')
                    and verified_result_clear(snapshot) is None):
                raise MemoryUnavailable('WRITE_BLOCKED: unsafe permission scene')
            flags = self.memory.resolve_flags_ptr()[-1]
            if tuple(snapshot.evidence.get('chain', ())) != self.memory.resolve_flags_ptr():
                raise MemoryUnavailable('WRITE_BLOCKED: save_chain_changed')
            # Only words containing World, starting-act, Super/entry and Game Land gate bits.
            allowed = {flags + 0x10 + offset * 4 for offset in (0, 1, 2, 6, 7)}
        else:
            raise MemoryUnavailable('WRITE_BLOCKED: operation has no reviewed address allowlist')
        if size != 4 or address % 4 or address not in allowed:
            raise MemoryUnavailable('WRITE_BLOCKED: address_not_allowed')
        return token
