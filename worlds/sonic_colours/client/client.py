import asyncio
import hashlib
import json
from pathlib import Path
import time

import Utils
from CommonClient import ClientCommandProcessor, CommonContext, gui_enabled, logger, server_loop
from NetUtils import ClientStatus
from websockets.exceptions import ConnectionClosed
from ..world_constants import GAME
from .diagnostics import diagnostic
from .hooks import NativeHooks
from .journal import Journal
from .memory import DMEBackend, SonicMemory, MemoryUnavailable
from .runtime import Runtime, validate_slot, inventory
from .state import SaveGuard, WritePolicy
from .versions import VERSION
from .deathlink import DeathLink


class SonicCommands(ClientCommandProcessor):
    def _cmd_sonicnewgame(self):
        """Confirm New Game intent. Native menu/freshness evidence is also required."""
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
        self.expected_seed = None
        self.expected_slot_data = None
        self.last_send = 0.0
        self.last_pending = set()
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
        if cmd == 'Connected':
            self.release_runtime()
            self.history_ready = False
            self.history_desynced = False
            self.locations_checked = set()
            self.finished_game = False
            self.last_pending = set()
            try:
                data = validate_slot(args['slot_data'])
                if self.expected_slot_data and data != self.expected_slot_data:
                    raise ValueError('server slot data differs from loaded .apsonic file')
                if self.seed_name and data['seed_name'] != self.seed_name:
                    raise ValueError('RoomInfo and slot seed identity mismatch')
                identity = {'seed': data['seed_name'], 'team': self.team, 'slot': self.slot,
                            'revision': VERSION['dol_sha256'], 'game': GAME,
                            'slot_digest': hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()}
                journal = Journal(self.journal_directory, identity)
                self.runtime = Runtime(data, journal, SaveGuard(journal), NativeHooks())
                if data['options']['death_link']:
                    self.deathlink = DeathLink(journal)
                asyncio.create_task(self.update_death_link(bool(data['options']['death_link'])))
                # CommonClient processes packets in order. An ordered Get reply
                # handles AP's omitted empty ReceivedItems without a timeout guess.
                self.barrier = f'_sonic_history_{time.monotonic_ns()}'
                asyncio.create_task(self.send_msgs([{'cmd': 'Get', 'keys': [self.barrier]}]))
                logger.warning('Sonic Colours (Wii) slot connected. For a new seed choose New Game and '
                               '/sonicnewgame. Intro evidence is retained until a verified save binding; '
                               '/sonicdebug shows individual native proof gaps.')
            except (ValueError, KeyError, OSError) as error:
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
                    self.runtime.journal.record_history([i.item for i in self.items_received])
                except (ValueError, OSError) as error:
                    self.history_ready = False
                    self.history_desynced = True
                    logger.error('Receipt synchronization blocked: %s', error)
        elif cmd == 'Retrieved' and self.barrier in args.get('keys', {}) and not self.history_desynced:
            self.history_ready = True

    def reset_server_state(self):
        self.release_runtime()
        super().reset_server_state()
        self.history_ready = False
        self.history_desynced = False
        self.barrier = None

    def make_gui(self):
        from kvui import GameManager

        class SonicManager(GameManager):
            base_title = 'Sonic Colours (Wii) Client (PAL development build)'
            logging_pairs = [('Client', 'Archipelago')]

        return SonicManager


async def dolphin_loop(ctx):
    try:
        import dolphin_memory_engine as dolphin
    except ImportError:
        ctx.dolphin_status = 'DME missing: install worlds/sonic_colours/requirements.txt'
        logger.error(ctx.dolphin_status)
        return
    backend = DMEBackend(dolphin)
    ctx.memory = memory = SonicMemory(backend)
    verified = False
    last_status = None
    try:
        while not ctx.exit_event.is_set():
            try:
                if not dolphin.is_hooked():
                    verified = False
                    backend.close()
                    if ctx.runtime:
                        ctx.runtime.hooks.invalidate_session()
                    dolphin.hook()
                if not backend.active():
                    verified = False
                    if ctx.runtime:
                        ctx.runtime.guard.disarm()
                        ctx.runtime.hooks.invalidate_session()
                    raise MemoryUnavailable('Waiting for running Dolphin emulation.')
                if not verified:
                    memory.verify_revision()
                    verified = True
                if not ctx.runtime or not ctx.server or ctx.slot is None:
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
                pending = checks - ctx.checked_locations
                if pending and (pending != ctx.last_pending or time.monotonic() - ctx.last_send >= 5):
                    await ctx.send_msgs([{'cmd': 'LocationChecks', 'locations': sorted(pending)}])
                    ctx.last_pending, ctx.last_send = pending.copy(), time.monotonic()
                if goal and not ctx.finished_game:
                    await ctx.send_msgs([{'cmd': 'StatusUpdate', 'status': ClientStatus.CLIENT_GOAL}])
                    ctx.finished_game = True
                ctx.dolphin_status = ctx.runtime.last_error or 'PAL synchronization active.'
            except MemoryUnavailable as error:
                ctx.dolphin_status = str(error)
                if str(error).startswith(('wrong_game', 'unknown_revision')):
                    verified = False
            except ConnectionClosed:
                ctx.dolphin_status = 'AP disconnected; synchronization stopped.'
                if ctx.runtime:
                    ctx.runtime.guard.disarm()
            except (OSError, RuntimeError, ValueError) as error:
                ctx.dolphin_status = f'Synchronization blocked: {error}'
                verified = False
                backend.close()
                if ctx.runtime:
                    ctx.runtime.guard.disarm()
            if ctx.dolphin_status != last_status:
                logger.info(ctx.dolphin_status)
                last_status = ctx.dolphin_status
            await asyncio.sleep(1)
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
