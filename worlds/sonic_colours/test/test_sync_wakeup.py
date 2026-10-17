import asyncio
from types import SimpleNamespace
from ..client.client import wait_for_sync


def test_server_packet_wakes_sync_before_idle_deadline():
    async def run():
        ctx=SimpleNamespace(sync_wakeup=asyncio.Event())
        task=asyncio.create_task(wait_for_sync(ctx,60))
        await asyncio.sleep(0)
        ctx.sync_wakeup.set()
        await asyncio.wait_for(task,1)
        assert not ctx.sync_wakeup.is_set()
        # A packet arriving while native work runs must also wake the next wait.
        ctx.sync_wakeup.set()
        await asyncio.wait_for(wait_for_sync(ctx,60),1)
        assert not ctx.sync_wakeup.is_set()
    asyncio.run(run())


def test_idle_timeout_does_not_leave_a_pending_task():
    async def run():
        ctx=SimpleNamespace(sync_wakeup=asyncio.Event())
        await wait_for_sync(ctx,.001)
        assert not ctx.sync_wakeup.is_set()
    asyncio.run(run())
