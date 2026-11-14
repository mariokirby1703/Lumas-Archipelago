"""Regression for ws -> wss fallback scheduling two reconnects on disconnect."""
import asyncio
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock,Mock,patch
import CommonClient

class ClosedSocket:
    def __aiter__(self):return self
    async def __anext__(self):raise StopAsyncIteration

class ReconnectTests(unittest.IsolatedAsyncioTestCase):
    async def check_connection(self,results):
        ctx=SimpleNamespace(server=None,server_address='archipelago.gg:58404',
            username='Luma',password=None,ui=None,max_size=1024,
            cancel_autoreconnect=Mock(),_messagebox_connection_loss=None,
            starting_reconnect_delay=5,current_reconnect_delay=5,
            disconnected_intentionally=False,autoreconnect_task=None,
            connection_closed=AsyncMock(),handle_connection_loss=Mock())
        with patch.object(CommonClient.websockets,'connect',new=AsyncMock(side_effect=results)) as connect, \
             patch.object(CommonClient,'server_autoreconnect',new=AsyncMock()) as reconnect:
            await CommonClient.server_loop(ctx)
            ctx.connection_closed.assert_awaited_once()
            self.assertIsNotNone(ctx.autoreconnect_task)
            await ctx.autoreconnect_task
            reconnect.assert_awaited_once_with(ctx)
            self.assertEqual(ctx.current_reconnect_delay,10)
            return ctx,connect
    async def test_tls_fallback_disconnect_schedules_once(self):
        ctx,connect=await self.check_connection([CommonClient.websockets.InvalidMessage('TLS required'),ClosedSocket()])
        self.assertEqual([c.args[0] for c in connect.await_args_list],
                         ['ws://archipelago.gg:58404','wss://archipelago.gg:58404'])
        self.assertEqual(ctx.server_address,'wss://archipelago.gg:58404')
    async def test_tls_fallback_refusal_schedules_once(self):
        ctx,_=await self.check_connection([CommonClient.websockets.InvalidMessage('TLS required'),ConnectionRefusedError()])
        ctx.handle_connection_loss.assert_called_once()
    async def test_plain_refusal_still_reconnects(self):
        ctx,_=await self.check_connection([ConnectionRefusedError()])
        ctx.handle_connection_loss.assert_called_once()
