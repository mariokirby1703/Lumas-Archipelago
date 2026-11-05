from pathlib import Path
import pytest
from ..client.memory import SonicMemory,MemoryUnavailable,SAVE_SLOT_COUNT,SAVE_SLOT_STRIDE
from ..client.versions import VERSION
from .test_memory import FakeBackend


@pytest.mark.parametrize('index',range(6))
def test_six_real_slots_have_independent_checked_addresses(index):
    backend = FakeBackend()
    manager,container = 0x90000100,0x90001000
    backend.put(VERSION['manager_global_candidate'],manager.to_bytes(4,'big'))
    backend.put(manager+0x30,container.to_bytes(4,'big'))
    backend.put(container,bytes([index]))
    memory = SonicMemory(backend)
    selected = container+8+index*SAVE_SLOT_STRIDE
    expected = manager,container,index,selected,selected+0x1c
    assert memory.resolve_flags_ptr() == expected
    assert memory.resolve_flags_ptr(allow_working=True) == expected
    assert memory.trace_save_chain()['chain'] == expected
    assert not backend.writes


@pytest.mark.parametrize('index',[6,7,254,255])
def test_invalid_indices_never_become_selected_save_addresses(index):
    backend = FakeBackend()
    backend.put(VERSION['manager_global_candidate'],(0x90000100).to_bytes(4,'big'))
    backend.put(0x90000130,(0x90001000).to_bytes(4,'big'))
    backend.put(0x90001000,bytes([index]))
    memory = SonicMemory(backend)
    for working in (False,True):
        with pytest.raises(MemoryUnavailable):memory.resolve_flags_ptr(allow_working=working)
    assert memory.trace_save_chain()['first_failure']['reason']=='index_out_of_range'
    assert not backend.writes


def test_private_original_constructor_and_accessor_confirm_six_slots():
    from ..client.native_dol import Dol
    path=Path('build/sonic_colours_reference/memdumps_and_more/main.dol')
    if not path.exists():pytest.skip('private original main.dol absent')
    image=Dol(path.read_bytes())
    assert image.read(0x8015F9F4,4)==bytes.fromhex('281e0006')
    assert image.read(0x8015FA20,4)==bytes.fromhex('38039608')
    assert SAVE_SLOT_COUNT==6 and SAVE_SLOT_STRIDE==0x19608


@pytest.mark.parametrize('index',range(7))
def test_grand_map_mailbox_accepts_all_six_slots(monkeypatch,index):
    import struct
    from ..client import map_refresh
    backend=FakeBackend();memory=SonicMemory(backend)
    words,offset=map_refresh.payload();target=0x80010000
    backend.put(target+offset,struct.pack('>4I',0,0,0x90001000,index))
    monkeypatch.setattr(map_refresh,'inspect_c2',lambda *args,**kwargs:{'installed':True,'target':target})
    if index<6:assert map_refresh.installed_data(memory)==target+offset
    else:
        with pytest.raises(MemoryUnavailable):map_refresh.installed_data(memory)
