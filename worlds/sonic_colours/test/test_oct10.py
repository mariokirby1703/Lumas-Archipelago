import struct
import pytest
from ..client.capsule_refresh import inspect_installed
from ..client.memory import SonicMemory, MemoryUnavailable
from ..client.hooks import NativeHooks
from ..world_constants import load_data
from .test_memory import FakeBackend
from .test_pickup_integration import Overlay
from .test_native_originals import PAIRS


def captured(b):
    f=load_data('capsule_hook_live_oct10.json')
    b.write_bytes(f['hook'],f['instruction'].to_bytes(4,'big'))
    b.write_bytes(f['target']-8,bytes.fromhex(f['header']))
    b.write_bytes(f['target'],bytes.fromhex(f['payload_hex']))
    return f


def test_actual_dolphin_c2_capture_is_exactly_recognized():
    b=FakeBackend();f=captured(b);m=SonicMemory(b)
    r=inspect_installed(m)
    assert r['variant']=='c9364ebe' and r['payload_length']==r['actual_header_length']==496
    assert r['return_target']==0x800d4828
    b.put(f['target']+40,bytes(4))
    with pytest.raises(MemoryUnavailable,match='first_differing_word'):inspect_installed(m)


@pytest.mark.skipif(not PAIRS,reason='original private RAM unavailable')
def test_real_c2_layout_keeps_native_core_intro_detection():
    b=Overlay(PAIRS[0]);captured(b);m=SonicMemory(b)
    m.verify_revision()
    s=NativeHooks().snapshot(m)
    assert s.scene=='gameplay' and s.new_game_verified and s.pickup_verified
