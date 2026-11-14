"""Client menu startup must enable skip without reporting stale inventory."""
import asyncio
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock,Mock,patch
spec=importlib.util.spec_from_file_location('lcu_menu_client',Path(__file__).resolve().parents[1]/'Client.py')
client=importlib.util.module_from_spec(spec);spec.loader.exec_module(client)

class MenuStartupTests(unittest.IsolatedAsyncioTestCase):
    async def test_skip_runs_before_save_or_player_is_available(self):
        ctx=SimpleNamespace(native_save_file=None,enable_skip=True,skip_slot=True,
                            slot=None,journal=None,exit_event=asyncio.Event())
        async def stop(_):ctx.exit_event.set()
        with patch.object(client,'enable_cutscene_skip',return_value={'before':0,'pid':123}) as skip, \
             patch.object(client,'Session') as session,patch.object(client.asyncio,'sleep',side_effect=stop):
            await client.watcher(ctx)
            skip.assert_called_once();session.assert_not_called()
    async def test_menu_profile_cannot_report_checks_or_deliver_items(self):
        journal=Mock();journal.pending.return_value=[]
        ctx=SimpleNamespace(native_save_file=None,enable_skip=True,skip_slot=True,
            slot=1,team=0,seed_name='fresh-slot2-seed',catalogue={'1':{}},journal=None,
            state_dir=Path('unused'),items_received=[],checked_locations=set(),
            finished_game=True,exit_event=asyncio.Event(),report_checks=AsyncMock(),
            enable_native_models=True)
        session=Mock();session.snapshot.return_value={'actor':{'status':'not_initialized'},
                                                      'characters':[{'found_bit':True}]}
        async def stop(_):ctx.exit_event.set()
        with patch.object(client,'enable_cutscene_skip',return_value={'before':1,'pid':123}) as skip, \
             patch.object(client,'Session',return_value=session), \
             patch.object(client,'Journal',return_value=journal), \
             patch.object(client,'changed_checks') as checks, \
             patch.object(client,'NativeDeliveryEngine') as delivery, \
             patch.object(client.asyncio,'sleep',side_effect=stop):
            await client.watcher(ctx)
            skip.assert_called_once();checks.assert_not_called()
            delivery.return_value.poll.assert_not_called();ctx.report_checks.assert_not_called()
            session.close.assert_called_once()
    async def test_seed_option_still_controls_skip(self):
        ctx=SimpleNamespace(native_save_file=None,enable_skip=True,skip_slot=False,
                            slot=None,journal=None,exit_event=asyncio.Event())
        async def stop(_):ctx.exit_event.set()
        with patch.object(client,'enable_cutscene_skip') as skip, \
             patch.object(client.asyncio,'sleep',side_effect=stop):
            await client.watcher(ctx)
            skip.assert_not_called()
    async def test_vehicle_check_is_queued_and_sent_before_native_delivery(self):
        journal=Mock();journal.pending.return_value=[]
        ctx=SimpleNamespace(native_save_file=None,enable_skip=False,skip_slot=False,
            slot=1,team=0,seed_name='vehicle-seed',catalogue={'123':{'name':'Vehicle pickup'}},
            journal=None,state_dir=Path('unused'),items_received=[],checked_locations=set(),
            finished_game=True,exit_event=asyncio.Event(),send_msgs=AsyncMock(),
            enable_native_models=False)
        ctx.report_checks=lambda locations:client.Context.report_checks(ctx,locations)
        session=Mock();session.snapshot.return_value={'actor':{'status':'read','context':{'index':157}},
                                                      'characters':[]}
        async def stop(_):ctx.exit_event.set()
        with patch.object(client,'Session',return_value=session), \
             patch.object(client,'Journal',return_value=journal), \
             patch.object(client,'changed_checks',return_value=([123],{})), \
             patch.object(client.asyncio,'sleep',side_effect=stop):
            await client.watcher(ctx)
        journal.queue.assert_called_once_with([123])
        ctx.send_msgs.assert_awaited_once_with([{'cmd':'LocationChecks','locations':[123]}])
