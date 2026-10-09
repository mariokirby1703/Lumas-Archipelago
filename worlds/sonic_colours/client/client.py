import asyncio
import hashlib
import json
from pathlib import Path
import time
from datetime import datetime, timezone

import Utils
from CommonClient import ClientCommandProcessor, CommonContext, gui_enabled, logger, server_loop
from NetUtils import ClientStatus
from websockets.exceptions import ConnectionClosed
from ..world_constants import GAME
from ..Items import BY_ID
from .diagnostics import diagnostic
from .hooks import NativeHooks
from .journal import Journal
from .memory import DMEBackend, SonicMemory, MemoryUnavailable
from .runtime import Runtime, validate_slot, inventory
from .state import SaveGuard, WritePolicy
from .versions import VERSION
from .deathlink import DeathLink
from .build_info import implementation_info
from .status import StatusReporter


class SonicCommands(ClientCommandProcessor):
    def _cmd_sonicnewgame(self):
        """Optional New Game confirmation; native detection is automatic and freshness is still required."""
        if not self.ctx.runtime:
            logger.info('Connect to your Sonic Colours (Wii) seed first.')
            return
        try:
            self.ctx.runtime.guard.confirm_new_game()
            logger.info(self.ctx.runtime.guard.reason)
        except MemoryUnavailable as error:
            logger.error(str(error))

    def _cmd_sonic(self):
        """Show inventory, synchronization and PAL hook status."""
        logger.info(json.dumps(diagnostic(self.ctx), indent=2))

    def _cmd_sonicstatus(self):
        """Show current connection and write-block reason."""
        self._cmd_sonic()

    def _cmd_sonicdebug(self):
        """Inspect the small candidate pointer chain; never dumps whole RAM."""
        logger.info(json.dumps(diagnostic(self.ctx, self.ctx.memory), indent=2))

    def _cmd_sonicitems(self):
        """Show durable per-receipt delivery and reconciliation details."""
        if self.ctx.runtime:
            logger.info(json.dumps(self.ctx.runtime.item_details(), indent=2))
        else:
            logger.info('Connect to your Sonic Colours slot first.')

    def _cmd_sonicrecover(self, action='', index=''):
        """skip INDEX marks an uncertain effect consumed without replaying it."""
        if action != 'skip' or not index.isdecimal() or not self.ctx.runtime:
            logger.info('Usage: /sonicrecover skip INDEX. Skips an uncertain effect; never credits it twice.')
            return
        try:
            self.ctx.runtime.journal.recover_skip(int(index))
        except (KeyError, ValueError, OSError) as error:
            logger.error('Recovery failed: %s', error)
            return
        logger.info('Receipt %s skipped durably.', index)


class SonicContext(CommonContext):
    game = GAME
    items_handling = 0b111
    command_processor = SonicCommands

    def __init__(self, address=None, password=None, patch_file=None, journal_directory=None):
        super().__init__(address, password)
        self.runtime = None
        self.deathlink = None
        self.memory = None
        self.history_ready = False
        self.history_desynced = False
        self.barrier = None
        self.dolphin_status = 'Waiting for Dolphin and AP slot.'
        self.server_seed = None
        self.authenticated_identity = None
        self.operation_status = {}
        self.expected_seed = None
        self.expected_slot_data = None
        self.last_send = 0.0
        self.last_pending = set()
        self.implementation = implementation_info()
        self.latest_acknowledged_location = None
        self.status_time_utc = None
        self.dolphin_instance = None
        self.last_observed_checked = set()
        self.journal_directory = Path(journal_directory or Utils.user_path('sonic_colours_journals'))
        if patch_file:
            patch = json.loads(Path(patch_file).read_text(encoding='utf-8'))
            if patch.get('game') != GAME:
                raise ValueError('Expected a Sonic Colours (Wii) v2 .apsonic file; regenerate old seeds/files.')
            self.expected_slot_data = validate_slot(patch['slot_data'])
            self.expected_seed = self.expected_slot_data['seed_name']
            self.auth = patch.get('player_name')

    async def server_auth(self, password_requested=False):
        if password_requested and not self.password:
            await super().server_auth(password_requested)
        if not self.auth:
            await self.get_username()
        await self.send_connect(game=GAME)

    def release_runtime(self):
        if self.runtime:
            self.runtime.guard.disarm()
            self.runtime.journal.close()
        self.runtime = None
        self.deathlink = None

    def on_deathlink(self, data):
        super().on_deathlink(data)
        if self.deathlink:
            self.deathlink.receive(data, time.monotonic())

    def on_package(self, cmd, args):
        if cmd == 'RoomInfo':
            self.authenticated_identity = None
            seed = args.get('seed_name')
            self.server_seed = seed if isinstance(seed, str) and seed else None
        elif cmd == 'Connected':
            self.history_ready = False
            self.history_desynced = False
            self.locations_checked = set()
            self.finished_game = False
            self.last_pending = set()
            self.last_observed_checked = set()
            self.latest_acknowledged_location = None
            try:
                data = validate_slot(args['slot_data'])
                if self.expected_slot_data and data != self.expected_slot_data:
                    raise ValueError('server slot data differs from loaded .apsonic file')
                if not self.server_seed:
                    raise ValueError('Connected requires a valid preceding RoomInfo server seed')
                if data['seed_name'] != self.server_seed:
                    raise ValueError(f'RoomInfo/Connected seed mismatch: team={self.team!r} slot={self.slot!r} server_seed={self.server_seed!r} slot_seed={data["seed_name"]!r}')
                self.authenticated_identity = (self.team, self.slot, self.server_seed)
                identity = {'seed': self.server_seed, 'team': self.team, 'slot': self.slot,
                            'revision': VERSION['dol_sha256'], 'game': GAME,
                            'slot_digest': hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()}
                if not self.runtime or self.runtime.journal.identity != identity:
                    self.release_runtime()
                    journal = Journal(self.journal_directory, identity)
                    self.runtime = Runtime(data, journal, SaveGuard(journal), NativeHooks(journal))
                    if data['options']['death_link']:
                        self.deathlink = DeathLink(journal)
                asyncio.create_task(self.update_death_link(bool(data['options']['death_link'])))
                # CommonClient processes packets in order. An ordered Get reply
                # handles AP's omitted empty ReceivedItems without a timeout guess.
                self.barrier = f'_sonic_history_{time.monotonic_ns()}'
                asyncio.create_task(self.send_msgs([{'cmd': 'Get', 'keys': [self.barrier]}]))
                logger.warning('Sonic Colours (Wii) slot connected. For a new seed choose New Game; '
                               'the client detects the mandatory intro automatically. Intro evidence is retained until a verified save binding; '
                               '/sonicdebug shows individual native proof gaps.')
            except (ValueError, KeyError, OSError) as error:
                self.authenticated_identity = None
                self.release_runtime()
                self.dolphin_status = f'Slot rejected: {error}'
                logger.error(self.dolphin_status)
        elif cmd == 'ReceivedItems':
            index = args.get('index', -1)
            if index == 0:
                self.history_ready, self.history_desynced = True, False
            elif index + len(args.get('items', [])) != len(self.items_received):
                self.history_ready, self.history_desynced = False, True
            if self.runtime and self.history_ready:
                try:
                    inventory([i.item for i in self.items_received])
                    previous = len(self.runtime.journal.data['receipts'])
                    self.runtime.journal.record_history([i.item for i in self.items_received])
                    for index in range(previous, len(self.items_received)):
                        logger.info('Item received / queued: receipt %s, %s', index, BY_ID[self.items_received[index].item])
                except (ValueError, OSError) as error:
                    self.history_ready = False
                    self.history_desynced = True
                    logger.error('Receipt synchronization blocked: %s', error)
        elif cmd == 'Retrieved' and self.barrier in args.get('keys', {}) and not self.history_desynced:
            self.history_ready = True
        if cmd in ('Connected', 'RoomUpdate'):
            # CommonContext has already applied missing_locations before invoking
            # this callback. Only server-confirmed locations are acknowledgements.
            newly_checked = self.checked_locations - self.last_observed_checked
            if newly_checked:
                self.latest_acknowledged_location = {
                    'time_utc': datetime.now(timezone.utc).isoformat(),
                    'locations': sorted(newly_checked), 'packet': cmd}
                logger.info('Location acknowledged: %s', sorted(newly_checked))
            if self.runtime:
                self.runtime.journal.acknowledge(self.checked_locations)
            self.last_observed_checked = set(self.checked_locations)

    def reset_server_state(self):
        # Keep the already authenticated seed's native observer while offline.
        # Reconnecting to another identity replaces it in Connected, before sends.
        super().reset_server_state()
        self.server_seed = None
        self.authenticated_identity = None
        self.history_ready = False
        self.history_desynced = False
        self.barrier = None

    def make_gui(self):
        from kvui import GameManager

        class SonicManager(GameManager):
            base_title = 'Sonic Colours (Wii) PAL — ' + self.implementation['loaded_code_id'][:12]
            logging_pairs = [('Client', 'Archipelago')]

        return SonicManager


async def transmit_checks(ctx, checks=(), goal=False):
    """Send earned durable checks even if Dolphin is stopped or history pending."""
    if not ctx.runtime:
        return
    if ctx.runtime.journal.persistence_pending:
        ctx.operation_status['journal_persistence'] = 'retrying failed journal persistence; transport held'
        ctx.runtime.journal.save()
        ctx.operation_status['journal_persistence'] = 'durable journal persistence retry succeeded'
    if not ctx.server or ctx.slot is None:
        ctx.operation_status['ap_transport'] = 'offline; durable queue retained'
        return
    earned = set(checks) | set(ctx.runtime.journal.data['checks'])
    pending = earned - ctx.checked_locations
    if not pending and not (goal and not ctx.finished_game):
        ctx.operation_status['ap_transport'] = 'idle: no pending checks or goal'
        return
    identity = ctx.runtime.journal.identity
    expected = (identity['team'], identity['slot'], identity['seed'])
    actual = ctx.authenticated_identity
    if actual != expected or actual != (ctx.team, ctx.slot, ctx.server_seed):
        message = ('Location transport identity mismatch: journal team=%r slot=%r seed=%r; '
                   'authenticated=%r; current team=%r slot=%r server seed=%r' %
                   (*expected, actual, ctx.team, ctx.slot, ctx.server_seed))
        ctx.operation_status['ap_transport'] = message
        raise MemoryUnavailable(message)
    if pending and (pending != ctx.last_pending or time.monotonic() - ctx.last_send >= 5):
        await ctx.send_msgs([{'cmd': 'LocationChecks', 'locations': sorted(pending)}])
        logger.info('LocationChecks sent: %s', sorted(pending))
        ctx.last_pending, ctx.last_send = pending.copy(), time.monotonic()
        ctx.operation_status['ap_transport'] = 'sent; awaiting server acknowledgement'
    if goal and not ctx.finished_game:
        await ctx.send_msgs([{'cmd': 'StatusUpdate', 'status': ClientStatus.CLIENT_GOAL}])
        ctx.finished_game = True


async def dolphin_loop(ctx):
    try:
        import dolphin_memory_engine as dolphin
    except ImportError:
        ctx.dolphin_status = 'DME missing: install worlds/sonic_colours/requirements.txt'
        logger.error(ctx.dolphin_status)
        while not ctx.exit_event.is_set():
            try:
                await transmit_checks(ctx)
            except (MemoryUnavailable, ConnectionClosed, OSError, RuntimeError) as error:
                logger.debug('Pending check transport: %s', error)
            await asyncio.sleep(1)
        return
    backend = DMEBackend(dolphin)
    logger.info('Sonic implementation: %s', json.dumps(ctx.implementation, sort_keys=True))
    ctx.memory = memory = SonicMemory(backend)
    verified = False
    status_reporter = StatusReporter()
    try:
        while not ctx.exit_event.is_set():
            checks, goal = set(), False
            started = time.monotonic()
            try:
                if not dolphin.is_hooked():
                    verified = False
                    backend.close()
                    if ctx.runtime:
                        ctx.runtime.hooks.invalidate_session()
                    dolphin.hook()
                ctx.dolphin_instance = backend.instance_info()
                if not backend.active():
                    verified = False
                    if ctx.runtime:
                        ctx.runtime.guard.disarm()
                        ctx.runtime.hooks.invalidate_session()
                    raise MemoryUnavailable('Waiting for running Dolphin emulation.')
                if not verified:
                    memory.verify_revision()
                    verified = True
                if not ctx.runtime:
                    raise MemoryUnavailable('PAL executable verified; waiting for AP slot.')
                memory.write_guard = WritePolicy(memory, ctx.runtime.guard, ctx.runtime.hooks.snapshot)
                checks, goal = ctx.runtime.poll(memory, [i.item for i in ctx.items_received], ctx.history_ready)
                if ctx.deathlink:
                    snap = ctx.runtime.snapshot
                    if VERSION['capabilities']['native_death']:
                        local_death = ctx.deathlink.poll(
                            safe=ctx.runtime.guard.can_send(snap) and snap.scene_verified and snap.scene in ('gameplay', 'dying'),
                            native_state=snap.death_state, now=time.monotonic(),
                            kill=lambda: ctx.runtime.hooks.kill(memory, snap))
                        if local_death:
                            await ctx.send_death('Sonic died.')
                # Runtime returns durable checks only after current attribution
                # is valid. Do not bypass its identity gate by rereading journal.
                snap = ctx.runtime.snapshot
                ctx.operation_status.update(
                    gameplay_detection={'scene': snap.scene, 'mission': snap.actual_mission, 'verified': snap.scene_verified},
                    pickup_detection={'verified': snap.pickup_verified, 'authorized': ctx.runtime.guard.can_record_pickups(snap)},
                    journal_persistence={'durable_events': len(ctx.runtime.journal.data['pickup_events']), 'earned_checks': len(ctx.runtime.journal.data['checks']), 'persistence_pending': ctx.runtime.journal.persistence_pending},
                    item_writes={'history_ready': ctx.history_ready, 'pending_receipts': ctx.runtime.pending_effects(), 'status': ctx.runtime.last_error})
                ctx.dolphin_status = ctx.runtime.guard.reason
            except MemoryUnavailable as error:
                ctx.dolphin_status = str(error)
                ctx.operation_status['gameplay_detection'] = str(error)
                if ctx.runtime:
                    ctx.runtime.snapshot = None
                    ctx.runtime.guard.disarm()
                if str(error).startswith(('wrong_game', 'unknown_revision')):
                    verified = False
                    if ctx.runtime:
                        ctx.runtime.hooks.invalidate_session()
            except ConnectionClosed:
                ctx.dolphin_status = 'AP disconnected; synchronization stopped.'
                if ctx.runtime:
                    ctx.runtime.snapshot = None
                    ctx.runtime.guard.disarm()
            except (OSError, RuntimeError, ValueError) as error:
                ctx.dolphin_status = f'Synchronization blocked: {error}'
                verified = False
                backend.close()
                if ctx.runtime:
                    ctx.runtime.snapshot = None
                    ctx.runtime.guard.disarm()
            try:
                await transmit_checks(ctx, checks, goal)
            except (ConnectionClosed, MemoryUnavailable, OSError) as error:
                ctx.operation_status['ap_transport'] = f'Location transmission pending: {error}'
            if status_reporter.ready(ctx.dolphin_status, time.monotonic()):
                ctx.status_time_utc = datetime.now(timezone.utc).isoformat()
                logger.info('Current Dolphin status [%s, instance=%s]: %s', ctx.status_time_utc,
                            json.dumps(ctx.dolphin_instance, sort_keys=True), ctx.dolphin_status)
            # Five-bit masks persist through normal gameplay, so bulk bit changes
            # capture multiple rings. Sample promptly; capsule pulses will need a
            # native retained event source, not an assumption about this interval.
            await asyncio.sleep(max(0.001, 0.02 - (time.monotonic() - started)) if backend.active() else 1)
    finally:
        backend.close()
        ctx.memory = None
        if dolphin.is_hooked():
            dolphin.un_hook()


async def main(args):
    ctx = SonicContext(args.connect, args.password, args.patch_file)
    ctx.auth = args.name or ctx.auth
    ctx.server_task = asyncio.create_task(server_loop(ctx), name='ServerLoop')
    if gui_enabled and not getattr(args, 'nogui', False):
        ctx.run_gui()
    ctx.run_cli()
    watcher = asyncio.create_task(dolphin_loop(ctx), name='SonicDolphin')
    try:
        await ctx.exit_event.wait()
    finally:
        ctx.exit_event.set()
        await watcher
        ctx.release_runtime()
        await ctx.shutdown()
