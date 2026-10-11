import asyncio
import pytest
from pathlib import Path
import tempfile

from NetUtils import NetworkItem
from ..Items import ITEM_TABLE
from ..client.client import SonicContext
from ..components import run_client
from worlds.LauncherComponents import components
from . import generate


def test_authenticated_singleton_permission_survives_truncated_consumable_history(tmp_path):
    async def scenario():
        data=generate().worlds[1].fill_slot_data()
        ctx=SonicContext(journal_directory=tmp_path);ctx.team,ctx.slot=0,1
        async def send(messages):pass
        ctx.send_msgs=send
        ctx.on_package('RoomInfo',{'seed_name':data['seed_name']})
        ctx.on_package('Connected',{'slot_data':data});await asyncio.sleep(0)
        journal=ctx.runtime.journal
        original=[ITEM_TABLE['Rings']]*40
        journal.record_history(original)
        green=ITEM_TABLE['Green Hover Wisp']
        ctx.items_received=[NetworkItem(green,0,1)]
        ctx.on_package('ReceivedItems',{'index':0,'items':[[green,0,1]]})
        assert ctx.history_desynced and not ctx.history_ready
        assert journal.data['receipts']==original
        assert journal.data['permission_receipts']==[green]
        journal.record_permissions([green,ITEM_TABLE['Rings'],ITEM_TABLE['1-Up'],ITEM_TABLE['Progressive Game Land Speed']])
        assert journal.data['permission_receipts']==[green]
        ctx.on_package('RoomInfo',{'seed_name':'another-seed'})
        blue=ITEM_TABLE['Blue Cube Wisp']
        ctx.on_package('ReceivedItems',{'index':1,'items':[[blue,0,1]]})
        assert journal.data['permission_receipts']==[green]
        ctx.release_runtime();await ctx.shutdown()
    asyncio.run(scenario())


def test_connected_receipts_empty_history_barrier_and_reconnect():
    async def scenario(directory):
        data = generate().worlds[1].fill_slot_data()
        ctx = SonicContext(journal_directory=directory)
        ctx.team, ctx.slot = 0, 1
        ctx.on_package('RoomInfo', {'seed_name': data['seed_name']})
        sent = []
        async def send(messages): sent.extend(messages)
        ctx.send_msgs = send
        ctx.on_package('Connected', {'slot_data': data})
        await asyncio.sleep(0)
        assert ctx.runtime is not None and not ctx.history_ready
        assert sent == [{'cmd': 'Get', 'keys': [ctx.barrier]}]
        ctx.on_package('Retrieved', {'keys': {ctx.barrier: None}})
        assert ctx.history_ready
        ctx.items_received = [NetworkItem(ITEM_TABLE['Rings (+10)'], 123, 2)]
        ctx.on_package('ReceivedItems', {'index': 0, 'items': [[ITEM_TABLE['Rings (+10)'], 123, 2]]})
        assert ctx.runtime.journal.data['receipts'] == [ITEM_TABLE['Rings (+10)']]
        ctx.on_package('ReceivedItems', {'index': 8, 'items': []})
        assert not ctx.history_ready and ctx.history_desynced
        ctx.on_package('Retrieved', {'keys': {ctx.barrier: None}})
        assert not ctx.history_ready
        ctx.on_package('ReceivedItems', {'index': 0, 'items': [[ITEM_TABLE['Rings (+10)'], 123, 2]]})
        assert ctx.history_ready
        ctx.release_runtime()
        ctx.on_package('Connected', {'slot_data': data})
        await asyncio.sleep(0)
        assert ctx.runtime.pending_effects() == [0]
        assert not ctx.runtime.guard.armed
        ctx.release_runtime()
        await ctx.shutdown()
    with tempfile.TemporaryDirectory() as directory:
        asyncio.run(scenario(directory))


def test_seed_file_mismatch_and_launcher_registration():
    async def scenario(directory):
        world = generate().worlds[1]
        world.generate_output(directory)
        path = next(Path(directory).glob('*.apsonic'))
        ctx = SonicContext(patch_file=path, journal_directory=directory)
        assert ctx.auth == 'SonicPlayer'
        data = world.fill_slot_data()
        data['seed_name'] = 'another-seed'
        ctx.team, ctx.slot = 0, 1
        ctx.on_package('RoomInfo', {'seed_name': data['seed_name']})
        ctx.on_package('Connected', {'slot_data': data})
        assert ctx.runtime is None and 'differs' in ctx.dolphin_status
        await ctx.shutdown()
    with tempfile.TemporaryDirectory() as directory:
        asyncio.run(scenario(directory))
    entries = [c for c in components if c.func is run_client]
    assert len(entries) == 1
    assert entries[0].supports_uri


def test_diagnostics_only_report_server_acknowledged_checks(tmp_path):
    async def scenario():
        from ..client.diagnostics import diagnostic
        ctx = SonicContext(journal_directory=tmp_path)
        ctx.locations_checked.add(847001000)  # local send is not an ACK
        assert diagnostic(ctx)['latest_acknowledged_location'] is None
        ctx.checked_locations.add(847001000)  # applied by CommonContext
        ctx.on_package('RoomUpdate', {'checked_locations': [847001000]})
        first = diagnostic(ctx)
        assert first['latest_acknowledged_location']['locations'] == [847001000]
        assert first['implementation']['loaded_python_paths']['worlds.sonic_colours.client.hooks']
        assert len(first['implementation']['loaded_code_id']) == 64
        assert 'wisp_permissions' in first['operation_blockers']
        ctx.on_package('RoomUpdate', {'checked_locations': [847001000]})
        assert diagnostic(ctx)['latest_acknowledged_location'] == first['latest_acknowledged_location']
        await ctx.shutdown()
    asyncio.run(scenario())

def test_roominfo_mismatch_rejects_slot_and_idle_transport_has_no_identity_error(tmp_path):
    from ..client.client import transmit_checks
    async def scenario():
        data=generate().worlds[1].fill_slot_data()
        ctx=SonicContext(journal_directory=tmp_path)
        assert ctx.seed_name is None
        ctx.team,ctx.slot=0,1
        ctx.on_package('RoomInfo',{'seed_name':'other-server-seed'})
        ctx.on_package('Connected',{'slot_data':data})
        assert ctx.runtime is None and ctx.authenticated_identity is None
        assert 'mismatch' in ctx.dolphin_status
        ctx.on_package('RoomInfo',{'seed_name':data['seed_name']})
        async def send(messages): pass
        ctx.send_msgs=send
        ctx.on_package('Connected',{'slot_data':data})
        ctx.server=object()
        ctx.authenticated_identity=None
        await transmit_checks(ctx)
        assert ctx.operation_status['ap_transport']=='idle: no pending checks or goal'
        ctx.server=None
        ctx.release_runtime();await ctx.shutdown()
    asyncio.run(scenario())

def test_transport_retries_failed_journal_fsync_before_sending(tmp_path, monkeypatch):
    from ..client.client import transmit_checks
    from ..client import journal as journal_module
    async def scenario():
        data=generate().worlds[1].fill_slot_data()
        ctx=SonicContext(journal_directory=tmp_path)
        ctx.team,ctx.slot=0,1
        ctx.on_package('RoomInfo',{'seed_name':data['seed_name']})
        sent=[]
        async def send(messages):sent.extend(messages)
        ctx.send_msgs=send
        ctx.on_package('Connected',{'slot_data':data})
        await asyncio.sleep(0)
        sent.clear();ctx.server=object()
        journal=ctx.runtime.journal
        original=journal_module.os.fsync
        def failure(fd):raise OSError('test disk persistence failure')
        monkeypatch.setattr(journal_module.os,'fsync',failure)
        code=next(iter(data['locations'].values()))
        with pytest.raises(OSError):
            journal.record_pickups([{'kind':'red_ring','mission':'stg110','ring':1}],{'stg110':1},{code})
        assert journal.persistence_pending
        with pytest.raises(OSError):await transmit_checks(ctx)
        assert not sent
        monkeypatch.setattr(journal_module.os,'fsync',original)
        await transmit_checks(ctx)
        assert not journal.persistence_pending
        assert sent==[{'cmd':'LocationChecks','locations':[code]}]
        ctx.server=None;ctx.release_runtime();await ctx.shutdown()
    asyncio.run(scenario())
