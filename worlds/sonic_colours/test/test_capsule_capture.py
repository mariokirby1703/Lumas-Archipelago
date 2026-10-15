import struct
from types import SimpleNamespace
import pytest
from ..client import capsule_capture as c
from ..client.memory import MemoryUnavailable


def queue(monkeypatch,head,events):
    data=bytearray(c.DATA_SIZE);struct.pack_into('>II',data,0,head,c.MAGIC)
    for sequence,mission,object_id in events:
        raw=mission.encode()
        struct.pack_into('>8I',data,16+(sequence&31)*32,sequence,0x90010000,
                         int.from_bytes(raw[:4],'big'),int.from_bytes(raw[4:],'big'),
                         object_id,0,1,123)
    monkeypatch.setattr(c,'installed_data',lambda m:0x80002000)
    return SimpleNamespace(read_u32=lambda a:struct.unpack_from('>I',data,a-0x80002000)[0],
                           read_bytes=lambda a,n:bytes(data[a-0x80002000:a-0x80002000+n]))


def test_events_survive_actor_removal_and_keep_original_mission(monkeypatch):
    memory=queue(monkeypatch,2,[(1,'stg130',64),(2,'stg140',149)])
    head,events,overflow=c.read_events(memory)
    assert head==2 and overflow==0
    assert [(e['mission'],e['object_id']) for e in events]==[('stg130',64),('stg140',149)]
    assert c.read_events(memory,2)==(2,[],0)


def test_ring_overflow_is_reported_and_newest_events_retained(monkeypatch):
    memory=queue(monkeypatch,40,[(i,'stg110',i) for i in range(9,41)])
    head,events,overflow=c.read_events(memory,3)
    assert overflow==5 and head==40
    assert [e['sequence'] for e in events]==list(range(9,41))


def test_incomplete_entry_cannot_credit_a_pickup(monkeypatch):
    memory=queue(monkeypatch,1,[])
    with pytest.raises(MemoryUnavailable,match='publication incomplete'):c.read_events(memory)


def test_native_game_restart_restarts_sequence(monkeypatch):
    memory=queue(monkeypatch,1,[(1,'stg110',149)])
    assert c.read_events(memory,10)[1][0]['object_id']==149


def test_hook_original_is_the_native_opened_write_and_payload_fits():
    words,offset=c.payload()
    assert c.ORIGINAL==0x981C0110 and c.HOOK==0x800D4FA8
    assert words[offset//4+1]==c.MAGIC
    assert words[-1]==0
    assert len(words)*4<1600


def test_emitted_hook_publishes_identity_and_preserves_native_registers():
    from .test_memory import FakeBackend
    b=FakeBackend();target=0x80002000;actor=0x90010000
    wrapper,record,descriptor=0x90020000,0x90021000,0x90022000
    app,doc,module,stage,name=0x90030000,0x90031000,0x90032000,0x90033000,0x90034000
    words,offset=c.payload();b.put(target,struct.pack('>'+'I'*len(words),*words))
    fields={actor:0x80761534,actor+0x64:wrapper,actor+0x114:0,actor+12:123,
        wrapper+4:actor,wrapper+8:record,wrapper+12:descriptor,
        descriptor:0x80770fa0,descriptor+0x10:record,descriptor+0x1c:wrapper,
        descriptor+0x14:0,record:0xff000095,0x808f336c:app,app+4:doc,
        doc+0x1c:module,module+0x34:stage,stage:0x80759438,stage+0x4c:name}
    for a,v in fields.items():b.put(a,v.to_bytes(4,'big'))
    b.put(name,b'stg110\0\0');regs=list(range(32));regs[0]=1;regs[1]=0x900f0000;regs[28]=actor
    original=regs[:];lr=0x80001234;cr=0x12345678;pc=0;cmp=0
    for _ in range(250):
        w=words[pc];pc+=1
        if not w:break
        op=w>>26;rt=w>>21&31;ra=w>>16&31;u=w&65535;imm=u-65536 if u&32768 else u
        if op==14:regs[rt]=((regs[ra] if ra else 0)+imm)&0xffffffff
        elif op==15:regs[rt]=(imm<<16)&0xffffffff
        elif op==7:regs[rt]=(regs[ra]*imm)&0xffffffff
        elif op in (32,40):regs[rt]=int.from_bytes(b.read_bytes(regs[ra]+imm,4 if op==32 else 2),'big')
        elif op in (36,37,38):
            size=1 if op==38 else 4;addr=regs[ra]+imm;b.write_bytes(addr,(regs[rt]&((1<<(size*8))-1)).to_bytes(size,'big'))
            if op==37:regs[ra]=addr
        elif op==24:regs[ra]=regs[rt]|u
        elif op==28:regs[ra]=regs[rt]&u
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
        elif w==0x554a033e:regs[10]&=0xfffff
        elif w==0x7c0004ac:pass
        elif op==31 and w&0x7ff==0:
            rhs=regs[w>>11&31];cmp=(regs[ra]>rhs)-(regs[ra]<rhs)
        elif op==31 and w&0x7ff==0x214:regs[rt]=(regs[ra]+regs[w>>11&31])&0xffffffff
        else:raise AssertionError(hex(w))
    else:raise AssertionError('capture did not terminate')
    assert regs==original and lr==0x80001234 and cr==0x12345678
    assert b.read_bytes(actor+0x110,1)==b'\x01'
    assert int.from_bytes(b.read_bytes(target+offset,4),'big')==1
    event=struct.unpack('>8I',b.read_bytes(target+offset+16+32,32))
    assert event==(1,stage,int.from_bytes(b'stg1','big'),int.from_bytes(b'10','big'),149,0,1,123)


def test_runtime_deduplicates_native_event_after_actor_and_stage_are_gone(monkeypatch):
    from ..client.runtime import Runtime
    from ..capsules import CAPSULES_BY_NATIVE_ID
    capsule=CAPSULES_BY_NATIVE_ID['stg110',149,0]
    runtime=Runtime.__new__(Runtime)
    runtime.snapshot=SimpleNamespace(actual_mission='stg130')
    runtime.guard=SimpleNamespace(can_record_pickups=lambda s:True)
    runtime._capsule_memory=SimpleNamespace(native_patch={'abi':1})
    runtime.slot_data={'locations':{capsule.name:capsule.code}}
    data={'pickup_checks':[],'pickup_events':[]}
    def record(events,masks,checks):
        data['pickup_checks'].extend(checks);data['pickup_events'].extend(events)
    runtime.journal=SimpleNamespace(data=data,record_pickups=record)
    event=dict(sequence=1,context=0x90010000,mission='stg110',object_id=149,instance=0,raw_wisp=capsule.raw_wisp,actor_id=123)
    monkeypatch.setattr(c,'read_events',lambda memory,after:(1,[event],0))
    runtime.observe_capsules(set());runtime.observe_capsules(set())
    assert data['pickup_checks']==[capsule.code]
    assert len(data['pickup_events'])==1
    assert data['pickup_events'][0]['provenance']=='PAL_800D4FA8_native_success'
    assert runtime._capsule_event_cursor==1
