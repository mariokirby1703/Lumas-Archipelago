import asyncio
from pathlib import Path
import tempfile

from NetUtils import NetworkItem
from ..Items import ITEM_TABLE
from ..client.client import SonicContext
from ..components import run_client
from worlds.LauncherComponents import components
from . import generate


def test_connected_receipts_empty_history_barrier_and_reconnect():
    async def scenario(directory):
        data = generate().worlds[1].fill_slot_data()
        ctx = SonicContext(journal_directory=directory)
        ctx.team, ctx.slot, ctx.seed_name = 0, 1, data['seed_name']
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
        ctx.on_package('Connected', {'slot_data': data})
        assert ctx.runtime is None and 'differs' in ctx.dolphin_status
        await ctx.shutdown()
    with tempfile.TemporaryDirectory() as directory:
        asyncio.run(scenario(directory))
    entries = [c for c in components if c.func is run_client]
    assert len(entries) == 1
    assert entries[0].supports_uri
