import asyncio
from types import SimpleNamespace
import pytest
from ..client.client import poll_runtime


def test_check_checkpoint_sends_and_receives_ack_before_projection():
    async def test():
        phases=[]
        identity={'team':0,'slot':1,'seed':'seed'}
        runtime=SimpleNamespace(journal=SimpleNamespace(identity=identity,persistence_pending=False))
        context=SimpleNamespace(runtime=runtime,items_received=[],history_ready=True,
            authenticated_identity=(0,1,'seed'),team=0,slot=1,server_seed='seed',server=object(),
            checked_locations=set(),last_pending=set(),last_send=0.,finished_game=False,operation_status={})
        async def send(messages):
            assert messages==[{'cmd':'LocationChecks','locations':[123]}]
            phases.append('sent')
            asyncio.get_running_loop().call_soon(lambda:context.checked_locations.add(123))
        context.send_msgs=send
        def steps(memory,items,ready):
            phases.append('observed')
            yield {123},False
            assert context.checked_locations=={123}
            phases.append('projected')
            return {123},False
        runtime.poll_steps=steps
        assert await poll_runtime(context,object())==({123},False)
        assert phases==['observed','sent','projected']
    asyncio.run(test())


def test_seed_switch_at_checkpoint_cancels_old_runtime_writes():
    async def test():
        phases=[]
        runtime=SimpleNamespace(journal=SimpleNamespace(identity={'team':0,'slot':1,'seed':'old'},persistence_pending=False))
        context=SimpleNamespace(runtime=runtime,items_received=[],history_ready=True,
            authenticated_identity=(0,1,'old'),server=None,slot=1,operation_status={})
        def steps(*args):
            try:
                asyncio.get_running_loop().call_soon(lambda:setattr(context,'runtime',None))
                yield set(),False
                pytest.fail('must not resume old native writer after disconnect')
            finally:phases.append('closed')
        runtime.poll_steps=steps
        assert await poll_runtime(context,object())==(set(),False)
        assert phases==['closed']
    asyncio.run(test())
