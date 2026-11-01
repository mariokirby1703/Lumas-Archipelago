from types import SimpleNamespace

import pytest

from ..client import mem2_shared as module


class Function:
    def __init__(self,result):
        self.result = result
        self.calls = []
    def __call__(self,*args):
        self.calls.append(args)
        return self.result(*args) if callable(self.result) else self.result


def setup(monkeypatch):
    from ..client.native_dol import ARENA,plan
    from ..client.native_events import SIZE,FRAME_FENCE
    frame = ARENA+len(plan()[1])-SIZE+FRAME_FENCE
    data = {(0x80000000,8):b'SNCP8P\0\0',(0x80004000,32):bytes(range(32)),
            (0x80002FC0,64):b'SCAPNAT1'+bytes(56),
            (0x808F336C,4):bytes.fromhex('80911f00'),(0x808F34F8,4):bytes.fromhex('90b00000'),
            (0x808F3628,4):bytes.fromhex('80b3fac0'),(frame,4):(123).to_bytes(4,'big')}
    shared = {(address-0x80000000,size):value for (address,size),value in data.items()}
    engine = SimpleNamespace(read_bytes=lambda address,size:data.get((address,size),bytes(size)))
    kernel = SimpleNamespace(**{name:Function(result) for name,result in {
        'OpenFileMappingW':7,'MapViewOfFile':0x10000000,'UnmapViewOfFile':1,'CloseHandle':1,
        'GetCurrentProcess':-1,'ReadProcessMemory':1,'WriteProcessMemory':1}.items()})
    monkeypatch.setattr(module.c,'WinDLL',lambda *args,**kwargs:kernel,raising=False)
    monkeypatch.setattr(module.c,'get_last_error',lambda:2,raising=False)
    monkeypatch.setattr(module,'dolphin_processes',lambda:[{'pid':17}])
    monkeypatch.setattr(module.WindowsSharedMEM2,'_read_offset',
                        lambda self,offset,size:shared.get((offset,size),bytes(size)))
    return engine,kernel,data,shared,frame


def test_pid_named_mapping_is_opened_without_creating_or_scanning(monkeypatch):
    engine,kernel,data,shared,frame = setup(monkeypatch)
    alias = module.WindowsSharedMEM2(engine,writable=False)
    assert alias.pid == 17
    assert kernel.OpenFileMappingW.calls == [(4,False,'dolphin-emu.17')]
    assert kernel.MapViewOfFile.calls == [(7,4,0,0,module.VIEW_SIZE)]
    shared[module.MEM2_OFFSET+0xAB6FE0,4] = bytes.fromhex('80759438')
    assert alias.read(0x90AB6FE0,4) == bytes.fromhex('80759438')
    with pytest.raises(ValueError):alias.write(0x90000000,b'test')
    assert not kernel.WriteProcessMemory.calls
    alias.close()
    assert kernel.UnmapViewOfFile.calls == [(0x10000000,)]
    assert kernel.CloseHandle.calls == [(7,)]


@pytest.mark.parametrize('failure',['header','signature','text','roots','frame','ambiguous','open','view'])
def test_mismatched_sources_and_failed_views_are_rejected(monkeypatch,failure):
    engine,kernel,data,shared,frame = setup(monkeypatch)
    if failure == 'header':shared[0,8] = b'SNCE8P\0\0'
    if failure == 'signature':shared[0x2FC0,64] = bytes(64)
    if failure == 'text':shared[0x4000,32] = bytes(32)
    if failure == 'roots':shared[0x8F34F8,4] = bytes(4)
    if failure == 'frame':shared[frame-0x80000000,4] = (122).to_bytes(4,'big')
    if failure == 'ambiguous':monkeypatch.setattr(module,'dolphin_processes',lambda:[{'pid':17},{'pid':18}])
    if failure == 'open':kernel.OpenFileMappingW.result = 0
    if failure == 'view':kernel.MapViewOfFile.result = 0
    with pytest.raises((RuntimeError,OSError)):
        module.WindowsSharedMEM2(engine)
    assert not kernel.WriteProcessMemory.calls
    if failure not in ('ambiguous','open'):
        assert kernel.CloseHandle.calls == [(7,)]


def test_source_changes_are_rechecked_before_later_writes(monkeypatch):
    engine,kernel,data,shared,frame = setup(monkeypatch)
    alias = module.WindowsSharedMEM2(engine)
    data[frame,4] = (124).to_bytes(4,'big')
    with pytest.raises(RuntimeError,match='frame source'):
        alias.validate_source()
    alias.close()


def test_wii_bounds_are_enforced(monkeypatch):
    engine,kernel,data,shared,frame = setup(monkeypatch)
    alias = module.WindowsSharedMEM2(engine)
    for address,size in ((0x8FFFFFFF,4),(0x93FFFFFF,4),(0x94000000,4),(0x90000000,0)):
        with pytest.raises(ValueError):alias.read(address,size)
    alias.close()
