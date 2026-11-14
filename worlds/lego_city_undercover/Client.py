"""Experimental AP client with automatic checks and opt-in native model grants.

Bound native models, tools, cheats and currency use the opt-in item bridge.
Story/area entrance gates and open-world setup remain unavailable.
"""
import argparse
import asyncio
import logging
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(Path(__file__).parent/'bridge'))
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
from station_exit import StationExitGate,read_station_exit,can_resume_first_lobby,read_lobby_lift
from native_model_transport import trigger_station_exit,open_lobby_lift
from activity_rewards import completed_activity_rewards


class Commands(ClientCommandProcessor):
    def _cmd_check(self, location_id: str):
        """Manually report an active location ID after performing its action."""
        try:location=int(location_id)
        except ValueError:return False
        if str(location) not in self.ctx.catalogue:
            self.output('ID not active in this seed');return False
        if self.ctx.journal is None:
            self.output('Wait for the connected journal to initialize');return False
        asyncio.create_task(self.ctx.report_checks([location]))
        return True


class Context(CommonContext):
    game='LEGO City Undercover'
    items_handling=0b111
    command_processor=Commands

    def __init__(self,args):
        super().__init__(args.connect,args.password)
        self.auth=args.name
        self.catalogue={}
        self.slot_options={}
        self.enable_skip=args.enable_cutscene_skip
        self.native_save_file=getattr(args,"native_save_file",None)
        self.enable_native_models=args.enable_native_models
        self.skip_slot=False
        self.model_labels=json.loads((Path(__file__).parent/"bridge/monitor_labels.json").read_text(encoding="utf-8")).get("models",{})
        self.journal=None
        catalogue=json.loads((Path(__file__).parent/'catalogue.json').read_text(encoding='utf-8'))
        self.item_effects={str(r['id']):dict(name=n,**r) for n,r in catalogue['items'].items()}
        self.state_dir=Path(__file__).parent/'notes/client_journal'

    async def report_checks(self, locations):
        if self.journal is None:
            raise RuntimeError('No connected journal binding')
        locations=sorted(set(locations)-set(self.checked_locations))
        if not locations:return
        self.journal.queue(locations)
        for location in locations:
            row=self.catalogue.get(str(location),{})
            logging.info('CHECK queued: %s | ID %s | %s',row.get('name',location),location,row.get('status','manual'))
        await self.send_msgs([dict(cmd='LocationChecks',locations=locations)])

    async def server_auth(self,password_requested=False):
        if password_requested and not self.password:await super().server_auth(password_requested)
        await self.get_username()
        await self.send_connect()

    def on_package(self,cmd,args):
        if cmd=='RoomInfo':
            self.seed_name=args['seed_name']
        if cmd=='Connected':
            self.slot_options=args.get('slot_data',{}).get('options',{})
            self.item_effects.update(args.get('slot_data',{}).get('item_effects',{}))
            self.catalogue=args.get('slot_data',{}).get('locations',{})
            self.goal_count=args.get('slot_data',{}).get('goal_tokens',20)
            self.skip_slot=bool(args.get('slot_data',{}).get('options',{}).get('cutscene_skip',False))
            logging.warning('Native grants, autosave and reward suppression: %s. Story/area entrance gates remain unavailable.',
                            'EXPERIMENTAL, enabled' if self.enable_native_models else 'disabled')


async def watcher(ctx):
    native_delivery=NativeDeliveryEngine(bridge_path(ROOT),ctx.native_save_file)
    exit_gate=StationExitGate();opened_lift=None
    session=None;previous=None;binding=None;journal_binding=None;seen_models=set();model_ids=None;skip_pid=None
    try:
        while not ctx.exit_event.is_set():
            try:
                # The skip manager can exist in the main menu, before a player
                # or readable save exists. Do not make its opt-in activation
                # depend on a full inventory snapshot.
                if ctx.enable_skip and ctx.skip_slot:
                    try:
                        skip=await asyncio.to_thread(enable_cutscene_skip)
                        if skip['before']==0 or skip_pid!=skip['pid']:
                            logging.info('Cutscene skip enabled (N0CUT5); works before loading a save')
                        skip_pid=skip['pid']
                    except (OSError,RuntimeError,ValueError) as error:
                        logging.debug('Cutscene skip waiting for manager: %s',error)
                if ctx.slot is not None and ctx.catalogue and ctx.seed_name:
                    current_binding=(ctx.seed_name,ctx.team,ctx.slot)
                    if current_binding!=binding:
                        previous=None;binding=current_binding;seen_models.clear()
                        if session:session.close()
                        session=None;model_ids=None
                    if ctx.journal is None or current_binding!=journal_binding:
                        if ctx.journal:ctx.journal.close()
                        ctx.journal=Journal(ctx.state_dir,dict(seed=ctx.seed_name,team=ctx.team,slot=ctx.slot,
                            catalogue=ctx.catalogue,detection_policy=2))
                        journal_binding=current_binding
                    for i,item in enumerate(ctx.items_received):
                        ctx.journal.receipt(i,item)
                        effect=ctx.item_effects.get(str(item.item))
                        if effect:register_delivery(ctx.journal,i,effect)
                    ctx.journal.acknowledge(ctx.checked_locations)
                    pending=ctx.journal.pending()
                    if pending:await ctx.send_msgs([dict(cmd='LocationChecks',locations=pending)])
                    if not ctx.finished_game and sum(x.item==2_999_999_999 for x in ctx.items_received)>=ctx.goal_count:
                        await ctx.send_msgs([dict(cmd='StatusUpdate',status=ClientStatus.CLIENT_GOAL)])
                        ctx.finished_game=True
                    if session is None:session=await asyncio.to_thread(Session)
                    snapshot=await asyncio.to_thread(session.snapshot)
                    if snapshot.get('actor',{}).get('status')!='read':
                        # Menu inventory may still contain prior profile data.
                        # Never interpret it as checks for the connected seed.
                        previous=None;seen_models.clear()
                        await asyncio.sleep(1)
                        continue
                    for row in snapshot.get('native_pickups',{}).get('objects',[]):
                        if row.get('native_type')!=7 or not row.get('native_collected'):continue
                        source=row.get('source_key')
                        identity=('red_brick',source or (row.get('tile_name'),row['name']))
                        if identity in seen_models:continue
                        seen_models.add(identity)
                        location_key=redbrick_location_key(source) if source else None
                        active=any(v.get('key')==location_key for v in ctx.catalogue.values())
                        logging.info('RED BRICK collected: %s | scene=%s | flags=%s | %s',
                            row['name'],row.get('tile_name'),row.get('pickup_flags'),
                            'check location active' if active else 'no corresponding location in this seed')
                    for reward_key,reward in completed_activity_rewards(snapshot).items():
                        identity=('activity_reward',reward_key)
                        if identity in seen_models:continue
                        seen_models.add(identity)
                        active=any((v.get('runtime') or {}).get('reward_key')==reward_key for v in ctx.catalogue.values())
                        logging.info('ACTIVITY completed: %s | source=%s | %s',reward['name'],reward['source_key'],
                                     'check location active' if active else 'location absent from current seed; included in future seeds')
                    for completed_key in sorted(completed_level_keys(snapshot.get('level_progress',{}))):
                        identity=('persistent_level',completed_key)
                        if identity in seen_models:continue
                        seen_models.add(identity)
                        logging.info('SAVED MISSION CHECK: %s',completed_key)
                    for row in snapshot.get('superbuilds',{}).get('records',[]):
                        if not row.get('complete'):continue
                        identity=('superbuild',row['name'],row.get('objective_name'))
                        if identity in seen_models:continue
                        seen_models.add(identity)
                        logging.info('SUPER BUILD completed: %s | objective=%s | state=%s flags=%s',
                            row['name'],row.get('objective_name') or 'unmapped',row['state'],row['completion_flags'])
                    for row in snapshot.get('native_pickups',{}).get('objects',[]):
                        source=row.get('source_key','') or ''
                        if not (row.get('native_collected') and row.get('native_type') in (12,29)
                                and '/levels/standalones/' in source):continue
                        identity=('mission_superbrick',source)
                        if identity in seen_models:continue
                        seen_models.add(identity)
                        active=[v for v in ctx.catalogue.values() if v.get('key')=='source_pickup:'+source]
                        logging.info('MISSION SUPER BRICK collected: %s / %s | flags=%s | position=%s | %s',
                            row.get('tile_name'),row['name'],row['pickup_flags'],row['position'],
                            'check location active' if active else 'source absent from this seed; updated APWorld required')
                    hero=snapshot.get('mission_hero',{})
                    if hero.get('status')=='read' and hero.get('complete'):
                        identity=('city_hero',hero['mission'])
                        if identity not in seen_models:
                            seen_models.add(identity)
                            logging.info('LEGO CITY HERO: %s | studs=%s target=%s | native completion=%s',
                                hero['mission'],hero['studs'],hero['threshold'],hero['latch'])
                    shield=snapshot.get('mission_shield',{})
                    if shield.get('status')=='read':
                        for part in shield.get('parts',[]):
                            identity=('shield',shield['mission'],part)
                            if identity not in seen_models:
                                seen_models.add(identity)
                                logging.info('POLICE SHIELD: %s | %s | mask=%s',shield['mission'],part,shield['mask'])
                    for row in snapshot.get('mission_tokens',{}).get('records',[]):
                        identity=('mission',row['internal_name'].upper())
                        if identity in seen_models:continue
                        seen_models.add(identity)
                        bound=any((v.get('runtime') or {}).get('kind')=='model_found' and
                            v['runtime']['native_name'].upper()==identity[1] for v in ctx.catalogue.values())
                        logging.info('STORY TOKEN collected: %s (%s) | model %s | %s',
                            ctx.model_labels.get(str(row['model_id']),{}).get('display_name',row['internal_name']),
                            row['internal_name'],row['model_id'],
                            'experimental token check' if bound else 'no token location in this seed; regenerate with updated APWorld')
                    for row in snapshot.get('characters',[]):
                        if row.get('group') not in ('character','vehicle') or not (row.get('found_bit') or row.get('pending_grant')):continue
                        identity=row['internal_name'].upper()
                        if identity in seen_models:continue
                        seen_models.add(identity)
                        bound=[v for v in ctx.catalogue.values() if
                            (v.get('runtime') or {}).get('kind')=='model_found' and
                            v['runtime']['native_name'].upper()==identity]
                        logging.info('FOUND %s: %s | model %s | found=%s pending=%s owned=%s | %s',
                            row['group'],row['internal_name'],row['model_id'],row.get('found_bit'),row.get('pending_grant'),row.get('owned_byte'),
                            'experimental token binding' if bound else 'no token location in this seed')
                    checks,previous=changed_checks(ctx.catalogue,previous,snapshot,
                        set(ctx.checked_locations) | set(ctx.journal.pending()))
                    if checks:await ctx.report_checks(checks)
                    if ctx.enable_native_models:
                        received=[ctx.item_effects[str(item.item)] for item in ctx.items_received if str(item.item) in ctx.item_effects]
                        await native_delivery.poll(session,snapshot,ctx.journal,ctx.item_effects.values(),received,ctx.slot_options)
                        # Only the verified first-visit/rescue phase can use the AP
                        # escape. Native code prepares its next first-visit entry
                        # before invoking the existing exterior door transition.
                        eligible=can_resume_first_lobby(snapshot.get('story',{}))
                        lift_probe=(await asyncio.to_thread(read_lobby_lift,session.read,session.base)) if eligible else None
                        if lift_probe is None:opened_lift=None
                        elif (snapshot['actor'].get('context',{}).get('index')==46 and
                              lift_probe['distance_squared']<=2.25 and
                              opened_lift!=(session.pid,lift_probe['owner'])):
                            opened_lift=(session.pid,lift_probe['owner'])
                            if await asyncio.to_thread(open_lobby_lift,session.pid,native_delivery.dll):
                                logging.info('Lobby lift arrival: opening existing lift doors without advancing tutorial')
                            else:opened_lift=None

                        probe=(await asyncio.to_thread(read_station_exit,session.read,session.base)) if eligible else None
                        if exit_gate.update(session.pid,probe,snapshot['actor'].get('context',{}).get('index')):
                            exit_gate.mark_triggered() # Do not replay a transition after a lost response.
                            if await asyncio.to_thread(trigger_station_exit,session.pid,native_delivery.dll):
                                logging.info('Police station transition: %s; first-visit re-entry prepared',probe['door_name'])
                            else:exit_gate.triggered=False

                await asyncio.sleep(1)
            except (OSError,RuntimeError,ValueError) as error:
                logging.warning('Reader waiting: %s',error)
                if session:session.close()
                session=None;previous=None;model_ids=None
                await asyncio.sleep(2)
    finally:
        if session:session.close()
        if ctx.journal:ctx.journal.close();ctx.journal=None


async def _run_client(args):
    ctx=Context(args)
    ctx.server_task=asyncio.create_task(server_loop(ctx))
    ctx.run_cli()
    task=asyncio.create_task(watcher(ctx))
    await ctx.exit_event.wait()
    await task
    await ctx.shutdown()


async def main(args):
    if args.enable_native_models:
        from native_client_lock import NativeClientLock
        try:
            with NativeClientLock():
                await _run_client(args)
        except RuntimeError as error:
            logging.error('%s',error)
    else:
        await _run_client(args)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--connect');p.add_argument('--name');p.add_argument('--password')
    p.add_argument('--native-save-file',type=Path,
        help='Exact gameN.legocityundercoversavegamedata of loaded slot; otherwise require a unique matching save')
    p.add_argument('--enable-cutscene-skip',action='store_true',help='Enable verified N0CUT5 permission')
    p.add_argument('--enable-native-items','--enable-native-models',dest='enable_native_models',action='store_true',
        help='Experimental native grants, currency, autosave and post-check vanilla reward suppression')
    # CommonClient/world imports may have installed a WARNING-level root handler.
    # Explicitly enable the native receipt/save progress messages afterwards.
    logging.basicConfig(level=logging.INFO)
    logging.getLogger().setLevel(logging.INFO)
    for handler in logging.getLogger().handlers:
        if handler.level>logging.INFO:handler.setLevel(logging.INFO)
    asyncio.run(main(p.parse_args()))
