"""Experimental AP client: native objective changes + manual checks; journals receipts.

Native reward suppression, grants, tool/area/story locks are NOT implemented.
"""
import argparse
import asyncio
import json
import logging
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(Path(__file__).parent/'bridge'))
from CommonClient import CommonContext, ClientCommandProcessor, server_loop
from live_monitor import Session
from research_profile import symbol_hash
from cutscene_skip import enable_cutscene_skip
from NetUtils import ClientStatus
from client_checks import changed_checks


class Commands(ClientCommandProcessor):
    def _cmd_check(self, location_id: str):
        """Manually report an active location ID after performing its action."""
        try:location=int(location_id)
        except ValueError:return False
        if str(location) not in self.ctx.catalogue:
            self.output('ID not active in this seed');return False
        asyncio.create_task(self.ctx.send_msgs([dict(cmd='LocationChecks',locations=[location])]))
        return True


class Context(CommonContext):
    game='LEGO City Undercover'
    items_handling=0b111
    command_processor=Commands

    def __init__(self,args):
        super().__init__(args.connect,args.password)
        self.auth=args.name
        self.catalogue={}
        self.enable_skip=args.enable_cutscene_skip
        self.skip_slot=False
        self.state_dir=Path(__file__).parent/'notes/client_journal'

    async def server_auth(self,password_requested=False):
        if password_requested and not self.password:await super().server_auth(password_requested)
        await self.get_username()
        await self.send_connect()

    def on_package(self,cmd,args):
        if cmd=='Connected':
            self.catalogue=args.get('slot_data',{}).get('locations',{})
            self.goal_count=args.get('slot_data',{}).get('goal_tokens',20)
            self.skip_slot=bool(args.get('slot_data',{}).get('options',{}).get('cutscene_skip',False))
            logging.warning('Native grants/locks/open-world setup unavailable. Received items are journaled, not applied.')


async def watcher(ctx):
    session=None;previous=None;binding=None
    try:
        while not ctx.exit_event.is_set():
            try:
                if ctx.slot is not None and ctx.catalogue:
                    current_binding=(ctx.seed_name,ctx.team,ctx.slot)
                    if current_binding!=binding:previous=None;binding=current_binding
                    ctx.state_dir.mkdir(parents=True,exist_ok=True)
                    key=symbol_hash(repr(binding));path=ctx.state_dir/f'{key:08x}.json'
                    journal=dict(binding=binding,receipts=[dict(index=i,item=x.item,location=x.location,player=x.player)
                                                          for i,x in enumerate(ctx.items_received)],
                                 native_items_applied=False,checked_locations=sorted(ctx.checked_locations))
                    temporary=path.with_suffix('.tmp');temporary.write_text(json.dumps(journal,indent=2),encoding='utf-8');temporary.replace(path)
                    if not ctx.finished_game and sum(x.item==2_999_999_999 for x in ctx.items_received)>=ctx.goal_count:
                        await ctx.send_msgs([dict(cmd='StatusUpdate',status=ClientStatus.CLIENT_GOAL)])
                        ctx.finished_game=True
                    if session is None:session=await asyncio.to_thread(Session)
                    snapshot=await asyncio.to_thread(session.snapshot)
                    if ctx.enable_skip and ctx.skip_slot:await asyncio.to_thread(enable_cutscene_skip)
                    checks,previous=changed_checks(ctx.catalogue,previous,snapshot)
                    if checks:await ctx.send_msgs([dict(cmd='LocationChecks',locations=checks)])
                await asyncio.sleep(1)
            except (OSError,RuntimeError,ValueError) as error:
                logging.warning('Reader waiting: %s',error)
                if session:session.close()
                session=None;previous=None
                await asyncio.sleep(2)
    finally:
        if session:session.close()


async def main(args):
    ctx=Context(args)
    ctx.server_task=asyncio.create_task(server_loop(ctx))
    ctx.run_cli()
    task=asyncio.create_task(watcher(ctx))
    await ctx.exit_event.wait()
    await task
    await ctx.shutdown()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--connect');p.add_argument('--name');p.add_argument('--password')
    p.add_argument('--enable-cutscene-skip',action='store_true',help='Only native write: enable verified N0CUT5 permission')
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main(p.parse_args()))
