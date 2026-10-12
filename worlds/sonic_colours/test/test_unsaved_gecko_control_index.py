"""Regression: PAL unsaved intro 0xFF is a *transient hook control*, not a save slot."""
import struct
import pytest
from ..client import capsule_refresh, gameplay_controls
from ..client.memory import SonicMemory, MemoryUnavailable
from ..client.versions import VERSION
from .test_memory import FakeBackend

MGR = 0x90001000
CONT = 0x90002000


def setup():
    backend = FakeBackend()
    mem = SonicMemory(backend)
    backend.put(VERSION['manager_global_candidate'], MGR.to_bytes(4,'big'))
    backend.put(MGR + 0x30, CONT.to_bytes(4,'big'))
    backend.put(CONT, b'\xff')
    return mem, backend


def patch_c2(mem, backend, hook, original, words, data_offset, fields, target):
    code = words.copy()
    code[-1] = 0x48000000 | ((hook + 4 - (target + len(code)*4 - 4)) & 0x03FFFFFC)
    backend.put(target, struct.pack('>'+'I'*len(code),*code))
    backend.put(hook,(0x48000000 | ((target-hook)&0x03FFFFFC)).to_bytes(4,'big'))
    address = target + data_offset
    backend.put(address,struct.pack('>'+'I'*len(fields),*fields))
    return address


def test_capsule_live_unsaved_owner_preserves_revision_and_allows_menu_transition():
    mem,backend=setup()
    words=capsule_refresh.payload_words()
    addr=patch_c2(mem,backend,capsule_refresh.HOOK,capsule_refresh.ORIGINAL, words,
        capsule_refresh.data_offset(words), (CONT,0xff,0), 0x80002000)
    assert capsule_refresh.installed_data(mem)==addr
    assert capsule_refresh.installed(mem)
    backend.put(CONT,b'\x00')  # first save slot now selected; stale 0xFF is inert
    assert capsule_refresh.installed_data(mem)==addr
    backend.put(addr+4,(0).to_bytes(4,'big'))
    assert capsule_refresh.installed_data(mem)==addr


def test_capsule_rejects_corrupt_or_rogue_unselected_control():
    mem,backend=setup()
    words=capsule_refresh.payload_words()
    addr=patch_c2(mem,backend,capsule_refresh.HOOK,capsule_refresh.ORIGINAL, words,
        capsule_refresh.data_offset(words), (CONT,0xff,0), 0x80002000)
    backend.put(addr+4,(254).to_bytes(4,'big'))
    # Stale transient control is inert (native FF != mailbox FE) but is not a
    # corrupt executable; client must be able to rewrite it.
    assert capsule_refresh.installed_data(mem)==addr
    backend.put(addr+4,(255).to_bytes(4,'big'))
    backend.put(addr,(0x90003000).to_bytes(4,'big'))
    with pytest.raises(MemoryUnavailable,match='invalid White capsule control data'):
        capsule_refresh.installed_data(mem)
    backend.put(addr,(0).to_bytes(4,'big'))  # writer's disarmed intermediate state
    assert capsule_refresh.installed_data(mem)==addr
    backend.put(addr+8,(4).to_bytes(4,'big'))
    with pytest.raises(MemoryUnavailable,match='invalid White capsule control data'):
        capsule_refresh.installed_data(mem)


@pytest.mark.parametrize('kind', ['boost_use','boost_query','boost_add','speed_get','speed_set','speed_ui'])
def test_gameplay_c2_accepts_sentinel_but_rejects_other_bad_indexes(kind):
    mem,backend=setup()
    hook,original=gameplay_controls.HOOKS[kind]
    words,offset=gameplay_controls.payload(kind)
    # Speed hooks have three control words; Boost hooks have five.
    size = 3 if kind.startswith('speed') else 5
    fields=(CONT,255,4,0,1)[:size]
    addr=patch_c2(mem,backend,hook,original,words,offset,fields,0x80004000)
    assert gameplay_controls.installed(mem,kind)==addr
    backend.put(addr+4,(254).to_bytes(4,'big'))
    assert gameplay_controls.installed(mem,kind)==addr
    backend.put(addr+4,(255).to_bytes(4,'big'))
    backend.put(addr,(0x90003000).to_bytes(4,'big'))
    with pytest.raises(MemoryUnavailable,match='invalid native gameplay control data'):
        gameplay_controls.installed(mem,kind)
    backend.put(addr,(CONT).to_bytes(4,'big'))
    backend.put(CONT,b'\x01')
    assert gameplay_controls.installed(mem,kind)==addr

@pytest.mark.parametrize('native_index',[4,5,254,255])
def test_capsule_gecko_accepts_real_native_presave_index_and_stale_after_selection(native_index):
    mem,backend=setup()
    backend.put(CONT,bytes([native_index]))
    words=capsule_refresh.payload_words()
    addr=patch_c2(mem,backend,capsule_refresh.HOOK,capsule_refresh.ORIGINAL,words,
        capsule_refresh.data_offset(words),(CONT,native_index,0),0x80002000)
    assert capsule_refresh.installed_data(mem)==addr
    backend.put(CONT,b'\x01')
    assert capsule_refresh.installed_data(mem)==addr
    # Disarmed index mailbox is inert and must remain writable.
    backend.put(addr,(0).to_bytes(4,'big'))
    assert capsule_refresh.installed_data(mem)==addr

@pytest.mark.parametrize('native_index',[4,254])
@pytest.mark.parametrize('kind',['boost_use','boost_query','boost_add','speed_get','speed_set','speed_ui'])
def test_gameplay_gecko_accepts_native_presave_index(native_index,kind):
    mem,backend=setup()
    backend.put(CONT,bytes([native_index]))
    hook,original=gameplay_controls.HOOKS[kind]
    words,offset=gameplay_controls.payload(kind)
    size=3 if kind.startswith('speed') else 5
    addr=patch_c2(mem,backend,hook,original,words,offset,
        (CONT,native_index,4,0,1)[:size],0x80004000)
    assert gameplay_controls.installed(mem,kind)==addr
    backend.put(CONT,b'\x01')
    assert gameplay_controls.installed(mem,kind)==addr


def test_reject_live_unsaved_mismatched_index_or_container():
    mem,backend=setup()
    backend.put(CONT,b'\x04')
    assert capsule_refresh.valid_native_control_index(mem,CONT,254)  # inert stale byte
    assert not capsule_refresh.valid_native_control_index(mem,CONT,256)
    assert not capsule_refresh.valid_native_control_index(mem,CONT+4,4)
    assert capsule_refresh.valid_native_control_index(mem,CONT,4)

@pytest.mark.parametrize('native_index',[4,254,255])
def test_white_capsule_configure_disables_white_before_save_selected(native_index,monkeypatch):
    """A fake no-slot PAL intro actually publishes the three control words."""
    from collections import defaultdict
    from types import SimpleNamespace
    from .test_new_game_no_slot import initialize, ProfileMemory
    from ..client import capsule_refresh
    from ..client.state import live_control_profile
    journal,native,guard,snaps=initialize(monkeypatch)
    import copy
    from dataclasses import replace
    trace=copy.deepcopy(snaps[-1].evidence['save_chain_trace'])
    trace['steps'][0]['raw']=f'0x{native_index:02X}'
    snapshot=replace(snaps[-1],evidence={**snaps[-1].evidence,'save_chain_trace':trace})
    mem,backend=setup()
    backend.put(CONT,bytes([native_index]))
    words=capsule_refresh.payload_words()
    addr=patch_c2(mem,backend,capsule_refresh.HOOK,capsule_refresh.ORIGINAL,words,
        capsule_refresh.data_offset(words),(0,0,0),0x80002000)
    mem.write_guard=SimpleNamespace(guard=guard)
    # All writes must keep the owner/index pair authenticated. A standalone
    # test policy checks the index, exact mailbox address, and C2 readback.
    def authorize(op,address,size):
        assert op=='capsule_controls' and size==4
        assert address in (addr,addr+4,addr+8)
        assert capsule_refresh.installed_data(mem)==addr
        assert live_control_profile(mem,snapshot,guard)[2]==native_index
        return ('valid-unsaved-control',addr,native_index)
    # Expose the guard through the production attribute expected by configure.
    mem.write_guard=SimpleNamespace(guard=guard)
    # The policy is callable and carries the guard for configure().
    class Policy:
        def __init__(self):self.guard=guard
        def __call__(self,*args):return authorize(*args)
    mem.write_guard=Policy()
    allowed=defaultdict(int)
    status=capsule_refresh.configure(mem,snapshot,{'counts':allowed},
                                      {'options':{'boost_lock':True}})
    assert status['available'] and not status['white_allowed']
    assert struct.unpack('>3I',mem.read_bytes(addr,12))==(CONT,native_index,0)
