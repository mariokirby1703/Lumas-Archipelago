"""Regression tests for bounded, authenticated Sonic/Dolphin hot paths.

These use local memory doubles, not claims of a measured live Dolphin FPS.
"""
from types import SimpleNamespace
import struct
import time
import pytest

from ..client import memory as memory_module
from ..client.memory import DMEBackend, SonicMemory, MemoryUnavailable
from ..client import ap_hud_connected as hud


class HookedEngine:
    def __init__(self):
        self.writes=[]
    def is_hooked(self):return True
    def get_status(self):return SimpleNamespace(name='hooked')
    def write_bytes(self,address,data):self.writes.append((address,bytes(data)))


def test_read_only_scene_proof_requires_current_boot_and_signature():
    from ..client.native_dol import SIGNATURE
    class MemoryMap:
        def __init__(self):self.data={0x80000000:b'SNCP8P\x00\x00',SIGNATURE:b'X'*64}
        def read_bytes(self,address,size):return self.data[address][:size]
    backend=MemoryMap();m=SonicMemory(backend)
    m._scene_proof=(time.monotonic(),backend.data[0x80000000],backend.data[SIGNATURE])
    assert m.scene_read_verified()
    backend.data[SIGNATURE]=b'Y'*64
    with pytest.raises(MemoryUnavailable,match='signature changed'):m.scene_read_verified()
    assert m._scene_proof is None
    backend.data[SIGNATURE]=b'X'*64
    m._scene_proof=(time.monotonic()-.30,backend.data[0x80000000],backend.data[SIGNATURE])
    assert not m.scene_read_verified()


def test_process_snapshot_is_cached_for_reads_but_mutation_forces_fresh_enumeration(monkeypatch):
    from ..client import mem2_windows
    monkeypatch.setattr(memory_module,'os',SimpleNamespace(name='nt'))
    calls=[]
    monkeypatch.setattr(mem2_windows,'dolphin_processes',lambda: calls.append(1) or [{'pid':123}])
    backend=DMEBackend(HookedEngine())
    assert backend.instance_info()['process_candidates'][0]['pid']==123
    assert backend.instance_info()['process_candidates'][0]['pid']==123
    assert len(calls)==1
    backend.write_bytes(0x80010000,b'\x01')
    assert len(calls)==2
    assert backend.engine.writes==[(0x80010000,b'\x01')]


def test_batched_hud_writes_recheck_after_scope_and_fail_on_pid_change(monkeypatch):
    from ..client import mem2_windows
    monkeypatch.setattr(memory_module,'os',SimpleNamespace(name='nt'))
    calls=[];pid=[123]
    monkeypatch.setattr(mem2_windows,'dolphin_processes',lambda: calls.append(1) or [{'pid':pid[0]}])
    backend=DMEBackend(HookedEngine())
    with backend.hud_write_batch():
        backend.write_bytes(0x80010000,b'\x01')
        backend.write_bytes(0x80010004,b'\x02')
    assert len(calls)==1
    # Outside the batch every write independently checks process identity.
    backend.write_bytes(0x80010008,b'\x03')
    assert len(calls)==2
    backend.fallback=SimpleNamespace(pid=123,close=lambda:None)
    pid[0]=456
    with pytest.raises(MemoryUnavailable,match='MEM2 PID changed'):
        backend.write_bytes(0x8001000c,b'\x04')


def test_hud_ack_reads_group_close_addresses_without_changing_values():
    class ReadMemory:
        def __init__(self):self.calls=0
        def read_bytes(self,address,size):
            self.calls+=1
            return b''.join(struct.pack('>I',7) for _ in range((size+3)//4))[:size]
        def read_u32(self,address):return 7
    m=ReadMemory();boxes={f'title{i}':(0x90010000+i*16,0x90100000+i*256) for i in range(90)}
    observed=hud.mailbox_acks(m,boxes)
    assert len(observed)==90 and set(observed.values())=={7}
    assert m.calls<20


def test_hud_ack_unreadable_bulk_span_falls_back_to_single_words():
    class ReadMemory:
        def read_bytes(self,address,size):
            if size>4:raise MemoryUnavailable('unmapped intervening guest heap')
            return struct.pack('>I',11)
        def read_u32(self,address):return 11
    boxes={'a':(1,0x90000000),'b':(2,0x90000100)}
    assert hud.mailbox_acks(ReadMemory(),boxes)=={0x90000000:11,0x90000100:11}


@pytest.mark.parametrize('module,name,args,kwargs', [
    ('progression_hook','payload',(),{}),
    ('capsule_refresh','payload_words',(),{}),
    ('movement_gate','payload',(),{'gecko':True}),
    ('gameplay_controls','payload',('boost_add',),{}),
])
def test_cached_assembler_preserves_bytes_and_returns_independent_storage(module,name,args,kwargs):
    from importlib import import_module
    function=getattr(import_module('worlds.sonic_colours.client.'+module),name)
    function.cache_clear()
    expected=function.__wrapped__(*args,**kwargs)
    first=function(*args,**kwargs)
    assert first==expected
    words=first if isinstance(first,list) else first[0]
    words[0]^=1
    assert function(*args,**kwargs)==expected
    assert function.cache_info().hits==1


def test_cpk_read_cache_is_bounded_and_invalidated_by_source_changes(tmp_path,monkeypatch):
    from ..tools import hud_cpk
    path=tmp_path/'data.cpk';path.write_bytes(b'abcdefgh')
    cpk=hud_cpk.CPK.__new__(hud_cpk.CPK)
    cpk.path=path;cpk.content_base=0
    cpk._cache_limit=4;cpk._cache_size=0;cpk._read_cache={}
    calls=[]
    monkeypatch.setattr(hud_cpk,'decompress',lambda data:calls.append(data) or data)
    row={'FileOffset':0,'FileSize':4,'ExtractSize':4}
    assert cpk.read(row)==cpk.read(row)==b'abcd'
    assert len(calls)==1
    assert cpk.read(dict(row,FileOffset=4))==b'efgh'
    assert cpk._cache_size==4 and len(cpk._read_cache)==1
    path.write_bytes(b'changed!!')
    assert cpk.read(row)==b'chan'
    assert len(calls)==3


def actor_memory(count=100):
    from ..client.memory import valid_range
    class Memory:
        def __init__(self):self.data={};self.calls=0
        def put(self,address,value):
            for i,b in enumerate(struct.pack('>I',value)):self.data[address+i]=b
        def read_bytes(self,address,size):
            self.calls+=1
            return bytes(self.data.get(address+i,0) for i in range(size))
        def read_u32(self,address):return int.from_bytes(self.read_bytes(address,4),'big')
        def read_ptr_checked(self,address,size=4):
            value=self.read_u32(address)
            if value%4 or not valid_range(value,size):raise MemoryUnavailable('invalid_pointer')
            return value
    m=Memory();stage=0x90001000;manager=0x90002000;sentinel=manager+24
    m.put(stage+24,manager);m.put(manager+20,count)
    nodes=[0x90003000+i*32 for i in range(count)]
    actors=[0x90100000+i*64 for i in range(count)]
    m.put(sentinel,nodes[0] if nodes else sentinel)
    m.put(sentinel+4,nodes[-1] if nodes else sentinel)
    for i,(node,actor) in enumerate(zip(nodes,actors)):
        m.put(node,nodes[i+1] if i+1<count else sentinel)
        m.put(node+4,nodes[i-1] if i else sentinel)
        m.put(node+8,actor);m.put(actor+52,manager)
    return m,stage,nodes,actors


def test_actor_walk_halves_per_actor_process_reads():
    from ..client.native_read import read_actors
    m,stage,nodes,actors=actor_memory()
    assert read_actors(m,stage)==actors
    assert m.calls==2*len(actors)+5


@pytest.mark.parametrize('failure',['backlink','owner','pointer','cycle','count'])
def test_batched_actor_walk_rejects_corrupt_ownership(failure):
    from ..client.native_read import read_actors
    m,stage,nodes,actors=actor_memory(3)
    if failure=='backlink':m.put(nodes[1]+4,0)
    elif failure=='owner':m.put(actors[1]+52,0)
    elif failure=='pointer':m.put(nodes[1]+8,2)
    elif failure=='cycle':m.put(nodes[-1],nodes[0])
    else:m.put(0x90002000+20,4)
    with pytest.raises(MemoryUnavailable):read_actors(m,stage)
