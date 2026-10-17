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
