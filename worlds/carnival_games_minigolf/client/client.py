import asyncio
import hashlib
import json
import time
from pathlib import Path

import Utils
from websockets.exceptions import ConnectionClosed
from CommonClient import ClientCommandProcessor, CommonContext, gui_enabled, logger, server_loop
from NetUtils import ClientStatus

from ..data import GAME, HOLES, MINIGAMES, WORLDS
from .journal import Journal
from .memory import Memory, MemoryUnavailable
from .runtime import Runtime, validate_slot


def emulation_active(dolphin):
    """A process hook can outlive emulation and still expose stale Wii RAM."""
    return dolphin.is_hooked() and getattr(dolphin.get_status(), 'name', None) == 'hooked'


class MiniGolfCommands(ClientCommandProcessor):
    def _cmd_dolphin(self):
        """Show Dolphin connection and game verification status."""
        logger.info(self.ctx.dolphin_status)

    def _cmd_minigolf(self):
        """Show check, item and world progression."""
        runtime = self.ctx.runtime
        if runtime:
            unlocked, coins = runtime.unlocked([item.item for item in self.ctx.items_received])
            logger.info("Worlds: %s | AP Barker Coins: %d | Checks: %d/%d | Local player: %d",
                        ', '.join(WORLDS[i] for i in sorted(unlocked)), coins,
                        len(self.ctx.locations_checked), len(runtime.locations), self.ctx.local_player + 1)
        else:
            logger.info("Connect to a Carnival Games MiniGolf AP slot first.")

    def _cmd_minigolfdebug(self):
        """Show the resolved live game context for troubleshooting."""
        if not self.ctx.runtime:
            logger.info("Connect to a Carnival Games MiniGolf AP slot first.")
            return
        try:
            import dolphin_memory_engine as dolphin
            if not emulation_active(dolphin):
                logger.info("Dolphin is not actively emulating the game.")
                return
            state = self.ctx.runtime.debug_state(Memory(dolphin), self.ctx.local_player)
            def address(value):
                return f"{value:08X}" if isinstance(value, int) else str(value)
            hole = state['derived_hole']
            hole_name = f" ({HOLES[hole]})" if isinstance(hole, int) and 0 <= hole < 27 else ""
            minigame = state['minigame']
            minigame_name = MINIGAMES[minigame][0] if isinstance(minigame, int) else "none"
            logger.info("Manager: %s | State: %s | Session: %s | Session player: %s | Root: %s | "
                        "Course: %s | Hole def: %s | Derived hole: %s%s | Strokes: %s | Par: %s | "
                        "Hole state: %s | In goal: %s | Controller: %s | VTable: %s | Minigame: %s | "
                        "Object array: %s | Result popup: %s | Win: %s | Perfect: %s",
                        address(state['manager']), state['manager_state'], address(state['session']),
                        state['session_player'], address(state['root']), state['course'], address(state['hole_def']),
                        hole, hole_name, state['strokes'], state['par'], address(state['hole_state']),
                        state['in_goal'], address(state['controller']), address(state['vtable']), minigame_name,
                        address(state['object_array']), address(state['result_popup']), state['win'], state['perfect'])
        except (ImportError, RuntimeError, OSError, MemoryUnavailable) as error:
            logger.info("Live MiniGolf debug state unavailable: %s", error)

    def _cmd_currency_recover(self, action=""):
        """Resolve an interrupted, ambiguous coin grant: skip keeps RAM balance; apply retries the grant."""
        runtime = self.ctx.runtime
        if not runtime or not runtime.journal.data['pending']:
            logger.info("No interrupted currency grant.")
            return
        journal = runtime.journal
        if action == 'skip':
            journal.advance(journal.data['pending']['index'])
        elif action == 'apply':
            journal.data['pending'] = None
            journal.save()
        else:
            logger.info("Usage: /currency_recover skip OR /currency_recover apply")
            return
        self.ctx.runtime_error = None
        logger.info("Currency recovery saved; synchronization will resume.")


class MiniGolfContext(CommonContext):
    game = GAME
    items_handling = 0b111
    command_processor = MiniGolfCommands

    def __init__(self, address=None, password=None, patch_file=None, local_player=0):
        super().__init__(address, password)
        self.local_player = local_player
        self.runtime = None
        self.runtime_error = None
        self.history_ready = False
        self.dolphin_status = "Waiting for Dolphin."
        self.expected_seed = None
        self.last_send = 0.0
        self.last_sent = set()
        self.journal_lock = None
        if patch_file:
            patch = json.loads(Path(patch_file).read_text(encoding='utf-8'))
            if patch.get('game') != GAME:
                raise ValueError("This is not a Carnival Games MiniGolf output file")
            validate_slot(patch['slot_data'])
            self.expected_seed = patch['slot_data']['seed_name']
            self.seed_name = self.expected_seed
            self.auth = patch.get('player_name')

    async def server_auth(self, password_requested=False):
        if password_requested and not self.password:
            await super().server_auth(password_requested)
        if not self.auth:
            await self.get_username()
        await self.send_connect(game=GAME)

    def release_journal(self):
        if self.journal_lock:
            self.journal_lock.close()
            self.journal_lock = None

    def acquire_journal(self, path):
        # Hold an OS lock for the entire connected session, so two clients cannot
        # both grant the same receipt from a shared journal.
        path.parent.mkdir(parents=True, exist_ok=True)
        handle = path.with_suffix('.lock').open('a+b')
        try:
            handle.seek(0)
            if __import__('sys').platform == 'win32':
                import msvcrt
                if handle.read(1) == b'':
                    handle.write(b'0')
                    handle.flush()
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            handle.close()
            raise ValueError("Another MiniGolf client is already using this seed and slot") from None
        self.journal_lock = handle

    def on_package(self, cmd, args):
        if cmd == 'Connected':
            self.release_journal()
            self.runtime = None
            self.history_ready = False
            self.runtime_error = None
            self.finished_game = False
            self.locations_checked = set()
            self.last_sent = set()
            try:
                data = args['slot_data']
                validate_slot(data)
                if self.expected_seed and self.expected_seed != data['seed_name']:
                    raise ValueError("Server seed differs from the loaded .apcgm file")
                identity = json.dumps([data['schema_version'], data['seed_name'], self.team, self.slot,
                                       self.local_player])
                key = hashlib.sha256(identity.encode()).hexdigest()
                path = Path(Utils.user_path('carnival_games_minigolf', key + '.json'))
                self.acquire_journal(path)
                self.runtime = Runtime(data, Journal(path))
                self.locations_checked = set(self.runtime.journal.data['checks'])
                # AP omits ReceivedItems for an empty inventory, including Sync replies.
                # A read-only round trip establishes an ordered barrier after Connected
                # and any initial ReceivedItems without guessing from an elapsed timeout.
                asyncio.create_task(self.send_msgs([{'cmd': 'Get', 'keys': ['_cgm_history_barrier']}]))
                logger.info("MiniGolf slot ready. Starting world: %s. Use a dedicated game profile for this seed.",
                            WORLDS[data['starting_world']])
            except (ValueError, KeyError, OSError) as error:
                self.release_journal()
                self.runtime_error = str(error)
                logger.error("MiniGolf synchronization disabled: %s", error)
        elif cmd == 'ReceivedItems':
            if args.get('index') == 0:
                self.history_ready = True
            elif args.get('index', 0) + len(args.get('items', [])) != len(self.items_received):
                self.history_ready = False
        elif cmd == 'Retrieved' and '_cgm_history_barrier' in args.get('keys', {}):
            self.history_ready = True

    def reset_server_state(self):
        self.clear_piece_projection()
        super().reset_server_state()
        self.history_ready = False
        self.runtime = None
        self.release_journal()

    def clear_piece_projection(self):
        if not self.runtime or not self.runtime.pieces_projected:
            return
        try:
            import dolphin_memory_engine as dolphin
            if emulation_active(dolphin):
                self.runtime.clear_piece_projection(Memory(dolphin), self.local_player)
        except (ImportError, RuntimeError, OSError, MemoryUnavailable):
            logger.warning("Could not clear projected Par Club Pieces while disconnecting; "
                           "reconnect before saving or entering gameplay.")

    def make_gui(self):
        from kvui import GameManager

        class MiniGolfManager(GameManager):
            base_title = "Carnival Games MiniGolf Client"
            logging_pairs = [('Client', 'Archipelago')]

        return MiniGolfManager


async def dolphin_loop(ctx):
    try:
        import dolphin_memory_engine as dolphin
    except ImportError:
        ctx.dolphin_status = "dolphin-memory-engine is missing; install the world requirements in your AP Python environment."
        logger.error(ctx.dolphin_status)
        return
    memory = Memory(dolphin)
    previous_status = None
    settled_context = None
    settle_at = 0.0
    try:
        while not ctx.exit_event.is_set():
            try:
                if not dolphin.is_hooked():
                    settled_context = None
                    dolphin.hook()
                if not dolphin.is_hooked():
                    raise MemoryUnavailable("Waiting for Dolphin.")
                if not emulation_active(dolphin):
                    settled_context = None
                    raise MemoryUnavailable("Dolphin connected; waiting for the game to start.")
                if not ctx.runtime or ctx.slot is None or not ctx.server:
                    raise MemoryUnavailable("Dolphin attached. Waiting for AP slot.")
                if ctx.runtime_error:
                    raise MemoryUnavailable(ctx.runtime_error)
                if not memory.verify_game():
                    settled_context = None
                    raise MemoryUnavailable("Waiting for Carnival Games MiniGolf RG9P54, supported executable revision.")
                snapshot = memory.resolve(ctx.local_player)
                context = (snapshot.manager, snapshot.roots, id(ctx.runtime))
                if context != settled_context:
                    settled_context = context
                    settle_at = time.monotonic() + 2
                    ctx.runtime.reset_transient()
                if time.monotonic() < settle_at:
                    raise MemoryUnavailable("Game profile found; waiting for RAM to settle.")
                items = [item.item for item in ctx.items_received]
                checks = ctx.runtime.poll(memory, items, ctx.local_player, ctx.history_ready)
                ctx.locations_checked |= checks
                pending = ctx.locations_checked - ctx.checked_locations
                if pending and (pending != ctx.last_sent or time.monotonic() - ctx.last_send >= 5):
                    await ctx.send_msgs([{'cmd': 'LocationChecks', 'locations': sorted(pending)}])
                    ctx.last_sent = pending.copy()
                    ctx.last_send = time.monotonic()
                if not ctx.finished_game and ctx.runtime.victory(items, ctx.locations_checked | ctx.checked_locations):
                    await ctx.send_msgs([{'cmd': 'StatusUpdate', 'status': ClientStatus.CLIENT_GOAL}])
                    ctx.finished_game = True
                    logger.info("Carnival Games MiniGolf goal complete!")
                if ctx.history_ready:
                    ctx.dolphin_status = "Dolphin connected; supported game verified; synchronization active."
                else:
                    ctx.dolphin_status = "Dolphin connected; game checks active; received item history loading."
            except MemoryUnavailable as error:
                ctx.dolphin_status = str(error)
                if ctx.dolphin_status == "Waiting for game player state.":
                    settled_context = None
            except ValueError as error:
                ctx.runtime_error = str(error)
                ctx.dolphin_status = f"Synchronization paused: {error}"
            except ConnectionClosed:
                ctx.dolphin_status = "AP connection lost; waiting for reconnect."
                settled_context = None
            except (RuntimeError, OSError) as error:
                ctx.dolphin_status = f"Dolphin unavailable: {error}"
                settled_context = None
                if ctx.runtime:
                    ctx.runtime.reset_transient()
                if dolphin.is_hooked():
                    dolphin.un_hook()
            if ctx.dolphin_status != previous_status:
                logger.info(ctx.dolphin_status)
                previous_status = ctx.dolphin_status
            await asyncio.sleep(0.1 if ctx.dolphin_status.endswith('active.') else 1)
    finally:
        if emulation_active(dolphin):
            ctx.clear_piece_projection()
        if dolphin.is_hooked():
            dolphin.un_hook()


async def main(args):
    ctx = MiniGolfContext(args.connect, args.password, args.patch_file, args.local_player - 1)
    ctx.auth = args.name or ctx.auth
    ctx.server_task = asyncio.create_task(server_loop(ctx), name='ServerLoop')
    if gui_enabled and not getattr(args, 'nogui', False):
        ctx.run_gui()
    ctx.run_cli()
    watcher = asyncio.create_task(dolphin_loop(ctx), name='DolphinSync')
    try:
        await ctx.exit_event.wait()
    finally:
        ctx.exit_event.set()
        await watcher
        ctx.clear_piece_projection()
        ctx.release_journal()
        await ctx.shutdown()
