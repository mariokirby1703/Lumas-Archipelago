import asyncio
from contextlib import nullcontext
import hashlib
import json
from pathlib import Path
import time
from datetime import datetime, timezone

import Utils
from CommonClient import ClientCommandProcessor, CommonContext, gui_enabled, logger, server_loop, mark_raw
from NetUtils import ClientStatus
from websockets.exceptions import ConnectionClosed
from ..world_constants import GAME
from ..Items import BY_ID
from .test_inventory import (ABILITY_SET, ABILITY_GROUPS, TESTABLE, MAXIMUM,
                             parse_item_request, resolve_ability_group)
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
from . import quiet_logging


def log_diagnostic(value):
    """One copyable GUI record; compact nested values avoid excessive height."""
    if isinstance(value, dict):
        text = '{\n' + ',\n'.join('  '+json.dumps(key)+': '+json.dumps(item)
                                  for key, item in value.items()) + '\n}'
    else:
        text = json.dumps(value)
    logger.info(text)


class SonicCommands(ClientCommandProcessor):
    def _test_inventory_base(self):
        """True server receipts, including uncommitted permission history."""
        if not self.ctx.runtime or not self.ctx.authenticated_identity:
            raise ValueError('Connect to an authenticated Sonic Colours AP slot first.')
        item_ids = ([item.item for item in self.ctx.items_received] if self.ctx.history_ready
                    else list(self.ctx.runtime.journal.data['receipts']))
        item_ids += [item for item in self.ctx.runtime.journal.data.get('permission_receipts', ())
                     if item not in item_ids]
        return inventory(item_ids)

    @mark_raw
    def _cmd_give(self, raw=''):
        """TEST ONLY: /give ITEM [LEVEL|all]. Numeric progressive items set a target level; no AP receipt."""
        self._change_test_ability('give', raw)

    @mark_raw
    def _cmd_remove(self, raw=''):
        """TEST ONLY: /remove ITEM [COUNT|all]. Temporarily mask a real AP ability; /testitems reset restores."""
        self._change_test_ability('remove', raw)

    @mark_raw
    def _cmd_testitems(self, raw=''):
        """List supported items or show/reset session-local /give and /remove overrides."""
        action=raw.strip().lower()
        if action in ('list', 'help'):
            log_diagnostic({'supported_items':list(TESTABLE), 'all_targets':list(ABILITY_SET),
                            'progressive_limits':MAXIMUM,
                            'examples':['/give Double Jump','/remove Double Jump',
                                        '/give White Boost Wisp','/remove Cyan Laser Wisp',
                                        '/give Progressive Crouch 2',
                                        '/give Progressive Breathing 5',
                                        '/give breath 2  (level 2 = 10 seconds)',
                                        '/give laser', '/remove drill',
                                        '/give legacy breath  (retired 30-second item)',
                                        '/remove Progressive Breathing all',
                                        '/give wisps', '/remove wisps',
                                        '/give movements', '/remove movements',
                                        '/give sweet', '/remove sweet',
                                        '/give asteroid', '/remove aquarium',
                                        '/give worlds', '/remove worlds',
                                        '/give all', '/remove all', '/testitems reset'],
                            'ability_groups': {group: list(items) for group, items in ABILITY_GROUPS.items()},
                            'note':('Only local test abilities. No AP item is sent/removed on the server. '
                                    '/give progressively numbered items sets the exact target level; '
                                    '/remove ITEM N subtracts N levels. /remove ITEM all sets 0.')})
            return
        try:
            original=self._test_inventory_base()
        except ValueError as error:
            logger.warning('%s',error)
            return
        overlay=self.ctx.runtime.test_inventory
        if action == 'reset':
            overlay.reset()
            self.ctx.refresh_movement_permissions()
            logger.warning('All local ability overrides cleared. Real AP receipts restored.')
        elif action:
            logger.info('Usage: /testitems [list|reset].')
            return
        log_diagnostic(overlay.describe(original))

    def _change_test_ability(self, action, raw):
        """One short result line; detailed ownership remains in /testitems."""
        refresh=False
        try:
            original = self._test_inventory_base()
            overlay = self.ctx.runtime.test_inventory
            if raw.strip().lower() == 'all':
                results = overlay.change_all_abilities(action, original)
                refresh=True
                if any(result['before'] != result['effective'] for result in results):
                    logger.info('%s: all abilities.', 'Given' if action == 'give' else 'Removed')
                else:
                    logger.info('No change: all abilities already %s.',
                                'unlocked' if action == 'give' else 'removed')
                return
            group = resolve_ability_group(raw)
            if group is not None:
                results = overlay.change_ability_group(action, group, original)
                refresh=True
                label = ('all Wisps' if group == 'wisps' else
                         'all World Shuttles' if group == 'worlds' else
                         'all Movement abilities (max level)' if action == 'give'
                         else 'all Movement abilities')
                if any(result['before'] != result['effective'] for result in results):
                    logger.info('%s: %s.', 'Given' if action == 'give' else 'Removed', label)
                else:
                    logger.info('No change: %s already %s.', label,
                                'unlocked' if action == 'give' else 'removed')
                return
            name, quantity = parse_item_request(raw, getattr(overlay, 'options', None))
            result = overlay.change(action, name, quantity, original)
            refresh=True
            if result['before'] == result['effective']:
                logger.info('No change: %s already %s.', name,
                            'at the requested level' if action == 'give' and name in MAXIMUM
                            else 'unlocked' if action == 'give' else 'removed')
                return
            level = (f" (level {result['effective']})" if name in MAXIMUM else '')
            logger.info('%s: %s%s.', 'Given' if action == 'give' else 'Removed', name, level)
        except ValueError as error:
            logger.warning('%s failed: %s', 'Give' if action == 'give' else 'Remove', error)
        finally:
            if refresh:self.ctx.refresh_movement_permissions()

    def _cmd_soniccapsules(self):
        """Read-only capsule/ghost-spawn evidence, including missing models."""
        snap = self.ctx.runtime.snapshot if self.ctx.runtime else None
        if snap is None:
            logger.info('Connect to Dolphin and a Sonic Colours slot first.')
            return
        stage = next(iter(snap.evidence.get('native_data', {}).get('stage_objects', [])), {})
        from ..capsules import CAPSULES
        rows = []
        for record in stage.get('capsules', []):
            definition = CAPSULES.get(record['key'])
            rows.append({'key': record['key'], 'wisp': definition.wisp_item if definition else None,
                         'eligible': bool(definition and definition.eligible),
                         'actor': f"0x{record['actor']:08X}", 'opened':record['opened'],
                         'model_present': bool(record.get('model')), 'model_mode':record.get('model_mode'),
                         'collision':record.get('collision'), 'native_enabled':record.get('native_enabled')})
        log_diagnostic({'mission':snap.actual_mission,'captured_actors':len(rows),
                        'unmodeled_capsules':[row for row in rows if not row['opened'] and not row['model_present']],
                        'capsules':rows,'capture_error':stage.get('capsule_error'),
                        'note':'Read-only evidence; scripted ghost spawn is not yet fixed.'})

    def _cmd_sonicmap(self):
        """Read-only Grand Map cache versus AP access for unowned castles."""
        snap = self.ctx.runtime.snapshot if self.ctx.runtime else None
        if not snap or snap.scene != 'global_map' or not self.ctx.memory:
            logger.info('Open the Grand World Map with Dolphin connected first.')
            return
        from .native_read import read_actors
        from ..Items import WORLD_ITEMS
        stage = next(iter(snap.evidence.get('native_data', {}).get('stage_objects', [])), {})
        try:
            actors=[a for a in read_actors(self.ctx.memory, stage['context'])
                    if self.ctx.memory.read_u32(a)==0x80777000]
            if len(actors) != 1:
                raise MemoryUnavailable('Grand World Map actor not unique')
            actor=actors[0]
            owned=self.ctx.runtime.test_inventory.apply(self._test_inventory_base())['counts']
            rows=[]
            for zone in range(1,6):
                present=bool(self.ctx.memory.read_u32(actor+0xB4+zone*8))
                allowed=bool(owned[WORLD_ITEMS[zone]])
                rows.append({'world':WORLD_ITEMS[zone].removesuffix(' Shuttle'),
                             'ap_owned':allowed,'castle_cache_present':present,
                             'cached_ui_mismatch':present and not allowed})
            log_diagnostic({'mission':snap.actual_mission, 'scene':snap.scene,
                            'history_ready':self.ctx.history_ready,'worlds':rows,
                            'note':'Presence of native cache handles is not proof of selectable map UI; reported visual-only mismatch still needs live repair.'})
        except (KeyError, MemoryUnavailable) as error:
            log_diagnostic({'error':str(error),'scene':snap.scene})

    def _cmd_sonicmovement(self):
        """Show current native movement states and AP permissions (READ ONLY)."""
        if not self.ctx.runtime:
            logger.info('Connect to a Sonic Colours slot first.')
            return
        from .movement_gate import permissions
        snap = self.ctx.runtime.snapshot
        stage = next(iter(snap.evidence.get('native_data',{}).get('stage_objects',[])),{}) if snap else {}
        player = stage.get('player',{})
        base = self._test_inventory_base()
        owned = self.ctx.runtime.test_inventory.apply(base)
        log_diagnostic({'mission':snap.actual_mission if snap else None,
                        'movement':player.get('movement'),
                        'owned_mask':permissions(owned['counts']),
                        'swim_item':bool(owned['counts']['Swim']),
                        'breath_item':bool(owned['counts']['Breath']),
                        'progressive_breathing':owned['counts']['Progressive Breathing'],
                        'test_inventory':self.ctx.runtime.test_inventory.describe(base),
                        'movement_status':self.ctx.runtime.movement_status})

    def _cmd_sonicwater(self):
        """Read-only PAL underwater stats; does NOT implement Swim/Breath gates."""
        if not self.ctx.runtime or not self.ctx.memory or not self.ctx.runtime.snapshot:
            logger.info('Connect to a Sonic Colours slot and Dolphin first.')
            return
        from .movement_gate import water_observed
        snap=self.ctx.runtime.snapshot
        stage=next(iter(snap.evidence.get('native_data',{}).get('stage_objects',[])),{})
        player=stage.get('player',{}).get('actor')
        if player is None:
            logger.info('Enter a Sonic gameplay stage to inspect water state.')
            return
        try:
            result=water_observed(self.ctx.memory,player)
            log_diagnostic({'mission':snap.actual_mission,'water':result,
                            'note':'Only read-only snapshot correlations: no trusted oxygen timer or bubble reset setter yet.'})
        except MemoryUnavailable as error:
            log_diagnostic({'error':str(error),'mission':snap.actual_mission})

    def _cmd_sonichud(self,action=''):
        """Report AP ticker events and native renderer proof gaps."""
        if not self.ctx.runtime:
            logger.info('Connect to a Sonic Colours slot first.');return
        runtime=self.ctx.runtime
        action=action.strip().lower()
        if action in ('on','off'):
            logger.info('AP HUD is always enabled when the native patch is installed.')
        elif action=='test':
            if not getattr(runtime,'hud_status',{}).get('font_ready'):
                logger.info('Enable /sonichud on and wait for a verified native HUD first.');return
            runtime.hud_ticker.enqueue({'kind':'Received','item':'HUD TEST Item','player':'Local preview',
                                       'flags':1,'local_test':True})
        elif action:
            logger.info('Usage: /sonichud [on|off|test]');return
        result=runtime.hud_ticker.diagnostics(True)
        result.update(getattr(runtime,'hud_status',{}))
        if result.get('hud_ready'):result['blocked_reason']=None
        if self.ctx.memory and not result.get('owner_verified'):
            try:
                from .ap_hud_native import probe
                result.update(probe(self.ctx.memory))
            except MemoryUnavailable as error:result['native_probe_reason']=str(error)
        log_diagnostic(result)

    def _cmd_sonicbinding(self):
        """Explain why the current AP save has or has not been attributed."""
        if not self.ctx.runtime:
            logger.info('Connect to a Sonic slot first.')
            return
        runtime=self.ctx.runtime;snap=runtime.snapshot
        journal=runtime.journal.data
        log_diagnostic({'playthrough':runtime.guard.state.value, 'save_armed':runtime.guard.armed,
                        'reason':runtime.guard.reason,
                        'save_identity_verified':bool(snap and snap.save_identity_verified),
                        'new_save_selected':bool(snap and snap.new_save_selected),
                        'stable_polls':snap.stable_polls if snap else None,
                        'scene':snap.scene if snap else None,
                        'bootstrap_present':bool(journal.get('bootstrap')),
                        'native_binding_present':bool(journal.get('native_binding')),
                        'intro_record_witness_count':len(journal.get('native_binding',{}).get('intro_record_witnesses',[])),
                        'note':'Diagnostic only. This command does not bypass the save binding guard.'})

    def _cmd_sonicmusictest(self, destination='', donor=''):
        """Audible test: DESTINATION_CUE DONOR_CUE, or off to restore the seed mapping."""
        if not self.ctx.runtime or not self.ctx.authenticated_identity:
            logger.info('Connect to your Sonic Colours slot first.')
            return
        from .music_bank import SHUFFLE_CUES
        if destination=='off' and not donor:
            self.ctx.runtime.music_test_pair=None
        elif (destination in SHUFFLE_CUES and donor in (SHUFFLE_CUES | {'bgm_sys_op','bgm_sys_end'})
              and self.ctx.runtime.slot_data['options']['music_randomization']):
            self.ctx.runtime.music_test_pair=(destination,donor)
        else:
            logger.info('Usage: /sonicmusictest LOOPING_DESTINATION DONOR, or /sonicmusictest off. Opening/ending donors are temporary auditions; looping is not guaranteed.')
            return
        self.ctx.runtime.next_music_poll=0
        logger.info('Music test pair: %s. Change scenes to restart the cue; /sonicmusictest off restores the seed mapping.',
                    self.ctx.runtime.music_test_pair)

    def _cmd_sonicsync(self):
        """Request the complete AP receipt history; never discard the durable journal."""
        if not self.ctx.runtime or not self.ctx.authenticated_identity:
            logger.info('Connect to your Sonic Colours slot first.')
            return
        logger.info('Requesting complete ReceivedItems history: server=%s durable=%s',
                    len(self.ctx.items_received),len(self.ctx.runtime.journal.data['receipts']))
        asyncio.create_task(self.ctx.send_msgs([{'cmd':'Sync'}]))

    @mark_raw
    def _cmd_sonicmusic(self, manifest=''):
        """Select a seed BGM patch manifest (path may contain spaces), or show music status. This does not install game resources."""
        if not self.ctx.runtime:
            logger.info('Connect to your Sonic Colours slot first.')
            return
        if manifest.strip():
            self.ctx.music_resource_manifest = manifest.strip().strip('"')
            self.ctx.runtime.select_resource_music(self.ctx.music_resource_manifest)
        log_diagnostic(self.ctx.runtime.music_status)

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
        report = diagnostic(self.ctx)
        if 'native_evidence' in report:
            report.pop('native_evidence')
            report['native_evidence_command'] = '/sonicdebug'
        if 'item_receipts' in report:
            report['item_receipt_count'] = len(report.pop('item_receipts'))
            report['item_receipts_command'] = '/sonicitems'
        log_diagnostic(report)

    def _cmd_sonicstatus(self):
        """Show current connection and write-block reason."""
        self._cmd_sonic()

    def _cmd_sonicdebug(self):
        """Inspect the small candidate pointer chain; never dumps whole RAM."""
        log_diagnostic(diagnostic(self.ctx, self.ctx.memory))

    @mark_raw
    def _cmd_sonicdeathtest(self, raw=''):
        """Local native kill test: /sonicdeathtest enable, then /sonicdeathtest kill. No broadcast."""
        action=raw.strip().lower()
        if action=='enable':
            self.ctx.native_death_test_enabled=True
            logger.info('Native death test enabled for this client session. /sonicdeathtest kill requests one ordinary death.')
        elif action=='kill' and getattr(self.ctx,'native_death_test_enabled',False):
            self.ctx.pending_native_death_test=True
            logger.info('One local native death requested; delivery waits for safe living gameplay.')
        else:logger.info('Test disabled by default. Use /sonicdeathtest enable, then /sonicdeathtest kill.')

    def _cmd_sonicdeathlinktest(self):
        """Receive one synthetic local DeathLink, without broadcasting to the server."""
        if not self.ctx.runtime:
            logger.info('Connect to an attributed Sonic Colours session first.');return
        if not self.ctx.deathlink:self.ctx.deathlink=DeathLink(self.ctx.runtime.journal)
        self.ctx.deathlink.receive({'source':'LOCAL TEST ONLY','time':time.time()},time.monotonic())
        logger.info('Synthetic incoming DeathLink queued locally. This command sends no DeathLink packet.')

    def _cmd_sonicmusicpreview(self):
        """Preview the currently captured native music cue for HUD placement."""
        runtime=self.ctx.runtime
        if not runtime or not getattr(runtime,'native_event_status',{}).get('cue_name'):
            logger.info('No captured native music cue is available.');return
        popup=getattr(runtime,'music_popup',None)
        if popup:
            popup.sequence=None;popup.cue=None
        panel=getattr(runtime,'_hud_connected',None)
        if panel:panel['music']=None
        logger.info('Music HUD preview requested for the current native cue; playback is unchanged.')

    @mark_raw
    def _cmd_sonictraptest(self,raw=''):
        """Explicit local Dead Weight test: /sonictraptest dead weight. No AP receipt or broadcast."""
        if raw.strip().lower()!='dead weight':
            logger.info('Use /sonictraptest dead weight for a 30-second local Jump lock.');return
        self.ctx.pending_trap_test=True

    @mark_raw
    def _cmd_soniclogs(self, raw=''):
        """Show suppressed routine client logs: /soniclogs [NUMBER|all|clear]."""
        argument = raw.strip().lower()
        if argument == 'clear':
            cleared = quiet_logging.clear()
            logger.info('Cleared %s stored Sonic diagnostic log entries.', cleared)
            return
        if argument in ('', 'last'):
            limit = 25
        elif argument == 'all':
            limit = None
        elif argument.isascii() and argument.isdecimal() and 1 <= int(argument) <= 500:
            limit = int(argument)
        else:
            logger.info('Usage: /soniclogs [1-500|all|clear]. Also: /sonicstatus, /sonicdebug, /sonicmovement, /sonicitems.')
            return
        log_diagnostic(quiet_logging.history(limit))

    def _cmd_sonicitems(self):
        """Show durable per-receipt delivery and reconciliation details."""
        if self.ctx.runtime:
            log_diagnostic(self.ctx.runtime.item_details())
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


def slot_identity_digest(data):
    """Keep old seed journals stable when adding a disabled optional trap."""
    if data.get('options_revision',0)<5 and data['options'].get('native_feature_tests')==0:
        data={**data,'options':{k:v for k,v in data['options'].items() if k!='native_feature_tests'}}
    if data.get('options_revision', 0) < 4:
        options = dict(data['options'])
        if options.get('dead_weight_trap_weight') == 0:
            options.pop('dead_weight_trap_weight', None)
        data = {**data, 'options': options}
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


class SonicContext(CommonContext):
    game = GAME
    items_handling = 0b111
    command_processor = SonicCommands

    def __init__(self, address=None, password=None, patch_file=None, journal_directory=None, music_resource_manifest=None):
        super().__init__(address, password)
        self.runtime = None
        self.deathlink = None
        self.memory = None
        self.sync_wakeup = asyncio.Event()
        self.history_ready = False
        self.history_desynced = False
        self.barrier = None
        self.dolphin_status = 'Waiting for Dolphin and AP slot.'
        self.server_seed = None
        self.authenticated_identity = None
        self.operation_status = {}
        self.expected_seed = None
        self.expected_slot_data = None
        self.expected_player = None
        self.music_resource_manifest = music_resource_manifest
        self.experimental_direct_hooks = False
        self.direct_hook_status = {'status':'disabled; existing Gecko hooks still supported'}
        self.direct_hook_attempted = False
        self.last_send = 0.0
        self.last_pending = set()
        self.implementation = implementation_info()
        self.latest_acknowledged_location = None
        self.status_time_utc = None
        self.dolphin_instance = None
        self.last_observed_checked = set()
        self.journal_directory = Path(journal_directory or Utils.user_path('sonic_colours_journals'))
        if patch_file:
            from ..patch import load_patch
            patch=load_patch(patch_file)
            self.expected_slot_data = patch.slot_data
            self.expected_seed = self.expected_slot_data['seed_name']
            self.auth = patch.player_name
            self.expected_player = patch.player

    async def server_auth(self, password_requested=False):
        if password_requested and not self.password:
            await super().server_auth(password_requested)
        if not self.auth:
            await self.get_username()
        await self.send_connect(game=GAME)

    def refresh_movement_permissions(self):
        runtime=self.runtime
        if runtime is None or self.memory is None or runtime.snapshot is None:return
        identity=runtime.journal.identity
        if self.authenticated_identity!=(identity['team'],identity['slot'],identity['seed']):return
        ids=([item.item for item in self.items_received] if self.history_ready
             else list(runtime.journal.data['receipts']))
        ids += [item for item in runtime.journal.data.get('permission_receipts',()) if item not in ids]
        runtime.refresh_movement_permissions(self.memory,runtime.effective_inventory(inventory(ids)))

    def release_runtime(self):
        if self.runtime:
            self.runtime.guard.disarm()
            self.runtime.journal.close()
        self.runtime = None
        self.deathlink = None

    def on_deathlink(self, data):
        super().on_deathlink(data)
        if self.deathlink and self.runtime and self.runtime.slot_data["options"].get("death_link", False):
            self.deathlink.receive(data, time.monotonic())

    def hud_item_name(self,item,slot):
        try:return self.item_names.lookup_in_slot(item,slot)
        except (KeyError,ValueError,AttributeError):return f'Item {item}'

    def hud_player_name(self,slot):
        return str(self.player_names.get(slot,f'Player {slot}'))

    def on_package(self, cmd, args):
        if cmd in ('Connected','ReceivedItems','RoomUpdate','Retrieved','Bounced'):
            wakeup=getattr(self,'sync_wakeup',None)
            if wakeup is not None:wakeup.set()
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
                if self.expected_player is not None and self.slot!=self.expected_player:
                    raise ValueError('server player slot differs from the player patch')
                if self.expected_slot_data and data != self.expected_slot_data:
                    raise ValueError('server slot data differs from loaded Sonic Colours player patch')
                if not self.server_seed:
                    raise ValueError('Connected requires a valid preceding RoomInfo server seed')
                if data['seed_name'] != self.server_seed:
                    raise ValueError(f'RoomInfo/Connected seed mismatch: team={self.team!r} slot={self.slot!r} server_seed={self.server_seed!r} slot_seed={data["seed_name"]!r}')
                self.authenticated_identity = (self.team, self.slot, self.server_seed)
                identity = {'seed': self.server_seed, 'team': self.team, 'slot': self.slot,
                            'revision': VERSION['dol_sha256'], 'game': GAME,
                            'slot_digest': slot_identity_digest(data)}
                # Freshly generated slots distinguish rooms hosting the same
                # generated seed. Legacy slots keep their existing journal key.
                if data.get('options_revision',0)>=5 and self.server_address:
                    from urllib.parse import urlsplit
                    endpoint=urlsplit(self.server_address if '://' in self.server_address else 'ws://'+self.server_address)
                    room=f'{(endpoint.hostname or "").lower()}:{endpoint.port or 38281}{endpoint.path.rstrip("/")}'
                    identity['room_endpoint']=hashlib.sha256(room.encode()).hexdigest()
                if not self.runtime or self.runtime.journal.identity != identity:
                    self.release_runtime()
                    journal = Journal(self.journal_directory, identity)
                    self.runtime = Runtime(data, journal, SaveGuard(journal), NativeHooks(journal))
                    self.runtime.experimental_direct_hooks = self.experimental_direct_hooks
                    if self.music_resource_manifest:
                        self.runtime.select_resource_music(self.music_resource_manifest)
                    if data['options']['death_link']:
                        self.deathlink = DeathLink(journal)
                asyncio.create_task(self.update_death_link(bool(data['options']['death_link'])))
                # CommonClient processes packets in order. An ordered Get reply
                # handles AP's omitted empty ReceivedItems without a timeout guess.
                self.barrier = f'_sonic_history_{time.monotonic_ns()}'
                asyncio.create_task(self.send_msgs([{'cmd': 'Get', 'keys': [self.barrier]}]))
                quiet_logging.record('connection', 'Sonic Colours (Wii) slot connected. New Game intro is detected automatically; /sonicdebug shows native proof gaps.')
            except (ValueError, KeyError, OSError) as error:
                self.authenticated_identity = None
                self.release_runtime()
                self.dolphin_status = f'Slot rejected: {error}'
                logger.error(self.dolphin_status)
        elif cmd == 'PrintJSON':
            if self.runtime and self.authenticated_identity==(self.team,self.slot,self.server_seed):
                self.runtime.hud_ticker.sent(args,self.team,self.slot,self.hud_item_name,self.hud_player_name)
        elif cmd == 'ReceivedItems':
            if self.runtime and self.authenticated_identity == (
                    self.runtime.journal.identity['team'],self.runtime.journal.identity['slot'],
                    self.runtime.journal.identity['seed']):
                try:
                    grants=[item[0] for item in args.get('items',())]
                    inventory(grants)
                    self.runtime.journal.record_permissions(grants)
                except (ValueError,OSError) as error:
                    logger.error('Permission receipt persistence blocked: %s',error)
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
                        quiet_logging.record('received_item', 'Item received / queued: receipt %s, %s', index, BY_ID[self.items_received[index].item])
                except (ValueError, OSError) as error:
                    self.history_ready = False
                    self.history_desynced = True
                    logger.error('Receipt synchronization blocked: %s', error)
            if self.runtime and self.history_ready and self.authenticated_identity==(self.team,self.slot,self.server_seed):
                index=args.get('index')
                if type(index) is int and 0<=index<=len(self.items_received):
                    self.runtime.hud_ticker.received(self.items_received[index:],index,lambda item:self.hud_item_name(item,self.slot),self.hud_player_name,self.slot)
            # Socket callbacks record durable receipts; the Dolphin loop owns
            # native permission writes. Do not block the next server packet
            # with controller, resource and executable probes here.
            self.operation_status['permission_refresh']='queued for Dolphin synchronization'
        elif cmd == 'Retrieved' and self.barrier in args.get('keys', {}) and not self.history_desynced:
            self.history_ready = True
            if self.runtime and self.authenticated_identity==(self.team,self.slot,self.server_seed):
                self.runtime.hud_ticker.history_ready(self.items_received)
        if cmd in ('Connected', 'RoomUpdate'):
            # CommonContext has already applied missing_locations before invoking
            # this callback. Only server-confirmed locations are acknowledgements.
            newly_checked = self.checked_locations - self.last_observed_checked
            if newly_checked:
                self.latest_acknowledged_location = {
                    'time_utc': datetime.now(timezone.utc).isoformat(),
                    'locations': sorted(newly_checked), 'packet': cmd}
                quiet_logging.record('location', 'Location acknowledged: %s', sorted(newly_checked))
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
    # Runtime already attributed these durable checks before journalling them.
    # Reconnect/DME loss must not strand that queue. This creates no new checks
    # from the currently loaded save; the AP room/team/slot identity below must
    # still match before any network send.
    earned = set(checks) | set(ctx.runtime.journal.data['checks'])
    goal = goal or bool(ctx.runtime.journal.data.get('goal_observed'))
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
        quiet_logging.record('transport', 'LocationChecks sent: %s', sorted(pending))
        ctx.last_pending, ctx.last_send = pending.copy(), time.monotonic()
        ctx.operation_status['ap_transport'] = 'sent; awaiting server acknowledgement'
    if goal and not ctx.finished_game:
        await ctx.send_msgs([{'cmd': 'StatusUpdate', 'status': ClientStatus.CLIENT_GOAL}])
        ctx.finished_game = True


async def poll_runtime(ctx,memory):
    runtime=ctx.runtime
    identity=runtime.journal.identity
    expected=(identity['team'],identity['slot'],identity['seed'])
    items=[item.item for item in ctx.items_received]
    steps=runtime.poll_steps(memory,items,ctx.history_ready)
    started=time.monotonic();longest=0.;phases=0
    backend=getattr(memory,'backend',None)
    counters=('read_calls','write_calls','process_enumerations')
    before={name:getattr(backend,name,0) for name in counters}
    blocking_ms=[]
    try:
        while True:
            try:
                phase_start=time.monotonic()
                try:
                    with memory.control_scope() if hasattr(memory,'control_scope') else nullcontext():
                        checks,goal=next(steps)
                finally:
                    duration=time.monotonic()-phase_start
                    longest=max(longest,duration);phases+=1
                    blocking_ms.append(round(duration*1000,2))
            except StopIteration as done:return done.value
            try:await transmit_checks(ctx,checks,goal)
            except (MemoryUnavailable,ConnectionClosed,OSError) as error:
                ctx.operation_status['ap_transport']='Location transmission pending: '+str(error)
            # Let socket acknowledgements and inventory messages run before
            # expensive data projection; no concurrent native-memory worker.
            await asyncio.sleep(0)
            if ctx.runtime is not runtime or ctx.authenticated_identity!=expected:
                return set(),False
            items[:]=[item.item for item in ctx.items_received]
    finally:
        steps.close()
        ctx.operation_status['sync_performance']={'cycle_ms':round((time.monotonic()-started)*1000,2),
            'longest_blocking_phase_ms':round(longest*1000,2),'phases':phases,
            'blocking_phases_ms':blocking_ms,
            'dolphin_io':{name:getattr(backend,name,0)-before[name] for name in counters},
            'strategy':'authenticated fast scene reads; fresh write proofs; AP checkpoints'}


async def wait_for_sync(ctx,delay):
    """Incoming AP traffic wakes idle synchronization without a busy wait."""
    wakeup=getattr(ctx,'sync_wakeup',None)
    if wakeup is None:
        await asyncio.sleep(delay);return
    if wakeup.is_set():
        wakeup.clear()
        return
    try:
        await asyncio.wait_for(wakeup.wait(), delay)
    except asyncio.TimeoutError:
        # Do not erase a wakeup that arrived concurrently with the timeout.
        return
    wakeup.clear()


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
    quiet_logging.record('implementation', 'Sonic implementation: %s', json.dumps(ctx.implementation, sort_keys=True))
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
                memory.required_native_seed=(ctx.expected_seed or ctx.server_seed if getattr(ctx,'generated_iso',None) else None)
                if getattr(memory,'native_patch',None) and ctx.server_seed:
                    memory.required_native_seed=ctx.server_seed
                backend.assert_instance(ctx.dolphin_instance)
                if not backend.active():
                    verified = False
                    if ctx.runtime:
                        ctx.runtime.guard.disarm()
                        ctx.runtime.hooks.invalidate_session()
                    raise MemoryUnavailable('Waiting for running Dolphin emulation.')
                if not verified and not ctx.runtime:
                    memory.verify_revision()
                    verified = True
                if not ctx.runtime:
                    raise MemoryUnavailable('PAL executable verified; waiting for AP slot.')
                memory.write_guard = WritePolicy(memory, ctx.runtime.guard, ctx.runtime.hooks.snapshot)
                if ctx.experimental_direct_hooks and ctx.direct_hook_status.get('status', '').startswith('FAILED'):
                    raise MemoryUnavailable('EXPERIMENT BLOCKED: restart Dolphin and client after a partial experimental install')
                if ctx.experimental_direct_hooks and not ctx.direct_hook_attempted:
                    # A valid DME attachment alone does not prove the guest disc
                    # header is ready. During Dolphin boot/reset, an all-zero
                    # header must defer the experiment, not permanently mark a
                    # never-attempted installation as partially failed.
                    # No guest writes are permitted before a full verified PAL
                    # revision check succeeds. Re-check on the next poll.
                    try:
                        memory.verify_revision()
                    except MemoryUnavailable as error:
                        ctx.direct_hook_status = {
                            'status': 'WAITING: verified PAL executable required before experimental install',
                            'preflight_error': str(error),
                            'installed_in_guest_ram': False,
                            'jit_execution_verified': False,
                        }
                        raise
                    # Intentional once-per-session experiment AFTER preflight.
                    # Only installation-phase errors require a full restart;
                    # the installer refuses unsafe scratch RAM or mismatched code.
                    ctx.direct_hook_attempted = True
                    try:
                        from .direct_hooks import install, inspect
                        movement = bool(ctx.runtime.slot_data['options']['movement_unlocks'])
                        ctx.direct_hook_status = (install(memory, enable_movement=movement) if not inspect(memory, enable_movement=movement) else
                                                  {'installed_in_guest_ram':True, 'jit_execution_verified':False,
                                                   'status':'existing experimental signatures recognized'})
                        logger.warning('EXPERIMENTAL guest code: %s', ctx.direct_hook_status)
                    except (MemoryUnavailable, ValueError, OSError) as error:
                        ctx.direct_hook_status = {'status':'FAILED; restart Dolphin: '+str(error)}
                        logger.error('EXPERIMENTAL hook installation failed, restart Dolphin: %s', error)
                        # A partial installation cannot safely continue writing.
                        raise MemoryUnavailable('EXPERIMENT BLOCKED: '+str(error))
                checks, goal = await poll_runtime(ctx,memory)
                verified = bool((memory.revision_observation or {}).get('verified'))
                if ctx.deathlink:
                    snap = ctx.runtime.snapshot
                    native=getattr(ctx.runtime,'native_event_status',{})
                    if native.get('installed'):
                        from .event_controls import safe_kill,cancel_kill
                        local_death = ctx.deathlink.poll(
                            safe=bool(snap.scene_verified and (ctx.runtime.guard.can_record_pickups(snap) or
                                      native['death_stage'] in getattr(ctx.runtime,'_death_allowed_stages',set()))),
                            native_state=snap.death_state, now=time.monotonic(),
                            native_sequence=native['death_sequence'],remote_ack=native['remote_ack'],
                            kill_safe=safe_kill(snap),
                            cancel=lambda:cancel_kill(memory,snap,ctx.runtime.guard,ctx.deathlink.remote_request),
                            kill=lambda: ctx.runtime.hooks.kill(memory, snap))
                        if local_death and ctx.runtime.slot_data['options']['death_link']:
                            await ctx.send_death('Sonic died.')
                if getattr(ctx,'pending_native_death_test',False):
                    from .event_controls import safe_kill
                    if safe_kill(ctx.runtime.snapshot):
                        if ctx.deathlink:
                            ctx.deathlink.remote_cycle=True
                            ctx.deathlink.journal.data['remote_cycle']=True
                            ctx.deathlink.journal.save()
                        request=ctx.runtime.hooks.kill(memory,ctx.runtime.snapshot)
                        ctx.pending_native_death_test=False
                        logger.debug('Local native kill request %s published; no network event sent.',request)
                if getattr(ctx,'pending_trap_test',False):
                    from .dead_weight import test_request
                    request=test_request(ctx.runtime,memory)
                    ctx.pending_trap_test=False
                    logger.debug('Local Dead Weight request %s published; awaiting native ACK.',request)
                # Runtime returns durable checks only after current attribution
                # is valid. Do not bypass its identity gate by rereading journal.
                snap = ctx.runtime.snapshot
                ctx.operation_status.update(
                    native_events=getattr(ctx.runtime,'native_event_status',{}),
                    wisp_inventory=getattr(ctx.runtime,'wisp_inventory_status',{}),
                    deathlink=ctx.deathlink.status() if ctx.deathlink else {'status':'disabled'},
                    gameplay_detection={'scene': snap.scene, 'mission': snap.actual_mission, 'verified': snap.scene_verified},
                    pickup_detection={'verified': snap.pickup_verified, 'authorized': ctx.runtime.guard.can_record_pickups(snap),
                                      'capsule_capture':getattr(ctx.runtime,'capsule_capture_status',{})},
                    journal_persistence={'durable_events': len(ctx.runtime.journal.data['pickup_events']), 'earned_checks': len(ctx.runtime.journal.data['checks']), 'persistence_pending': ctx.runtime.journal.persistence_pending},
                    capsule_refresh=ctx.runtime.hooks.capsule_refresh_status,
                    physical_red_rings=getattr(ctx.runtime,'physical_ring_status',{}),
                    game_land_unlock_animation=getattr(ctx.runtime,'game_land_notice_status',{}),
                    breath=getattr(ctx.runtime,'breath_status',{}),
                    native_progression=ctx.runtime.hooks.progression_status,
                    native_gameplay_controls=ctx.runtime.hooks.gameplay_controls_status,
                    boost_gain_guard=ctx.runtime.boost_gain_status,
                    movement_unlocks=ctx.runtime.movement_status,
                    global_map_refresh=ctx.runtime.hooks.global_map_refresh_status,
                    native_egg_medals=ctx.runtime.hooks.medal_status,
                    music_randomization=ctx.runtime.music_status,
                    experimental_direct_hooks=ctx.direct_hook_status,
                    item_writes={'history_ready': ctx.history_ready, 'pending_receipts': ctx.runtime.pending_effects(), 'status': ctx.runtime.last_error})
                ctx.dolphin_status = (snap.status if snap.evidence.get('executable_error')
                                      else ctx.runtime.guard.reason)
            except MemoryUnavailable as error:
                ctx.dolphin_status = str(error)
                ctx.operation_status['gameplay_detection'] = str(error)
                ctx.operation_status['pickup_detection'] = {'verified': False, 'authorized': False}
                ctx.operation_status['item_writes'] = {'suspended': True, 'reason': str(error)}
                if ctx.runtime:
                    ctx.runtime.snapshot = None
                    if ctx.runtime.hooks.reject_observation(memory.revision_observation, str(error)):
                        ctx.runtime.guard.disarm()
                    else:
                        ctx.runtime.guard.suspend()
                if str(error).startswith(('wrong_game', 'unknown_revision')):
                    verified = False
                    try:
                        if backend.recover_empty_text_mapping(error):
                            ctx.dolphin_status='Reattaching Dolphin after repeated empty native text reads; PAL verification pending'
                            if ctx.runtime:ctx.runtime.hooks.invalidate_session()
                    except (MemoryUnavailable,RuntimeError,OSError):
                        pass
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
                quiet_logging.record('dolphin_status', 'Current Dolphin status [%s, instance=%s]: %s', ctx.status_time_utc,
                            json.dumps(ctx.dolphin_instance, sort_keys=True), ctx.dolphin_status)
            # Five-bit masks persist through normal gameplay, so bulk bit changes
            # capture multiple rings. Sample promptly; capsule pulses will need a
            # native retained event source, not an assumption about this interval.
            delay=(max(0.001,0.02-(time.monotonic()-started))
                   if backend.active() and ctx.runtime else .25)
            await wait_for_sync(ctx,delay)
    finally:
        backend.close()
        ctx.memory = None
        if dolphin.is_hooked():
            dolphin.un_hook()


async def main(args):
    ctx = SonicContext(args.connect, args.password, args.patch_file,
                       music_resource_manifest=getattr(args, 'music_resource_manifest', None))
    ctx.auth = args.name or ctx.auth
    ctx.generated_iso=getattr(args,'generated_iso',None)
    ctx.experimental_direct_hooks = bool(getattr(args, 'experimental_direct_hooks', False))
    ctx.server_task = asyncio.create_task(server_loop(ctx), name='ServerLoop')
    if gui_enabled and not getattr(args, 'nogui', False):
        ctx.run_gui()
    dolphin_launch_status=getattr(args,'dolphin_launch_status',None)
    if dolphin_launch_status and dolphin_launch_status.get('restarted'):
        logger.info('Dolphin was restarted with the patched ISO: %s',ctx.generated_iso)
    ctx.run_cli()
    watcher = asyncio.create_task(dolphin_loop(ctx), name='SonicDolphin')
    try:
        await ctx.exit_event.wait()
    finally:
        ctx.exit_event.set()
        await watcher
        ctx.release_runtime()
        await ctx.shutdown()
