"""Exercise the real AP server/client protocol with deterministic mocked game RAM."""
import asyncio
import functools
import pathlib
import sys
import tempfile
from collections import Counter
from unittest.mock import patch

import MultiServer
import Utils
from CommonClient import server_loop
from NetUtils import ClientStatus
from worlds.carnival_games_minigolf.client.client import MiniGolfContext
from worlds.carnival_games_minigolf.client.constants import RESULT_VTABLE
from worlds.carnival_games_minigolf.data import MINIGAMES
from worlds.carnival_games_minigolf.Items import GOAL_WORLD_ACCESS, ITEM_TABLE
from worlds.carnival_games_minigolf.Locations import BARKER_REQUIREMENT_LOCATION, LOCATION_TABLE
from worlds.carnival_games_minigolf.test.test_runtime import TestRuntime


async def main():
    archive = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else next(pathlib.Path('build/carnival-games-minigolf/generation').glob('*.zip'))
    server_ctx = MultiServer.Context('127.0.0.1', 0, '', '', 1, 10, False)
    server_ctx.load(str(archive))
    server_ctx.init_save(False)
    fixture = TestRuntime()
    fixture.setUp()
    fixture.memory.write(fixture.sub, bytes([1])*88)
    fixture.memory.write(fixture.sub+0x6A, bytes([1])*27)
    fixture.memory.write(fixture.sub+0x86, bytes([1])*27)
    with tempfile.TemporaryDirectory() as directory, patch.object(Utils, 'persistent_store'), \
            patch.object(Utils, 'user_path', side_effect=lambda *p: str(pathlib.Path(directory).joinpath(*p))):
        async with MultiServer.websockets.serve(functools.partial(MultiServer.server, ctx=server_ctx), '127.0.0.1', 0) as host:
            port = host.sockets[0].getsockname()[1]
            ctx = MiniGolfContext(f'127.0.0.1:{port}')
            ctx.auth = server_ctx.player_names[0, 1]
            ctx.server_task = asyncio.create_task(server_loop(ctx))
            try:
                for _ in range(100):
                    if ctx.runtime and ctx.history_ready:
                        break
                    await asyncio.sleep(.05)
                assert ctx.runtime and ctx.history_ready, 'Client handshake did not complete'
                array, popup = 0x80960000, 0x80970000
                fixture.memory.put(fixture.manager+0x100, array, 4)
                fixture.memory.put(array, popup, 4)
                fixture.memory.put(popup+0x1C, RESULT_VTABLE, 4)
                fixture.memory.write(popup+0xC0, bytes([1, 1]))
                fixture.memory.put(fixture.controller+0x44, fixture.root, 4)
                for _ in range(30):
                    fixture.memory.put(fixture.controller+0x1C, 0x80400000, 4)
                    fixture.memory.put(fixture.manager+0x104, 0, 4)
                    fixture.memory.put(fixture.root+0x2DC, 2, 4)
                    for hole in range(27):
                        fixture.memory.put(fixture.session+0x2F0, hole, 4)
                        fixture.memory.put(fixture.hole_state+0x127, 0)
                        ctx.runtime.poll(fixture.memory, [i.item for i in ctx.items_received])
                        fixture.memory.put(fixture.hole_state+0x127, 1)
                        checks = ctx.runtime.poll(fixture.memory, [i.item for i in ctx.items_received])
                        ctx.locations_checked |= checks
                    for w, (_, vtable) in enumerate(MINIGAMES):
                        fixture.memory.put(fixture.controller+0x1C, vtable, 4)
                        fixture.memory.put(fixture.manager+0x104, 0, 4)
                        ctx.runtime.poll(fixture.memory, [i.item for i in ctx.items_received])
                        fixture.memory.put(fixture.manager+0x104, 1, 4)
                        checks = ctx.runtime.poll(fixture.memory, [i.item for i in ctx.items_received])
                        ctx.locations_checked |= checks
                    await ctx.send_msgs([{'cmd': 'LocationChecks', 'locations': sorted(ctx.locations_checked)}])
                    await asyncio.sleep(.05)
                    if len(ctx.checked_locations) == len(ctx.runtime.locations):
                        break
                expected = len(ctx.runtime.locations)
                if len(ctx.checked_locations) != expected:
                    checked_kinds = Counter(data.kind for data in ctx.runtime.locations.values()
                                            if data.code in ctx.checked_locations)
                    missing_kinds = Counter(data.kind for data in ctx.runtime.locations.values()
                                            if data.code not in ctx.checked_locations)
                    unlocked, coins = ctx.runtime.unlocked([item.item for item in ctx.items_received])
                    raise AssertionError((len(ctx.checked_locations), expected, checked_kinds, missing_kinds,
                                          unlocked, coins, ctx.runtime_error))
                assert len(ctx.items_received) == expected, (len(ctx.items_received), expected)
                assert ctx.runtime.victory([i.item for i in ctx.items_received], ctx.checked_locations)
                if ctx.runtime.slot['goal'] == 1 and ctx.runtime.slot['goal_world_access'] == 1:
                    assert LOCATION_TABLE[BARKER_REQUIREMENT_LOCATION].code in ctx.checked_locations
                    assert ITEM_TABLE[GOAL_WORLD_ACCESS] in [item.item for item in ctx.items_received]
                    assert not any(data.kind == 'barker_shop' for data in ctx.runtime.locations.values())
                await ctx.send_msgs([{'cmd': 'StatusUpdate', 'status': ClientStatus.CLIENT_GOAL}])
                await asyncio.sleep(.1)
                assert server_ctx.client_game_state[0, 1] == ClientStatus.CLIENT_GOAL
                ctx.runtime.poll(fixture.memory, [i.item for i in ctx.items_received])
                balance = fixture.memory.read(fixture.sub+0x58, 18)
                # Recreate Connected/ReceivedItems, as on a server reconnect, from the saved journal.
                ctx.on_package('Connected', {'slot_data': ctx.runtime.slot})
                ctx.on_package('ReceivedItems', {'index': 0, 'items': ctx.items_received})
                ctx.runtime.poll(fixture.memory, [i.item for i in ctx.items_received])
                assert fixture.memory.read(fixture.sub+0x58, 18) == balance
                print(f'PASS: real AP handshake, {expected} checks/items, server goal, journal reconnect')
            finally:
                ctx.exit_event.set()
                ctx.release_journal()
                await ctx.shutdown()
                fixture.doCleanups()


if __name__ == '__main__':
    asyncio.run(main())
