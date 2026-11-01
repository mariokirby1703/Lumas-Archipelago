from types import SimpleNamespace

import pytest

from ..client import memory as module


def setup(monkeypatch):
    monkeypatch.setattr(module,'os',SimpleNamespace(name='nt'))
    clock = [100.]
    monkeypatch.setattr(module.time,'monotonic',lambda:clock[0])
    context,table = 0x90AB6FE0,0x90001000
    words = {0x808F336C:0x80010000,0x80010004:0x80020000,0x8002001C:0x80030000,
             0x80030034:context,0x808F34F8:table}
    class Engine:
        writes = []
        def is_hooked(self):return True
        def get_status(self):return SimpleNamespace(name='hooked')
        def read_bytes(self,address,size):return words.get(address,0).to_bytes(4,'big')[:size]
        def write_bytes(self,address,data):self.writes.append((address,data))
    class Alias:
        pid = 17
        closed = False
        writes = []
        values = {context:bytes.fromhex('80759438'),table:bytes.fromhex('8075db5c')}
        def read(self,address,size):return self.values.get(address,bytes(size))
        def write(self,address,data):self.writes.append((address,data))
        def close(self):self.closed=True
    engine,alias = Engine(),Alias()
    backend = module.DMEBackend(engine)
    backend.instance_info = lambda **kwargs: {'process_candidates':[{'pid':17}]}
    opened = []
    backend._open_mem2_alias = lambda: opened.append(True) or alias
    return backend,engine,alias,words,context,table,clock,opened


def test_zero_filled_reads_switch_only_after_two_independent_native_owners(monkeypatch):
    backend,engine,alias,words,context,table,clock,opened = setup(monkeypatch)
    assert backend.read_bytes(context,4) == bytes(4)
    assert backend.recover_zero_mem2(context,table)
    assert backend.read_bytes(context,4) == bytes.fromhex('80759438')
    assert backend.fallback is alias
    assert not engine.writes and not alias.writes
    assert not backend.recover_zero_mem2(context,table)
    assert len(opened) == 1
    backend.write_bytes(context+4,b'abcd')
    assert alias.writes == [(context+4,b'abcd')]
    assert not engine.writes


@pytest.mark.parametrize('failure',['stage','table','changed_roots','pid','ambiguous','wrong_root','out_of_range','nonzero'])
def test_unverified_aliases_never_replace_dme(monkeypatch,failure):
    backend,engine,alias,words,context,table,clock,opened = setup(monkeypatch)
    alias.values = dict(alias.values)
    if failure == 'stage':alias.values[context] = bytes(4)
    if failure == 'table':alias.values[table] = bytes(4)
    if failure == 'changed_roots':
        def candidate():
            words[0x80030034] = context+4
            return alias
        backend._open_mem2_alias = candidate
    if failure == 'pid':alias.pid = 18
    if failure == 'ambiguous':backend.instance_info = lambda **kw: {'process_candidates':[{'pid':17},{'pid':18}]}
    if failure == 'wrong_root':words[0x80030034] = context+4
    if failure == 'out_of_range':context = 0x94000000
    if failure == 'nonzero':words[context] = 0x80759438
    assert not backend.recover_zero_mem2(context,table)
    assert backend.fallback is None
    assert not engine.writes and not alias.writes
    if failure in ('stage','table','changed_roots','pid'):
        assert alias.closed


def test_failed_probes_are_throttled_and_close_drops_alias(monkeypatch):
    backend,engine,alias,words,context,table,clock,opened = setup(monkeypatch)
    alias.values = {context:bytes(4),table:bytes(4)}
    assert not backend.recover_zero_mem2(context,table)
    assert not backend.recover_zero_mem2(context,table)
    assert len(opened) == 1
    clock[0] += 5
    alias.values = {context:bytes.fromhex('80759438'),table:bytes.fromhex('8075db5c')}
    assert backend.recover_zero_mem2(context,table)
    backend.close()
    assert backend.fallback is None and alias.closed


def test_zero_context_requests_probe_without_inventing_a_scene():
    from ..client.memory import SonicMemory
    from ..client.native_read import read_stage_objects
    from .test_memory import FakeBackend
    backend = FakeBackend()
    words = {0x808F336C:0x80010000,0x80010000:0x80758DB8,0x80010004:0x80020000,
             0x80020000:0x80010000,0x8002001C:0x80030000,0x80030000:0x80758F38,
             0x80030034:0x90AB6FE0,0x808F34F8:0x90001000}
    for address,value in words.items():backend.put(address,value.to_bytes(4,'big'))
    calls = []
    backend.recover_zero_mem2 = lambda context,table: calls.append((context,table)) or False
    rows = read_stage_objects(SonicMemory(backend),include_pickups=False)
    assert calls == [(0x90AB6FE0,0x90001000)]
    assert rows[0]['vtable'] == 0
    assert 'scene' not in rows[0]
