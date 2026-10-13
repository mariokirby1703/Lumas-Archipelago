from types import SimpleNamespace
import pytest
from ..client.memory import DMEBackend

@pytest.mark.parametrize('header,text,recover',[(b'SNCP8P',bytes(4),True),(bytes(6),bytes(4),True),(b'SNCE8P',bytes(4),False),(b'SNCP8P',bytes.fromhex('60000000'),False)])
def test_reattach_only_repeated_empty_boot_mapping(monkeypatch,header,text,recover):
    from ..client import memory as module
    monkeypatch.setattr(module.time,'monotonic',lambda:100.)
    class Engine:
        unhooks=0
        def is_hooked(self):return True
        def get_status(self):return SimpleNamespace(name='hooked')
        def read_bytes(self,a,n):return header if a==0x80000000 else text
        def un_hook(self):self.unhooks+=1
    e=Engine();b=DMEBackend(e);b.instance_info=lambda:{'process_candidates':[{'pid':1}]}
    assert not b.recover_empty_text_mapping('unknown_revision: text mismatch')
    assert not b.recover_empty_text_mapping('unknown_revision: text mismatch')
    assert b.recover_empty_text_mapping('unknown_revision: text mismatch')==recover
    assert e.unhooks==int(recover)
    for _ in range(5):assert not b.recover_empty_text_mapping('unknown_revision: text mismatch')
    assert e.unhooks==int(recover)
    assert not b.recover_empty_text_mapping('WRITE_BLOCKED: save identity')
