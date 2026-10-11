"""Original CPK identity, emitted PPC, durable checks and native-data safety.

Guest execution is simulated here; this is not a Dolphin pickup validation.
"""
import struct
from dataclasses import replace
from pathlib import Path
import pytest
from BaseClasses import CollectionState
from ..medals import MEDALS
from ..Items import ITEM_TABLE, WISP_ITEMS
from ..client import medal_hook
from ..client.memory import SonicMemory, MemoryUnavailable
from ..client.native_read import read_medals
from ..client.journal import Journal
from ..client.runtime import inventory
from ..client.progression_hook import identity_tag
from ..client.cpk import CPK
from .test_memory import FakeBackend
from .test_runtime import IDENTITY, snapshot
from .test_pickup_integration import Overlay
from .test_native_originals import PAIRS
from . import generate

SOURCE = Path(__file__).parents[1]/'notes/memdumps_and_more/sonic2010_0.cpk'


@pytest.mark.skipif(not SOURCE.exists(), reason='original PAL CPK not available')
def test_all_21_medal_identities_against_original_orc():
    archive = CPK(SOURCE)
    for medal in MEDALS:
        row = next(r for r in archive.toc.rows if r['FileName'] == medal['mission_id']+'_obj_00.orc')
        raw = archive.read(row)
        assert raw[0x18:0x1c] == b'BINA' and raw[0x20:0x24] == b'SOBJ'
        u32 = lambda offset: struct.unpack_from('>I', raw, offset)[0]
        types, offset = u32(0x28), u32(0x2c)+0x20
        matches = []
        for i in range(types):
            string, count, indices = struct.unpack_from('>3I', raw, offset+i*12)
            name = raw[string+0x20:].split(b'\0',1)[0]
            if name != b'EggmanMedal': continue
            for j in range(count):
                index = struct.unpack_from('>H', raw, indices+0x20+j*2)[0]
                record = u32(u32(0x34)+0x20+index*4)+0x20
                object_id, positions, instances = u32(record)&0xfffff, u32(record+0x18)+0x20, u32(record+0x1c)
                for instance in range(instances):
                    matches.append((object_id, instance, struct.unpack_from('>3f',raw,positions+instance*24)))
        assert len(matches) == 1
        object_id, instance, position = matches[0]
        assert (object_id,instance) == (medal['object_id'],medal['instance_index'])
        assert position == pytest.approx(medal['position'], abs=.002)


def native_fixture(medal=MEDALS[0]):
    b=FakeBackend(); m=SonicMemory(b)
    stage,manager,actor,wrapper,record,descriptor,vector = (0x90001000+i*0x1000 for i in range(7))
    values={stage+0x18:manager, actor:medal_hook.VTABLE, actor+0xc:123,
            actor+0x34:manager,actor+0x64:wrapper,wrapper+4:actor,wrapper+8:record,wrapper+12:descriptor,
            descriptor:0x80770FA0,descriptor+0x10:record,descriptor+0x1c:wrapper,
            descriptor+0x14:medal['instance_index'],record:medal['object_id'],
            record+0x18:vector,record+0x1c:1}
    for address,value in values.items(): b.put(address,value.to_bytes(4,'big'))
    b.put(vector,struct.pack('>3f',*medal['position']))
    return b,m,stage,actor


def install(b, target=0x80002000):
    words,offset=medal_hook.payload();hook=medal_hook.HOOK
    words[-1]=0x48000000 | ((hook+4-(target+len(words)*4-4))&0x3fffffc)
    b.write_bytes(target,struct.pack('>'+'I'*len(words),*words))
    b.write_bytes(hook,(0x48000000 | ((target-hook)&0x3fffffc)).to_bytes(4,'big'))
    return target+offset


def execute_pickup(b, actor, target=0x80002000):
    words,_=medal_hook.payload();regs=list(range(32));regs[1]=0x900f0000;regs[28]=actor
    original=regs[:];lr,cr=0x80001234,0x12345678;before=(lr,cr);pc=0;cmp=0
    for _ in range(300):
        w=words[pc];pc+=1
        if not w: break
        op=w>>26;rt=w>>21&31;ra=w>>16&31;u=w&65535;imm=u-65536 if u&32768 else u
        if op==14: regs[rt]=((regs[ra] if ra else 0)+imm)&0xffffffff
        elif op==15: regs[rt]=(imm<<16)&0xffffffff
        elif op in (32,34): regs[rt]=int.from_bytes(b.read_bytes(regs[ra]+imm,1 if op==34 else 4),'big')
        elif op in (36,37):
            addr=regs[ra]+imm;b.write_bytes(addr,regs[rt].to_bytes(4,'big'))
            if op==37:regs[ra]=addr
        elif op==11:cmp=(regs[ra]>imm)-(regs[ra]<imm)
        elif op==16:
            if {0x41820000:cmp==0,0x40820000:cmp!=0}[w&0xffff0000]:pc=pc-1+imm//4
        elif op==18:
            delta=w&0x3fffffc
            if delta&0x2000000:delta-=0x4000000
            if w&1:lr=target+pc*4
            pc=pc-1+delta//4
        elif w==0x7c0802a6:regs[0]=lr
        elif w==0x7c000026:regs[0]=cr
        elif w==0x7d8802a6:regs[12]=lr
        elif w==0x7c0ff120:cr=regs[0]
        elif w==0x7c0803a6:lr=regs[0]
        elif op==31 and w&0x7ff==0:
            rhs=regs[w>>11&31];cmp=(regs[ra]>rhs)-(regs[ra]<rhs)
        elif op==31 and w&0x7ff==0x378:regs[ra]=regs[rt]|regs[w>>11&31]
        elif w==0x60000000:pass
        else:raise AssertionError(hex(w))
    else:raise AssertionError('PPC capture loop')
    assert regs[3]==actor
    assert all(regs[i]==original[i] for i in range(32) if i!=3)
    assert (lr,cr)==before


@pytest.mark.parametrize('medal', [MEDALS[0],MEDALS[7]])
def test_native_pickup_latch_durable_restart_exit_and_dedup(tmp_path,medal):
    b,m,stage,actor=native_fixture(medal);data=install(b)
    chain=(0x90080000,0x90081000,1,0x90082000)
    b.put(chain[1],b'\x01');m.resolve_flags_ptr=lambda **kw:chain
    m.write_guard=lambda *args: 'test bound control'
    native=read_medals(m,stage,medal['mission_id'],[actor])
    snap=snapshot(scene='gameplay',actual_mission=medal['mission_id'],evidence={'chain':chain,
        'native_data':{'stage_objects':[{'medals':native}]}})
    slot=generate({'eggman_heart_sanity':True}).worlds[1].fill_slot_data()
    with Journal(tmp_path,IDENTITY) as j:
        medal_hook.configure(m,snap,j)
        medal_hook.observe(m,snap,j,slot);assert not j.data['pickup_checks']
        execute_pickup(b,actor)
        assert m.read_u32(data+40)==1<<medal['index']
    with Journal(tmp_path,IDENTITY) as j:
        # Native latch remains even after actor disposal/exit and client restart.
        later=replace(snap,scene='world_map',evidence={'chain':chain})
        medal_hook.observe(m,later,j,slot)
        assert j.data['pickup_checks']==[medal['code']]
        medal_hook.observe(m,later,j,slot);assert len(j.data['pickup_events'])==1
        medal_hook.configure(m,later,j);assert m.read_u32(data+8)==0
    with Journal(tmp_path,{**IDENTITY,'seed':'other seed'}) as j:
        medal_hook.observe(m,snap,j,slot);assert not j.data['pickup_checks']
        medal_hook.configure(m,snap,j);assert m.read_u32(data+40)==0


def test_native_identity_rejects_wrong_wrapper_and_position():
    b,m,stage,actor=native_fixture()
    wrapper=m.read_u32(actor+0x64);b.put(wrapper+4,bytes(4))
    with pytest.raises(MemoryUnavailable,match='medal_native_owner'):read_medals(m,stage,MEDALS[0]['mission_id'],[actor])
    b.put(wrapper+4,actor.to_bytes(4,'big'))
    vector=m.read_u32(m.read_u32(wrapper+8)+0x18);b.put(vector,struct.pack('>f',12345.))
    assert not read_medals(m,stage,MEDALS[0]['mission_id'],[actor])


@pytest.mark.skipif(not PAIRS,reason='original PAL RAM absent')
def test_medal_thunk_only_exact_normalization_and_mutable_words():
    b=Overlay(PAIRS[0]);m=SonicMemory(b);address=install(b)
    assert medal_hook.installed_data(m)==address
    m.verify_revision()
    b.write_bytes(0x80002000+20,bytes(4))
    with pytest.raises(MemoryUnavailable,match='unknown_revision'):m.verify_revision()


def test_disabled_option_and_conservative_traversal_rule():
    off=generate();on=generate({'eggman_heart_sanity':True})
    assert not any(l.name.endswith(' - Eggman Heart') for l in off.get_locations())
    locations=[l for l in on.get_locations() if l.name.endswith(' - Eggman Heart')]
    assert len(locations)==21 and len({l.address for l in locations})==21
    state=CollectionState(on);assert not any(l.access_rule(state) for l in locations)
    for name in WISP_ITEMS:state.collect(on.worlds[1].create_item(name),prevent_sweep=True)
    assert all(l.access_rule(state) for l in locations)
    assert not any(l.parent_region.can_reach(state) for l in locations if l.name.startswith('Game Land 1-2'))


@pytest.mark.parametrize('seed',range(100))
def test_medals_white_lock_and_goals_fill_without_tv_item(seed):
    m=generate({'eggman_heart_sanity':True,'boost_lock':seed%2,'goal':seed%5,
                'red_ring_checks':('off','singles','per_level')[seed%3],
                'rank_checks':('off','c','all')[seed%3]},seed,fill=True)
    assert m.can_beat_game() and not m.get_unfilled_locations()
    assert 'Terminal Velocity Access' not in ITEM_TABLE
    assert all(i.name!='Terminal Velocity Access' for i in m.itempool)
    assert sum(i.name=='White Boost Wisp' for i in m.itempool)==1


def test_native_medal_capture_reaches_real_websocket_ack_without_item_history(tmp_path,monkeypatch):
    import asyncio
    import websockets
    import Utils
    from NetUtils import Endpoint, encode, decode, NetworkPlayer, NetworkSlot, SlotType
    from CommonClient import process_server_cmd
    from ..client.client import SonicContext, transmit_checks
    monkeypatch.setattr(Utils,'persistent_store',lambda *args:None)
    async def scenario():
        slot=generate({'eggman_heart_sanity':True}).worlds[1].fill_slot_data()
        ctx=SonicContext(journal_directory=tmp_path);ctx.auth='SonicPlayer'
        assert ctx.seed_name is None
        received=[]
        async def server(socket):
            await socket.send(encode([{'cmd':'RoomInfo','seed_name':slot['seed_name'],
                'version':[0,7,0],'tags':[],'password':False,'games':[],
                'hint_cost':10,'location_check_points':1}]))
            for packet in decode(await socket.recv()): assert packet['cmd']=='Connect'
            await socket.send(encode([{'cmd':'Connected','team':0,'slot':1,
                'players':[NetworkPlayer(0,1,'SonicPlayer','SonicPlayer')],
                'slot_info':{1:NetworkSlot('SonicPlayer',slot['game'],SlotType.player)},
                'missing_locations':list(slot['locations'].values()),'checked_locations':[], 'slot_data':slot}]))
            async for raw in socket:
                for packet in decode(raw):
                    if packet['cmd']=='LocationChecks':
                        received.append(packet['locations'])
                        await socket.send(encode([{'cmd':'RoomUpdate','checked_locations':packet['locations']}]))
        async with websockets.serve(server,'127.0.0.1',0) as listener:
            ctx.server_address=f'ws://127.0.0.1:{listener.sockets[0].getsockname()[1]}'
            async with websockets.connect(ctx.server_address) as socket:
                ctx.server=Endpoint(socket)
                for _ in range(2):
                    for packet in decode(await socket.recv()): await process_server_cmd(ctx,packet)
                assert not ctx.history_ready and ctx.seed_name is None
                b,m,stage,actor=native_fixture();install(b)
                chain=(0x90080000,0x90081000,1,0x90082000)
                b.put(chain[1],b'\x01');m.resolve_flags_ptr=lambda **kw:chain
                m.write_guard=lambda *args:'test bound capture'
                native=read_medals(m,stage,MEDALS[0]['mission_id'],[actor])
                snap=snapshot(evidence={'native_data':{'stage_objects':[{'medals':native}]}})
                journal=ctx.runtime.journal
                medal_hook.configure(m,snap,journal)
                execute_pickup(b,actor)
                medal_hook.observe(m,snap,journal,slot)
                assert journal.data['pickup_checks']==[MEDALS[0]['code']]
                await transmit_checks(ctx)
                for packet in decode(await asyncio.wait_for(socket.recv(),3)): await process_server_cmd(ctx,packet)
                assert received==[[MEDALS[0]['code']]]
                assert journal.data['acknowledged_locations']==[MEDALS[0]['code']]
                medal_hook.observe(m,snap,journal,slot)
                ctx.last_send=0;await transmit_checks(ctx)
                await asyncio.sleep(.02)
                assert received==[[MEDALS[0]['code']]] and not ctx.history_ready
            ctx.release_runtime()
    asyncio.run(scenario())

