import pytest
from ..client import memory as module, versions
from ..client.memory import SonicMemory, MemoryUnavailable
from ..client.native_dol import SIGNATURE


@pytest.fixture
def rig(monkeypatch):
    now=[1.0];proofs=[]
    class Backend:
        signature=b'a'*64
        def read_bytes(self,address,size):
            return self.signature if address==SIGNATURE else b'SNCP8P\0\0'[:size]
    backend=Backend();m=SonicMemory(backend)
    def prove(memory):
        proofs.append(now[0]);memory.native_patch={'verified':True}
        return 'verified'
    monkeypatch.setattr(versions,'verify_revision',prove)
    monkeypatch.setattr(module.time,'monotonic',lambda:now[0])
    return m,backend,now,proofs


def test_only_native_controls_share_a_bounded_synchronous_proof(rig):
    m,backend,now,proofs=rig
    with m.control_scope():
        m.verify_for_write('movement_controls')
        m.verify_for_write('capsule_controls')
        assert len(proofs)==1
        now[0]+=.051
        m.verify_for_write('oxygen_controls')
        assert len(proofs)==2
        m.verify_for_write('permission_bits')
        m.verify_for_write('stats')
        assert len(proofs)==4
    assert m._control_proof is None
    m.verify_for_write('movement_controls')
    assert len(proofs)==5


def test_reset_or_signature_change_requires_full_proof(rig):
    m,backend,now,proofs=rig
    with m.control_scope():
        m.verify_for_write('movement_controls')
        backend.signature=b'b'*64
        m.verify_for_write('capsule_controls')
        assert len(proofs)==2


def test_no_proof_survives_exception_or_next_async_step(rig):
    m,backend,now,proofs=rig
    with pytest.raises(RuntimeError):
        with m.control_scope():
            m.verify_for_write('movement_controls')
            raise RuntimeError('scene exit')
    assert m._control_proof is None
    with m.control_scope():m.verify_for_write('movement_controls')
    assert len(proofs)==2


def test_nested_batches_rejected_and_failed_verification_not_cached(rig,monkeypatch):
    m,backend,now,proofs=rig
    def fail(memory):raise MemoryUnavailable('modified executable')
    with m.control_scope():
        m.verify_for_write('movement_controls')
        with pytest.raises(MemoryUnavailable,match='nested'):
            with m.control_scope():pass
        now[0]+=.051
        monkeypatch.setattr(versions,'verify_revision',fail)
        with pytest.raises(MemoryUnavailable,match='modified'):m.verify_for_write('movement_controls')
        assert m._control_proof is None


def test_legacy_images_do_not_share_full_executable_checks(rig,monkeypatch):
    m,backend,now,proofs=rig
    monkeypatch.setattr(versions,'verify_revision',lambda m:proofs.append('legacy'))
    with m.control_scope():
        m.verify_for_write('movement_controls');m.verify_for_write('movement_controls')
    assert proofs==['legacy','legacy']
