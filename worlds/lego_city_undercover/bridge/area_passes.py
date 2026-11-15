"""Explicit opt-in boundary rollback. Auburn is never locked.

No world-coordinate guesses: area is the native grid tile's canonical prefix.
Unknown areas and scripted scenes defer; native code revalidates every command.
"""
import asyncio
import logging
import time
from collections import deque
from datetime import datetime,timezone
try:
    from .research_profile import ABILITY_NAMES
except ImportError:
    from research_profile import ABILITY_NAMES

DISTRICTS=tuple(n for n in ABILITY_NAMES if n.startswith(('SF_','WI_','NY_','IS_','BR_')))
START='SF_Docks'
FIRST='SF_Residential'
FIRST_PASS_KEYS=frozenset((
    'objective:DisguiseBooth_SF_DO_0918',
    'source_pickup:GAME5/levels/lego_city/lego_city/sf_docks/sf_docks_0715/sf_docks_0715.giz:27:7',
    'source_pickup:GAME5/levels/lego_city/lego_city/sf_docks/sf_docks_1018/sf_docks_1018.giz:722:3',
)) # User-confirmed fresh-slot checks before Police; not all Auburn candidates.


def canonical(value):
    aliases={d.casefold():d for d in DISTRICTS};aliases['ny_monaco_tunnel']='NY_Tunnel'
    return aliases.get(str(value).casefold())


def tile_district(tile):
    prefix,_,suffix=str(tile).rpartition('_')
    return canonical(prefix) if len(suffix)==4 and suffix.isascii() and suffix.isdigit() else None


def allowed_districts(effects):
    result={START}
    for effect in effects:
        if effect.get('category')=='area_pass':
            area=canonical(effect.get('native_name') or effect.get('name','').removeprefix('Area Pass: '))
            if area:result.add(area)
    return result


def has_area(state,player,district):
    return district==START or any(state.has('Area Pass: '+alias,player) for alias in (district,district.lower()))


class AreaGate:
    def __init__(self):
        self.identity=None;self.checkpoint=None;self.pending=None;self.problem=None;self.last_capture=0;self.last_status=None
        self.events=deque(maxlen=200);self.event_identity=None;self.checkpoint_position=None
        self.last_reported_event=None

    async def poll(self,session,snapshot,journal,received,dll,backup_ready=False):
        status=await self._poll(session,snapshot,journal,received,dll,backup_ready)
        location=snapshot.get('location',{});district=tile_district(location.get('native_tile'))
        identity=(status,district,snapshot.get('mission_shield',{}).get('scene'))
        if identity!=self.event_identity:
            self.event_identity=identity
            self.events.append(dict(timestamp=datetime.now(timezone.utc).isoformat(),status=status,district=district,
                native_tile=location.get('native_tile'),position=location.get('player_position'),
                scene=snapshot.get('mission_shield',{}).get('scene'),save_binding=journal.binding_token.hex(),
                ride=snapshot.get('ride'),
                checkpoint=self.checkpoint,checkpoint_position=self.checkpoint_position,
                position_write_requested=status in ('return_requested','return_uncertain'),
                native_save_written=False,error=self.problem))
        return status

    def report(self):
        return dict(format='LCU area rollback evidence',version=1,experimental=True,events=list(self.events))

    async def _poll(self,session,snapshot,journal,received,dll,backup_ready=False):
        if not backup_ready:return 'waiting_for_save_backup'
        identity=(session.pid,journal.binding_token)
        if identity!=self.identity:
            self.__init__();self.identity=identity
        actor=snapshot.get('actor',{});context=actor.get('context',{}).get('index')
        location=snapshot.get('location',{});district=tile_district(location.get('native_tile'))
        scene=snapshot.get('mission_shield',{}).get('scene','')
        if scene and str(scene).casefold()!='lego_city' and tile_district(scene) is None:return 'deferred_scene_or_context'
        if actor.get('status')!='read' or context not in (46,157) or not district:return 'deferred_scene_or_context'
        allowed=allowed_districts(received);now=time.monotonic()
        if district in allowed:
            if self.pending:
                logging.info('AREA allowed district observed after return request: %s (not proof of exact restored coordinates)',district);self.pending=None
            if now-self.last_capture<0.8:return 'allowed'
            self.last_capture=now
            from native_model_transport import area_command
            try:result=await asyncio.to_thread(area_command,session.pid,district,journal.binding_token,dll)
            except Exception as error:
                if self.problem!=str(error):logging.warning('AREA checkpoint unavailable: %s',error)
                self.problem=str(error);return 'checkpoint_unavailable'
            if result['accepted']:
                self.checkpoint=district;self.checkpoint_position=location.get('player_position');self.problem=None
            return 'checkpoint_recorded' if result['accepted'] else 'checkpoint_unconfirmed'
        if not self.checkpoint:return 'locked_area_without_checkpoint'
        if self.pending:
            # Never repeat a teleport after an uncertain reply/failed observation.
            return 'return_waiting_for_observation'
        self.pending=dict(district=district,time=now)
        from native_model_transport import area_command,NativePlayerBusy
        try:
            result=await asyncio.to_thread(area_command,session.pid,district,journal.binding_token,dll,True)
        except NativePlayerBusy:
            self.pending=None;return 'deferred_player_busy' # explicit rejection before mutation
        except Exception as error:
            self.problem=str(error);logging.warning('AREA return stopped; no automatic retry: %s',error)
            return 'return_uncertain'
        logging.info('AREA locked: %s; return to %s accepted=%s; awaiting observed position',district,self.checkpoint,result['accepted'])
        return 'return_requested'
