"""Experimental, opt-in native area-pass boundary controller.

Auburn (SF_Docks) is ALWAYS unlocked, independently of AP receipts.
The native DLL owns the actual actor/vehicle transform and save/seed checks;
this module never accepts arbitrary coordinates, never writes game memory itself,
and never assumes a requested return actually happened.

WARNING: the native return currently works only near a previously captured
checkpoint for the SAME actor/vehicle in the SAME process and bound save. Distant
fast travel, loading inside a locked district, and vehicle switching while
locked cannot safely be recovered by this mechanism. This is NOT a full native
barrier or a guaranteed softlock-free mode.
"""
import asyncio
from collections import deque
from datetime import datetime, timezone
import logging
import json
import re
import time

try:
    from .research_profile import ABILITY_NAMES
except ImportError:
    from research_profile import ABILITY_NAMES

DISTRICTS = tuple(name for name in ABILITY_NAMES if name.startswith(('SF_', 'WI_', 'NY_', 'IS_', 'BR_')))
START = 'SF_Docks'
FIRST = 'SF_Residential'
# These were observed reachable in the opening Auburn save without Police.
# Native interaction and resource requirements beyond that evidence remain partial.
FIRST_PASS_KEYS = frozenset((
    'objective:DisguiseBooth_SF_DO_0918',
    'source_pickup:GAME5/levels/lego_city/lego_city/sf_docks/sf_docks_0715/sf_docks_0715.giz:27:7',
    'source_pickup:GAME5/levels/lego_city/lego_city/sf_docks/sf_docks_1018/sf_docks_1018.giz:722:3',
))
# Source-backed Auburn candidates. Police Station and SF_Residential are NOT
# opening Auburn placements, even when available in an older opening catalogue.
AUBURN_OPENING_KEYS = FIRST_PASS_KEYS | frozenset((
    'source_pickup:GAME5/levels/lego_city/lego_city/sf_docks/sf_docks_0817/sf_docks_0817.giz:1174:4',
    'source_pickup:GAME5/levels/lego_city/lego_city/sf_docks/sf_docks_0817/sf_docks_0817.giz:1174:5',
    'source_pickup:GAME5/levels/lego_city/lego_city/sf_docks/sf_docks_0817/sf_docks_0817.giz:1174:6',
    'story_arrest:clown_1',
))

CAPTURE_INTERVAL_SECONDS = 0.65
RETURN_RECHECK_SECONDS = 1.0
SAFE_CONTEXTS = frozenset((11, 46, 124, 152, 157))  # RideAlong still requires a live mounted vehicle natively.
# Native command rejection codes 1-22 are confirmed rejection replies before
# teleport for the area command, except unknown/native faults. In particular
# 20/21/22 are a deterministic reason NOT to retry until re-entering allowed land.
DEFINITIVE_RETURN_CODES = frozenset((1, 3, 4, 5, 6, 13, 20, 21, 22))
_REJECTION = re.compile(r'Native command rejected \((\d+)\):')


def canonical(value):
    if not isinstance(value, str):
        return None
    aliases = {name.casefold(): name for name in DISTRICTS}
    aliases['ny_monaco_tunnel'] = 'NY_Tunnel'
    return aliases.get(value.strip().casefold())


def tile_district(tile):
    if not isinstance(tile, str):
        return None
    prefix, marker, suffix = tile.rpartition('_')
    if not marker or len(suffix) != 4 or not suffix.isascii() or not suffix.isdigit():
        return None
    return canonical(prefix)


def allowed_districts(effects):
    result = {START}
    for effect in effects:
        if not isinstance(effect, dict) or effect.get('category') != 'area_pass':
            continue
        district = canonical(effect.get('native_name') or
                             str(effect.get('name', '')).removeprefix('Area Pass: '))
        if district:
            result.add(district)
    return result


def apply_test_restrictions(allowed, journal):
    """Read a seed-bound local deny-list; never edit server receipts or saves."""
    path = getattr(journal, 'directory', None)
    if path is None:
        return allowed
    try:
        data = json.loads((path / 'area_test_restrictions.json').read_text(encoding='utf-8'))
        if data.get('binding') != journal.binding_token.hex():
            return allowed
        blocked = {canonical(name) for name in data.get('blocked', [])}
        return (allowed - blocked) | {START}
    except FileNotFoundError:
        return allowed
    except (OSError, ValueError, TypeError):
        logging.warning('AREA test restrictions unreadable; retaining AP permissions')
        return allowed


def has_area(state, player, district):
    """Generation-time access: one pass per actual native district, Auburn free."""
    district = canonical(district)
    if district is None:
        return False
    if district == START:
        return True
    # Keep the historical lower-case alias available to already-created seeds.
    return (state.has('Area Pass: ' + district, player) or
            state.has('Area Pass: ' + district.lower(), player))


def auburn_opening_key(key, row):
    """A stricter test than NO_POLICE_KEYS when randomized area gating is on.

    Note: story_disguise:COP and police_station source pickups must remain
    reachable *after* the Cherry Tree Hills pass, not as Auburn checks.
    """
    if key not in AUBURN_OPENING_KEYS:
        return False
    if key == 'story_arrest:clown_1':
        return True
    district = canonical(row.get('district'))
    if district is None:
        source = str(row.get('source', '')).lower()
        if '/police_station/' in source or '/sf_residential/' in source:
            return False
        district = START if '/sf_docks/' in source else None
    return district == START


def _native_failure_code(error):
    match = _REJECTION.search(str(error))
    return int(match.group(1)) if match else None


def movement_diagnostic(snapshot):
    actor=snapshot.get('actor') or {}
    context=actor.get('context') or {}
    name=str(actor.get('equipped_internal_name') or '').casefold()
    ride=snapshot.get('ride') or {}
    if (snapshot.get('ridden') or {}).get('status')=='native_ridden_character':
        kind='ridden_character';reason='original GetRidden target; preserve rider relationship and teleport creature'
    elif name == 'behemoth':
        kind='takeover_creature';reason='T-Rex Behemoth: native character takeover; not an ApiVehicle'
    elif context.get('index') == 11:
        kind='passenger_or_scripted_ride';reason='requires live mounted vehicle; rail route restoration remains unverified'
    elif context.get('index') == 157:
        kind='mounted_vehicle';reason='same live vehicle checkpoint required'
    elif context.get('index') == 46:
        kind='default';reason='unmounted character or separate creature identity must be validated natively'
    else:
        kind='scripted_or_transition';reason='no general context override; native actor/ride relationship not proven'
    return dict(kind=kind,context=context,vehicle_class=ride.get('native_class'),reason=reason)


class AreaGate:
    """Host polling state machine around the guarded native snapshot/return RPC.

    Accepted returns can be repeated after a fresh forbidden-area observation
    and a cooldown. Rejected or uncertain commands remain latched. Captures refresh in a permitted
    district, including immediately on foot<->vehicle context changes.
    """
    def __init__(self):
        self.identity = None
        self.checkpoint = None
        self.checkpoint_position = None
        self.checkpoint_context = None
        self.foot_checkpoint = None
        self.checkpoint_ride = None
        self.last_return_observation = None
        self.test_blocked=[]
        self.pending = None
        self.problem = None
        self.last_capture = 0.0
        self.last_status = None
        self.events = deque(maxlen=200)
        self.event_identity = None
        self.last_reported_event = None

    def _reset_for_binding(self, identity):
        # A saved checkpoint must NEVER survive a PID, AP slot or save binding
        # change. Its native counterpart has independent identity protection.
        self.__init__()
        self.identity = identity

    async def poll(self, session, snapshot, journal, received, dll, backup_ready=False):
        identity = (session.pid, journal.binding_token)
        if (snapshot.get('native_binding') or {}).get('bank'):
            identity += ((snapshot['native_binding']['bank'],snapshot.get('process',{}).get('profile'),
                          snapshot.get('actor',{}).get('address')),)
        if identity != self.identity:
            self._reset_for_binding(identity)
        status = await self._poll(session, snapshot, journal, received, dll, backup_ready)
        location = snapshot.get('location') or {}
        actor = snapshot.get('actor') or {}
        district = tile_district(location.get('native_tile'))
        context = (actor.get('context') or {}).get('index')
        scene = (snapshot.get('mission_shield') or {}).get('scene')
        event_identity = (status, district, scene, context, str(self.problem))
        if event_identity != self.event_identity:
            self.event_identity = event_identity
            self.events.append(dict(
                timestamp=datetime.now(timezone.utc).isoformat(), status=status,
                district=district, native_tile=location.get('native_tile'),
                position=location.get('player_position'), scene=scene,
                context=context, ride=snapshot.get('ride'),ridden=snapshot.get('ridden'),
                movement=movement_diagnostic(snapshot),
                save_binding=journal.binding_token.hex(),
                checkpoint=self.checkpoint,
                checkpoint_position=self.checkpoint_position,
                checkpoint_context=self.checkpoint_context,
                position_write_requested=status in ('return_requested', 'disembark_requested','return_uncertain'),
                native_save_written=False, error=self.problem,
                verification='native_binding_verified' if status=='checkpoint_recorded' else 'unsupported' if status in
                    ('locked_area_without_checkpoint','locked_area_without_foot_checkpoint','disembark_not_observed') else 'observation',
                return_observation=self.last_return_observation,
                recovery=('Kehre nach Auburn zurück oder lade einen dort gespeicherten Teststand. Kein automatischer Fernteleport.'
                          if status in ('locked_area_without_checkpoint','locked_area_without_foot_checkpoint') else None)))
        return status

    def report(self):
        return dict(format='LCU area rollback evidence', version=2,
                    experimental=True, test_blocked=self.test_blocked,events=list(self.events))

    async def _poll(self, session, snapshot, journal, received, dll, backup_ready):
        if not backup_ready:
            return 'waiting_for_save_backup'
        location = snapshot.get('location') or {}
        actor = snapshot.get('actor') or {}
        district = tile_district(location.get('native_tile'))
        context = (actor.get('context') or {}).get('index')
        scene = (snapshot.get('mission_shield') or {}).get('scene', '')
        if scene and str(scene).casefold() != 'lego_city' and tile_district(scene) is None:
            return 'deferred_scene_or_context'
        if actor.get('status') != 'read' or context not in SAFE_CONTEXTS or district is None:
            return 'deferred_scene_or_context'

        allowed = apply_test_restrictions(allowed_districts(received), journal)
        self.test_blocked=sorted(allowed_districts(received)-allowed)
        if district in allowed:
            had_pending = self.pending is not None
            if had_pending:
                target=self.pending.get('target_position');observed=location.get('player_position')
                distance=(sum((float(a)-float(b))**2 for a,b in zip(target,observed))**.5
                          if target and observed and len(target)==len(observed)==3 else None)
                permission_received=self.pending.get('district')==district
                self.last_return_observation=dict(allowed_area_observed=True,permission_received=permission_received,
                    returned_from_denied_district=not permission_received,distance_to_requested_pose=distance,
                    pose_observed=distance is not None and distance<=3.0,
                    controls_physics_and_save_verified=False,verification='observation')
                logging.info('AREA returned to an allowed district; exact native return pose is not independently proven')
                self.pending = None
            now = time.monotonic()
            if (not had_pending and self.checkpoint == district and self.checkpoint_context == context
                    and now - self.last_capture < CAPTURE_INTERVAL_SECONDS):
                return 'allowed'
            from native_model_transport import area_command
            try:
                result = await asyncio.to_thread(
                    area_command, session.pid, district, journal.binding_token, dll, fresh=self.checkpoint is None)
            except Exception as error:
                self.problem = str(error)
                logging.warning('AREA checkpoint not captured: %s', error)
                return 'checkpoint_unavailable'
            if not result.get('accepted'):
                self.problem = 'native command returned checkpoint accepted=false'
                return 'checkpoint_unconfirmed'
            self.checkpoint = district
            self.checkpoint_context = context
            self.checkpoint_position = result.get('target_position') or location.get('player_position')
            self.checkpoint_ride=(snapshot.get('ride') or {}).get('vehicle_interface')
            if context==46 and result.get('movement_kind',0)==0 and (snapshot.get('ridden') or {}).get('status')!='native_ridden_character' and (snapshot.get('ride') or {}).get('status') in (None,'not_mounted','expired_weak_reference'):
                self.foot_checkpoint=district
            self.problem = None
            self.last_capture = now
            return 'checkpoint_recorded'

        # The current snapshot belongs to a forbidden district. We do not
        # calculate or write coordinates in Python; native rechecks the actor,
        # ride, exact tile, maximum distance and bound save atomically.
        if not self.checkpoint or self.checkpoint not in allowed:
            if self.checkpoint:self.problem='Recorded checkpoint district no longer has an Area Pass'
            return 'locked_area_without_checkpoint'
        passenger = (context==11 or (snapshot.get('ride') or {}).get('player_role')=='passenger'
                     or bool((snapshot.get('ride') or {}).get('rail_transport')))
        changed_vehicle=(self.checkpoint_ride and (snapshot.get('ride') or {}).get('vehicle_interface') and
                         self.checkpoint_ride!=(snapshot.get('ride') or {})['vehicle_interface'])
        # An exit can occur entirely between polls while still on locked land.
        # The vehicle checkpoint then cannot be used by the unmounted actor.
        foot_after_vehicle=(context==46 and self.checkpoint_context!=46 and self.foot_checkpoint
                            and (snapshot.get('ride') or {}).get('status') in (None,'not_mounted','expired_weak_reference'))
        disembarking = self.pending is not None and self.pending.get('mode')=='disembark'
        if passenger or disembarking or foot_after_vehicle or changed_vehicle:
            if not self.foot_checkpoint or self.foot_checkpoint not in allowed:
                return 'locked_area_without_foot_checkpoint'
            if foot_after_vehicle and self.pending and self.pending.get('state')=='rejected' and self.pending.get('code')==21:
                # Confirmed no-op: vehicle identity changed. A separately
                # validated foot anchor is now the correct return target.
                self.pending=None
            if self.pending and self.pending.get('state') in ('uncertain','rejected'):
                return 'return_waiting_for_observation'
            if self.pending and self.pending.get('state')=='accepted' and time.monotonic()-self.pending['issued_at']<RETURN_RECHECK_SECONDS:
                return 'return_waiting_for_observation'
            started=(self.pending or {}).get('started_at',time.monotonic())
            if disembarking and context!=46 and time.monotonic()-started>5.0:
                return 'disembark_not_observed'
            from native_model_transport import area_disembark, NativePlayerBusy
            try:
                result=await asyncio.to_thread(area_disembark,session.pid,district,journal.binding_token,dll)
            except NativePlayerBusy:
                return 'deferred_player_busy'
            except Exception as error:
                self.problem=str(error)
                self.pending=dict(state='uncertain',district=district,error=str(error))
                return 'return_uncertain'
            if not result.get('accepted'):
                self.pending=dict(state='uncertain',district=district)
                return 'return_uncertain'
            self.pending=dict(state='accepted' if result.get('foot_return_requested') else 'disembarking',
                              district=district,mode='disembark',issued_at=time.monotonic(),started_at=started,
                              target_position=result.get('target_position'))
            return 'return_requested' if result.get('foot_return_requested') else 'disembark_requested'
        if self.pending is not None:
            if self.pending.get('state') == 'accepted':
                # Held movement may cross the boundary again between polls,
                # so an allowed snapshot is not guaranteed after a successful
                # return. Revalidate through the native command after cooldown.
                # A timeout/unknown result never reaches this retry branch.
                if time.monotonic() - self.pending['issued_at'] < RETURN_RECHECK_SECONDS:
                    return 'return_waiting_for_observation'
                self.pending = None
            elif self.pending.get('state') == 'rejected':
                return 'return_rejected_safe'
            else:
                return 'return_waiting_for_observation'
        from native_model_transport import area_command, NativePlayerBusy
        try:
            result = await asyncio.to_thread(
                area_command, session.pid, district, journal.binding_token, dll, True)
        except NativePlayerBusy:
            # Explicit rejection BEFORE mutation, safe to retry on the next poll.
            return 'deferred_player_busy'
        except Exception as error:
            code = _native_failure_code(error)
            self.problem = str(error)
            if code in DEFINITIVE_RETURN_CODES:
                self.pending = dict(state='rejected', district=district,
                                    checkpoint=self.checkpoint, code=code)
                logging.warning('AREA return safely rejected (%s); not retrying in locked area', code)
                return 'return_rejected_safe'
            # A timeout or native-call fault could have moved the actor. We
            # must never retry until an allowed district has been observed.
            self.pending = dict(state='uncertain', district=district,
                                checkpoint=self.checkpoint, error=str(error))
            logging.warning('AREA return outcome uncertain; automatic retry disabled: %s', error)
            return 'return_uncertain'
        if not result.get('accepted'):
            self.problem = 'native return command replied accepted=false'
            self.pending = dict(state='uncertain', district=district)
            return 'return_uncertain'
        self.problem = None
        self.pending = dict(state='accepted', district=district,
                            checkpoint=self.checkpoint, issued_at=time.monotonic(),target_position=result.get('target_position'))
        logging.info('AREA return requested: from %s to %s; awaiting fresh native observation',
                     district, self.checkpoint)
        return 'return_requested'
