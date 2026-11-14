"""Experimental LEGO City Undercover AP client with opt-in native item grants.

The same source is used by the console client and native_client_gui.py. Native
item receipts require matching game/save identities and disk verification.
"""
import argparse
import asyncio
import json
import logging
from pathlib import Path
import queue
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent / 'bridge'))

from CommonClient import CommonContext, ClientCommandProcessor, server_loop
from live_monitor import Session
from client_journal import Journal
from cutscene_skip import enable_cutscene_skip
from NetUtils import ClientStatus
from client_checks import changed_checks
from level_progress import completed_level_keys
from red_bricks import redbrick_location_key
from item_delivery import register_delivery
from native_delivery import NativeDeliveryEngine
from native_bridge_path import bridge_path
from station_exit import StationExitGate, read_station_exit, can_resume_first_lobby, read_lobby_lift
from native_model_transport import (trigger_station_exit, open_lobby_lift,
                                    relax_tutorial_fields, unlock_chief_key, reveal_chief_radio)
from activity_rewards import completed_activity_rewards
from tutorial_field_timing import TutorialFieldTiming
from story_arrests import ARRESTS, completed_story_arrests
from test_overrides import TestOverrides


class Commands(ClientCommandProcessor):
    def _cmd_check(self, location_id: str):
        """Manually report a checked location that is active in this seed."""
        try:
            location = int(location_id)
        except ValueError:
            return False
        if str(location) not in self.ctx.catalogue:
            self.output('ID not active in this seed')
            return False
        if self.ctx.journal is None:
            self.output('Wait for the connected journal to initialize')
            return False
        asyncio.create_task(self.ctx.report_checks([location]))
        return True


class Context(CommonContext):
    game = 'LEGO City Undercover'
    items_handling = 0b111
    command_processor = Commands

    def __init__(self, args):
        super().__init__(args.connect, args.password)
        self.auth = args.name
        self.catalogue = {}
        self.slot_options = {}
        self.enable_skip = args.enable_cutscene_skip
        self.native_save_file = getattr(args, 'native_save_file', None)
        self.enable_native_models = args.enable_native_models
        self.skip_slot = False
        self.model_labels = json.loads((Path(__file__).parent / 'bridge/monitor_labels.json')
                                       .read_text(encoding='utf-8')).get('models', {})
        self.journal = None
        self.test_overrides = TestOverrides()
        self.ui_events = getattr(args, 'ui_events', None)
        self.native_ready = False
        self.game_loaded = False
        catalogue = json.loads((Path(__file__).parent / 'catalogue.json').read_text(encoding='utf-8'))
        self.item_effects = {str(row['id']): dict(name=name, **row)
                             for name, row in catalogue['items'].items()}
        self.state_dir = Path(__file__).parent / 'notes/client_journal'

    def notify(self, kind, value):
        if self.ui_events is not None:
            self.ui_events.put((kind, value))

    async def report_checks(self, locations):
        if self.journal is None:
            raise RuntimeError('No connected journal binding')
        locations = sorted(set(locations) - set(self.checked_locations))
        if not locations:
            return
        self.journal.queue(locations)
        for location in locations:
            row = self.catalogue.get(str(location), {})
            logging.info('CHECK queued: %s | ID %s | %s', row.get('name', location),
                         location, row.get('status', 'manual'))
        await self.send_msgs([dict(cmd='LocationChecks', locations=locations)])

    async def server_auth(self, password_requested=False):
        if password_requested and not self.password:
            await super().server_auth(password_requested)
        await self.get_username()
        await self.send_connect()

    def on_package(self, cmd, args):
        if cmd == 'RoomInfo':
            self.seed_name = args['seed_name']
        if cmd == 'Connected':
            self.slot_options = args.get('slot_data', {}).get('options', {})
            self.item_effects.update(args.get('slot_data', {}).get('item_effects', {}))
            self.catalogue = args.get('slot_data', {}).get('locations', {})
            self.goal_count = args.get('slot_data', {}).get('goal_tokens', 20)
            self.skip_slot = bool(self.slot_options.get('cutscene_skip', False))
            logging.warning('Native grants, autosave and reward suppression: %s. '
                            'Story/area entrance gates remain unavailable.',
                            'EXPERIMENTAL, enabled' if self.enable_native_models else 'disabled')


def notify_game(ctx, loaded, detail=None):
    ctx.game_loaded = bool(loaded)
    ctx.notify('game_loaded', bool(loaded))
    ctx.notify('game', 'Spiel: ' + (detail if loaded and detail else 'Nicht geladen'))
    if not loaded:
        ctx.native_ready = False
        ctx.notify('ready', False)
        ctx.notify('save', 'Save: Nicht gebunden')


async def watcher(ctx):
    native_delivery = NativeDeliveryEngine(bridge_path(ROOT), ctx.native_save_file)
    exit_gate = StationExitGate()
    opened_lift = None
    tutorial_timing = TutorialFieldTiming()
    session = None
    previous = None
    binding = None
    journal_binding = None
    seen_models = set()
    seen_arrests = set()
    skip_pid = None
    try:
        while not ctx.exit_event.is_set():
            try:
                if ctx.enable_skip and ctx.skip_slot:
                    try:
                        skip = await asyncio.to_thread(enable_cutscene_skip)
                        if skip['before'] == 0 or skip_pid != skip['pid']:
                            logging.info('Cutscene skip enabled (N0CUT5); works before loading a save')
                        skip_pid = skip['pid']
                    except (OSError, RuntimeError, ValueError) as error:
                        logging.debug('Cutscene skip waiting for manager: %s', error)
                if ctx.slot is not None and ctx.catalogue and ctx.seed_name:
                    current_binding = (ctx.seed_name, ctx.team, ctx.slot)
                    if current_binding != binding:
                        previous = None
                        binding = current_binding
                        seen_models.clear()
                        seen_arrests.clear()
                        ctx.test_overrides = TestOverrides()
                        ctx.native_ready = False
                        ctx.notify('ready', False)
                        if session:
                            session.close()
                        session = None
                    if ctx.journal is None or current_binding != journal_binding:
                        if ctx.journal:
                            ctx.journal.close()
                        ctx.journal = Journal(ctx.state_dir, dict(seed=ctx.seed_name, team=ctx.team,
                            slot=ctx.slot, catalogue=ctx.catalogue, detection_policy=2))
                        journal_binding = current_binding
                    for i, item in enumerate(ctx.items_received):
                        ctx.journal.receipt(i, item)
                        effect = ctx.item_effects.get(str(item.item))
                        if effect:
                            register_delivery(ctx.journal, i, effect)
                    ctx.journal.acknowledge(ctx.checked_locations)
                    pending = ctx.journal.pending()
                    if pending:
                        await ctx.send_msgs([dict(cmd='LocationChecks', locations=pending)])
                    if (not ctx.finished_game and
                            sum(x.item == 2_999_999_999 for x in ctx.items_received) >= ctx.goal_count):
                        await ctx.send_msgs([dict(cmd='StatusUpdate', status=ClientStatus.CLIENT_GOAL)])
                        ctx.finished_game = True
                    if session is None:
                        session = await asyncio.to_thread(Session)
                    snapshot = await asyncio.to_thread(session.snapshot)
                    if snapshot.get('actor', {}).get('status') != 'read':
                        # Stale inventory from the game menu must never create AP checks.
                        previous = None
                        seen_models.clear()
                        notify_game(ctx, False)
                        await asyncio.sleep(1)
                        continue
                    notify_game(ctx, True, snapshot['actor'].get('equipped_internal_name', 'Spieler geladen'))

                    for row in snapshot.get('native_pickups', {}).get('objects', []):
                        if row.get('native_type') != 7 or not row.get('native_collected'):
                            continue
                        source = row.get('source_key')
                        identity = ('red_brick', source or (row.get('tile_name'), row['name']))
                        if identity in seen_models:
                            continue
                        seen_models.add(identity)
                        location_key = redbrick_location_key(source) if source else None
                        active = any(v.get('key') == location_key for v in ctx.catalogue.values())
                        logging.info('RED BRICK collected: %s | scene=%s | flags=%s | %s',
                            row['name'], row.get('tile_name'), row.get('pickup_flags'),
                            'check location active' if active else 'no corresponding location in this seed')
                    for reward_key, reward in completed_activity_rewards(snapshot).items():
                        identity = ('activity_reward', reward_key)
                        if identity in seen_models:
                            continue
                        seen_models.add(identity)
                        active = any((v.get('runtime') or {}).get('reward_key') == reward_key
                                     for v in ctx.catalogue.values())
                        logging.info('ACTIVITY completed: %s | source=%s | %s', reward['name'],
                            reward['source_key'], 'check location active' if active else
                            'location absent from current seed; included in future seeds')
                    for completed_key in sorted(completed_level_keys(snapshot.get('level_progress', {}))):
                        identity = ('persistent_level', completed_key)
                        if identity not in seen_models:
                            seen_models.add(identity)
                            logging.info('SAVED MISSION CHECK: %s', completed_key)
                    for row in snapshot.get('superbuilds', {}).get('records', []):
                        if not row.get('complete'):
                            continue
                        identity = ('superbuild', row['name'], row.get('objective_name'))
                        if identity not in seen_models:
                            seen_models.add(identity)
                            logging.info('SUPER BUILD completed: %s | objective=%s | state=%s flags=%s',
                                row['name'], row.get('objective_name') or 'unmapped', row['state'], row['completion_flags'])
                    for row in snapshot.get('native_pickups', {}).get('objects', []):
                        source = row.get('source_key', '') or ''
                        if not (row.get('native_collected') and row.get('native_type') in (12, 29)
                                and '/levels/standalones/' in source):
                            continue
                        identity = ('mission_superbrick', source)
                        if identity in seen_models:
                            continue
                        seen_models.add(identity)
                        active = any(v.get('key') == 'source_pickup:' + source for v in ctx.catalogue.values())
                        logging.info('MISSION SUPER BRICK collected: %s / %s | flags=%s | position=%s | %s',
                            row.get('tile_name'), row['name'], row['pickup_flags'], row['position'],
                            'check location active' if active else 'source absent from this seed; updated APWorld required')
                    hero = snapshot.get('mission_hero', {})
                    if hero.get('status') == 'read' and hero.get('complete'):
                        identity = ('city_hero', hero['mission'])
                        if identity not in seen_models:
                            seen_models.add(identity)
                            logging.info('LEGO CITY HERO: %s | studs=%s target=%s | native completion=%s',
                                hero['mission'], hero['studs'], hero['threshold'], hero['latch'])
                    shield = snapshot.get('mission_shield', {})
                    if shield.get('status') == 'read':
                        for part in shield.get('parts', []):
                            identity = ('shield', shield['mission'], part)
                            if identity not in seen_models:
                                seen_models.add(identity)
                                logging.info('POLICE SHIELD: %s | %s | mask=%s',
                                             shield['mission'], part, shield['mask'])
                    for row in snapshot.get('mission_tokens', {}).get('records', []):
                        identity = ('mission', row['internal_name'].upper())
                        if identity in seen_models:
                            continue
                        seen_models.add(identity)
                        bound = any((v.get('runtime') or {}).get('kind') == 'model_found' and
                                    v['runtime']['native_name'].upper() == identity[1]
                                    for v in ctx.catalogue.values())
                        logging.info('STORY TOKEN collected: %s (%s) | model %s | %s',
                            ctx.model_labels.get(str(row['model_id']), {}).get('display_name', row['internal_name']),
                            row['internal_name'], row['model_id'],
                            'experimental token check' if bound else
                            'no token location in this seed; regenerate with updated APWorld')
                    for row in snapshot.get('characters', []):
                        if row.get('group') not in ('character', 'vehicle') or not (row.get('found_bit') or row.get('pending_grant')):
                            continue
                        identity = row['internal_name'].upper()
                        if identity in seen_models:
                            continue
                        seen_models.add(identity)
                        bound = any((v.get('runtime') or {}).get('kind') == 'model_found' and
                                    v['runtime']['native_name'].upper() == identity
                                    for v in ctx.catalogue.values())
                        logging.info('FOUND %s: %s | model %s | found=%s pending=%s owned=%s | %s',
                            row['group'], row['internal_name'], row['model_id'], row.get('found_bit'),
                            row.get('pending_grant'), row.get('owned_byte'),
                            'experimental token binding' if bound else 'no token location in this seed')
                    arrests = completed_story_arrests(snapshot.get('story', {}))
                    active_keys = {row.get('key') for row in ctx.catalogue.values()}
                    for arrest in ARRESTS:
                        if arrest['key'] in arrests - seen_arrests:
                            logging.info('STORY arrest completed: %s | %s | %s', arrest['name'],
                                arrest['job'] + '.' + arrest['field'],
                                'check location active' if arrest['key'] in active_keys else
                                'location absent from current seed; enable story_missions in a newly generated seed')
                    seen_arrests.update(arrests)
                    checks, previous = changed_checks(ctx.catalogue, previous,
                        ctx.test_overrides.mask_snapshot(snapshot),
                        set(ctx.checked_locations) | set(ctx.journal.pending()))
                    if checks:
                        await ctx.report_checks(checks)
                    if ctx.enable_native_models:
                        received = [ctx.item_effects[str(item.item)] for item in ctx.items_received
                                    if str(item.item) in ctx.item_effects]
                        await native_delivery.poll(session, snapshot, ctx.journal,
                            ctx.item_effects.values(), received, ctx.slot_options, ctx.test_overrides)
                        # The binding is a prerequisite for any local test button.
                        # A binding error or an unavailable game context must disable it.
                        bound = native_delivery.path is not None
                        problem = native_delivery.last_problem or ''
                        safe_context = snapshot['actor'].get('context', {}).get('index') == 46
                        # An equipped-outfit deferral may remain in last_problem
                        # after the user changes outfits. The backend always
                        # revalidates the actual context before a mutation.
                        ctx.native_ready = bool(bound and safe_context and
                            not problem.startswith(('Loaded native save is bound',
                                                    'No unique matching native save')))
                        ctx.notify('ready', ctx.native_ready)
                        ctx.notify('save', 'Save: ' + native_delivery.path.name if bound else
                                   'Save: Noch nicht eindeutig zugeordnet')
                        fields_ready = tutorial_timing.ready(session.pid, snapshot.get('scene_fields', {}))
                        if fields_ready and safe_context:
                            changed = await asyncio.to_thread(relax_tutorial_fields, session.pid, native_delivery.dll)
                            if changed:
                                logging.info('Station tutorial: %s scoped pad/lesson changes after genuine prerequisite', changed)
                            if await asyncio.to_thread(unlock_chief_key, session.pid, native_delivery.dll):
                                logging.info('Chief office tutorial: original key revealed; pick it up and use the lock normally')
                            if await asyncio.to_thread(reveal_chief_radio, session.pid, native_delivery.dll):
                                logging.info('Chief office tutorial: original radio build parts activated; assemble normally')
                        eligible = can_resume_first_lobby(snapshot.get('story', {}))
                        lift_probe = (await asyncio.to_thread(read_lobby_lift, session.read, session.base)) if eligible else None
                        if lift_probe is None:
                            opened_lift = None
                        elif (safe_context and lift_probe['distance_squared'] <= 2.25 and
                              opened_lift != (session.pid, lift_probe['owner'])):
                            opened_lift = (session.pid, lift_probe['owner'])
                            if await asyncio.to_thread(open_lobby_lift, session.pid, native_delivery.dll):
                                logging.info('Lobby lift arrival: opening existing lift doors without advancing tutorial')
                            else:
                                opened_lift = None
                        probe = (await asyncio.to_thread(read_station_exit, session.read, session.base)) if eligible else None
                        if exit_gate.update(session.pid, probe, snapshot['actor'].get('context', {}).get('index')):
                            exit_gate.mark_triggered()
                            if await asyncio.to_thread(trigger_station_exit, session.pid, native_delivery.dll):
                                logging.info('Police station transition: %s; first-visit re-entry prepared', probe['door_name'])
                            else:
                                exit_gate.triggered = False
                    else:
                        ctx.native_ready = False
                        ctx.notify('ready', False)
                        ctx.notify('save', 'Save: Native Modus deaktiviert')
                else:
                    notify_game(ctx, False)
                await asyncio.sleep(1)
            except (OSError, RuntimeError, ValueError) as error:
                logging.warning('Reader waiting: %s', error)
                ctx.native_ready = False
                ctx.notify('ready', False)
                notify_game(ctx, False)
                if session:
                    session.close()
                session = None
                previous = None
                tutorial_timing = TutorialFieldTiming()
                await asyncio.sleep(2)
    finally:
        notify_game(ctx, False)
        if session:
            session.close()
        if ctx.journal:
            ctx.journal.close()
            ctx.journal = None


async def _run_client(args):
    ctx = Context(args)
    ctx.server_task = asyncio.create_task(server_loop(ctx))
    gui = getattr(args, 'ui_controls', None)
    if gui is None:
        ctx.run_cli()

    async def controls():
        last_status = None
        while not ctx.exit_event.is_set():
            try:
                action, payload = gui.get_nowait()
                if action == 'disconnect':
                    ctx.exit_event.set()
                elif ctx.journal is None:
                    logging.error('TEST: Erst AP und Spiel verbinden lassen.')
                elif action == 'reset':
                    ctx.test_overrides.reset()
                    logging.info('TEST: Rückkehr zum AP-Zustand angefordert (Währungsbuchungen bleiben bestehen).')
                elif action in ('give', 'remove'):
                    if not ctx.native_ready or not ctx.enable_native_models:
                        raise ValueError('Native Test-Items sind erst mit gebundenem Save und normaler Spielfigur verfügbar.')
                    matches = [e for e in ctx.item_effects.values() if e['name'] == payload]
                    if len(matches) != 1:
                        raise ValueError('Unbekanntes oder mehrdeutiges Item: ' + str(payload))
                    ctx.test_overrides.set(matches[0], action == 'give')
                    logging.info('TEST angefordert: %s · %s', action, payload)
                else:
                    logging.warning('GUI: Unbekannter Befehl %s', action)
            except queue.Empty:
                pass
            except (ValueError, RuntimeError) as error:
                logging.error('TEST: %s', error)
            connected = bool(ctx.server and ctx.slot is not None)
            override_signature = tuple(sorted((str(key), value[1])
                for key, value in ctx.test_overrides.entries.items()))
            status = (connected, ctx.native_ready, len(ctx.checked_locations),
                      len(ctx.items_received), str(ctx.auth), override_signature)
            if ctx.ui_events is not None and status != last_status:
                ctx.notify('connection', connected)
                ctx.notify('ap', ('Archipelago: Verbunden · ' + str(ctx.auth)) if connected else
                           'Archipelago: Warte auf Verbindung …')
                ctx.notify('progress', f'Checks: {len(ctx.checked_locations)} · AP-Items: {len(ctx.items_received)}')
                ctx.notify('overrides', [e['name'] + (' → geben' if value else
                    ' → AP' if value is None else ' → entfernen')
                    for e, value in ctx.test_overrides.entries.values()])
                last_status = status
            await asyncio.sleep(.25)

    control_task = asyncio.create_task(controls()) if gui is not None else None
    task = asyncio.create_task(watcher(ctx))
    try:
        await ctx.exit_event.wait()
    finally:
        ctx.exit_event.set()
        await task
        await ctx.shutdown()
        if control_task:
            await control_task


async def main(args):
    if args.enable_native_models:
        from native_client_lock import NativeClientLock
        try:
            with NativeClientLock():
                await _run_client(args)
        except RuntimeError as error:
            logging.error('%s', error)
    else:
        await _run_client(args)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--connect')
    parser.add_argument('--name')
    parser.add_argument('--password')
    parser.add_argument('--native-save-file', type=Path,
        help='Loaded slot gameN.legocityundercoversavegamedata, or auto-detect a unique matching save')
    parser.add_argument('--enable-cutscene-skip', action='store_true')
    parser.add_argument('--enable-native-items', '--enable-native-models',
        dest='enable_native_models', action='store_true')
    logging.basicConfig(level=logging.INFO)
    logging.getLogger().setLevel(logging.INFO)
    for handler in logging.getLogger().handlers:
        if handler.level > logging.INFO:
            handler.setLevel(logging.INFO)
    asyncio.run(main(parser.parse_args()))
