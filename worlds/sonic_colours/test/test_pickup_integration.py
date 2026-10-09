"""Production pickup/journal transport; synthetic server, original guest captures."""
import asyncio
from dataclasses import replace
import pytest
from ..client.client import SonicContext, transmit_checks
from ..client.journal import Journal
from ..client.state import SaveGuard, WritePolicy
from ..client.runtime import Runtime
from ..client.hooks import NativeHooks
from ..client.memory import SonicMemory, MemoryUnavailable
from ..Items import ITEM_TABLE
from ..Locations import LOCATION_TABLE
from . import generate
from .test_runtime import IDENTITY, snapshot
from .test_memory import FakeBackend
from .test_native_originals import PAIRS
from ..tools.read_dumps import DumpBackend


class Overlay:
    def __init__(self, pair):
        self.original = DumpBackend(*pair)
        self.bytes = {}
        self.writes = []
    def read_bytes(self, address, size):
        original = self.original.read_bytes(address, size)
        return bytes(self.bytes.get(address+i, b) for i, b in enumerate(original))
    def write_bytes(self, address, data):
        self.writes.append((address, bytes(data)))
        self.bytes.update((address+i, b) for i, b in enumerate(data))


@pytest.mark.parametrize('mode', ['singles', 'per_level'])
def test_immediate_intro_ever_mask_survives_loss_and_restart(tmp_path, mode):
    data = generate({'red_ring_checks': mode}).worlds[1].fill_slot_data()
    class Hooks:
        value = snapshot(save_identity=None, scene_verified=True, pickup_verified=True,
                         stage_epoch='intro1', actual_mission='stg110', new_game_verified=True,
                         fresh_fields=(True, True), active_rings={'stg110': frozenset()})
        def snapshot(self, memory): return self.value
    with Journal(tmp_path, IDENTITY) as journal:
        guard=SaveGuard(journal); guard.confirm_new_game()
        hooks=Hooks(); runtime=Runtime(data,journal,guard,hooks)
        runtime.poll(SonicMemory(FakeBackend()),[],False)
        for ring in range(1,6):
            hooks.value=replace(hooks.value, active_rings={'stg110': frozenset({ring})})
            checks,_=runtime.poll(SonicMemory(FakeBackend()),[],False)
            assert len(checks)==(ring if mode=='singles' else int(ring==5))
            hooks.value=replace(hooks.value, active_rings={'stg110': frozenset()})
            runtime.poll(SonicMemory(FakeBackend()),[],False)
        assert journal.data['save_identity'] is None
        assert journal.data['ever_collected_mask']['stg110']==31
        assert len(journal.data['pickup_events'])==5
    with Journal(tmp_path, IDENTITY) as journal:
        assert len(journal.data['pickup_checks'])==(5 if mode=='singles' else 1)


@pytest.mark.skipif(not PAIRS, reason='private original captures absent')
def test_original_intro_native_stats_writer_and_receipt_once(tmp_path):
    backend=Overlay(PAIRS[0]); memory=SonicMemory(backend)
    data=generate().worlds[1].fill_slot_data()
    with Journal(tmp_path, IDENTITY) as journal:
        hooks=NativeHooks(journal); guard=SaveGuard(journal); guard.confirm_new_game()
        runtime=Runtime(data,journal,guard,hooks)
        memory.write_guard=WritePolicy(memory,guard,hooks.snapshot)
        for _ in range(3): runtime.poll(memory,[],False)
        address=runtime.snapshot.rings_address
        assert memory.read_u32(address)==16
        items=[ITEM_TABLE['Rings (+10)'],ITEM_TABLE['1-Up'],ITEM_TABLE['Ring Loss Trap']]
        runtime.poll(memory,items,True)
        assert memory.read_u32(address)==0
        assert [v['state'] for v in journal.data['effects'].values()]==['confirmed']*3
        assert len(backend.writes)==3
        runtime.poll(memory,items,True)
        assert len(backend.writes)==3
        assert journal.data['save_identity'] is None


@pytest.mark.skipif(not PAIRS, reason='private original captures absent')
def test_original_intro_binding_resume_and_world_gate_write(tmp_path):
    data=generate({'wisp_unlocks':'vanilla'}).worlds[1].fill_slot_data()
    with Journal(tmp_path, IDENTITY) as journal:
        hooks=NativeHooks(journal); guard=SaveGuard(journal); guard.confirm_new_game()
        runtime=Runtime(data,journal,guard,hooks)
        for stamp in ('200443','200443','202546','205502'):
            pair=next(p for p in PAIRS if stamp in p[0].name)
            runtime.poll(SonicMemory(DumpBackend(*pair)),[],False)
        assert journal.data['save_identity']
        assert runtime.snapshot.save_identity_verified
        # New host/Dolphin session can match the persisted native witness.
        backend=Overlay(pair); memory=SonicMemory(backend); resumed=NativeHooks(journal)
        guard.disarm(); runtime.hooks=resumed
        memory.write_guard=WritePolicy(memory,guard,resumed.snapshot)
        for _ in range(3): runtime.poll(memory,[],True)
        assert guard.armed
        assert backend.writes
        flags=memory.resolve_flags_ptr()[-1]
        assert memory.read_progress_bit(flags,8)  # Game Land entry
        assert not memory.read_progress_bit(flags,21)  # unreceived Sweet Mountain
        assert not memory.read_progress_bit(flags,211)  # AP counter is zero
        assert runtime.snapshot.save_identity==journal.data['save_identity']
        selected=memory.resolve_selected_slot()[-1]
        backend.write_bytes(selected,b'bad-profile!')
        runtime.poll(memory,[],True)
        assert not guard.armed


@pytest.mark.skipif(not PAIRS, reason='private original captures absent')
def test_original_capsule_identity_colour_and_consumption(tmp_path):
    pair=next(p for p in PAIRS if '212125' in p[0].name)
    backend=Overlay(pair); memory=SonicMemory(backend)
    state=NativeHooks().snapshot(memory)
    capsules=state.evidence['native_data']['stage_objects'][0]['capsules']
    cyan=next(c for c in capsules if c['object_id']==646)
    from ..capsules import CAPSULES
    assert CAPSULES[cyan['key']].wisp_item=='Cyan Laser Unlock'
    assert not cyan['opened']
    backend.write_bytes(cyan['actor']+0x110,b'\x01')
    opened=NativeHooks().snapshot(memory)
    assert cyan['key'] in opened.opened_capsules
    # A corrupt binding prevents a capsule credit, while other player reads survive.
    backend.write_bytes(cyan['wrapper']+4,b'\x00'*4)
    rejected=NativeHooks().snapshot(memory)
    assert cyan['key'] not in rejected.opened_capsules
    assert rejected.pickup_verified


def test_real_websocket_checks_before_received_items_and_server_ack(tmp_path, monkeypatch):
    import websockets
    from NetUtils import Endpoint, encode, decode, NetworkSlot, SlotType, NetworkPlayer
    from CommonClient import process_server_cmd
    import Utils
    # Avoid CommonClient's global user-settings write; the transport is real TCP.
    monkeypatch.setattr(Utils,'persistent_store',lambda *args: None)
    async def scenario():
        data=generate().worlds[1].fill_slot_data()
        ctx=SonicContext(journal_directory=tmp_path)
        ctx.seed_name=data['seed_name']
        received=[]; checks_received=0
        async def server(socket):
            nonlocal checks_received
            await socket.send(encode([{'cmd':'Connected','team':0,'slot':1,
                'players':[NetworkPlayer(0,1,'SonicPlayer','SonicPlayer')],
                'slot_info':{1:NetworkSlot('SonicPlayer',data['game'],SlotType.player)},
                'missing_locations':list(data['locations'].values()),'checked_locations':[],
                'slot_data':data}]))
            async for raw in socket:
                for packet in decode(raw):
                    received.append(packet)
                    if packet['cmd']=='LocationChecks':
                        checks_received += 1
                        if checks_received == 1:
                            continue  # Synthetic packet/ACK loss; retained journal must retry.
                        await socket.send(encode([{'cmd':'RoomUpdate','checked_locations':packet['locations']}]))
        async with websockets.serve(server,'127.0.0.1',0) as listener:
            ctx.server_address=f'ws://127.0.0.1:{listener.sockets[0].getsockname()[1]}'
            async with websockets.connect(ctx.server_address) as socket:
                ctx.server=Endpoint(socket)
                for packet in decode(await socket.recv()): await process_server_cmd(ctx,packet)
                assert not ctx.history_ready
                runtime=ctx.runtime; guard=runtime.guard
                guard.confirm_new_game()
                value=snapshot(save_identity=None, scene_verified=True,pickup_verified=True,
                    stage_epoch='intro',actual_mission='stg110',new_game_verified=True,fresh_fields=(True,True))
                guard.observe(value); runtime.snapshot=value; runtime.observe_pickups()
                runtime.snapshot=replace(value,active_rings={'stg110':frozenset({3})})
                runtime.observe_pickups()
                code=LOCATION_TABLE['Tropical Resort Act 1 - Red Ring 3'].code
                assert runtime.journal.data['pickup_checks']==[code]
                assert not runtime.journal.data['acknowledged_locations']
                await transmit_checks(ctx)
                await asyncio.sleep(.02)
                assert not runtime.journal.data['acknowledged_locations']
                ctx.last_send = 0
                runtime.snapshot = None  # Dolphin unavailable must not block replay.
                await transmit_checks(ctx)
                for packet in decode(await asyncio.wait_for(socket.recv(),3)):
                    await process_server_cmd(ctx,packet)
                assert any(p['cmd']=='LocationChecks' and p['locations']==[code] for p in received)
                assert runtime.journal.data['acknowledged_locations']==[code]
                assert not ctx.history_ready and runtime.journal.data['save_identity'] is None
                count=len(received); await transmit_checks(ctx); await asyncio.sleep(.02)
                assert not any(p['cmd']=='LocationChecks' for p in received[count:])
                ctx.seed_name='different-seed'
                with pytest.raises(MemoryUnavailable,match='identity'):
                    await transmit_checks(ctx)
            ctx.server=None
        ctx.release_runtime(); await ctx.shutdown()
    asyncio.run(scenario())

def test_capsule_opening_in_intro_is_durable_and_instance_specific(tmp_path):
    from ..capsules import CAPSULES
    data=generate({'wisp_capsule_sanity':'story','wisp_unlocks':'vanilla'}).worlds[1].fill_slot_data()
    candidates=[c for c in CAPSULES.values() if c.eligible and c.mission=='stg110' and c.wisp_item=='White Boost Unlock'][:2]
    assert len(candidates)==2
    with Journal(tmp_path,IDENTITY) as journal:
        guard=SaveGuard(journal);guard.confirm_new_game()
        runtime=Runtime(data,journal,guard,None)
        value=snapshot(save_identity=None,scene_verified=True,pickup_verified=True,
                       stage_epoch='intro',actual_mission='stg110',new_game_verified=True,fresh_fields=(True,True))
        guard.observe(value)
        native=[{'key':c.key,'opened':False,'actor_id':i} for i,c in enumerate(candidates)]
        runtime.snapshot=replace(value,evidence={'native_data':{'stage_objects':[{'capsules':native}]}})
        runtime.observe_capsules(frozenset())
        for c in native:
            c['opened']=True
            runtime.observe_capsules(frozenset())
        assert journal.data['pickup_checks']==sorted(c.code for c in candidates)
        assert len(journal.data['pickup_events'])==2
        runtime.snapshot=replace(runtime.snapshot,stage_epoch='retry')
        runtime.observe_capsules(frozenset())
        assert len(journal.data['pickup_events'])==2
        assert journal.data['save_identity'] is None


@pytest.mark.skipif(not PAIRS, reason='private original captures absent')
def test_original_bound_colour_permission_fields_and_no_physical_ring_mutation(tmp_path):
    from ..client.runtime import inventory
    data=generate().worlds[1].fill_slot_data()
    with Journal(tmp_path,IDENTITY) as journal:
        hooks=NativeHooks(journal);guard=SaveGuard(journal);guard.confirm_new_game()
        runtime=Runtime(data,journal,guard,hooks)
        for stamp in ('200443','200443','202546','205502'):
            pair=next(p for p in PAIRS if stamp in p[0].name)
            runtime.poll(SonicMemory(DumpBackend(*pair)),[],False)
        pair=next(p for p in PAIRS if '212125' in p[0].name)
        backend=Overlay(pair);memory=SonicMemory(backend)
        memory.write_guard=WritePolicy(memory,guard,hooks.snapshot)
        for _ in range(3):runtime.poll(memory,[],False)
        before=runtime.snapshot.persisted_rings
        owned=inventory([ITEM_TABLE['Cyan Laser Unlock']])
        with pytest.raises(MemoryUnavailable,match='tutorial'):
            hooks.project_permissions(memory,runtime.snapshot,owned,data)
        stage=runtime.snapshot.evidence['native_data']['stage_objects'][0]
        assert memory.read_u8(stage['stage']+0x61)==2
        assert memory.read_u8(stage['actor_state']+0x90)==2
        flags=memory.resolve_flags_ptr()[-1]
        assert memory.read_progress_bit(flags,1)
        assert not memory.read_progress_bit(flags,0)
        assert NativeHooks().snapshot(memory).persisted_rings==before
