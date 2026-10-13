import struct
import pytest
from ..client.memory import SonicMemory,MemoryUnavailable
from ..client.native_read import read_result
from .test_memory import FakeBackend


@pytest.mark.parametrize('change',['animation','grade','owner'])
def test_final_result_coherence_ignores_only_unrelated_animation(change):
    stage,ui=0x90010000,0x90020000
    class Backend(FakeBackend):
        scans=0
        def read_bytes(self,a,n):
            if (a,n)==(ui+0xdc,0x50):
                self.scans+=1
                if self.scans==2:
                    if change=='animation':self.put(ui+0xe4,struct.pack('>f',.75))
                    if change=='grade':self.put(ui+0x124,(3).to_bytes(4,'big'))
                    if change=='owner':self.put(stage+0x9c,(ui+0x200).to_bytes(4,'big'))
            return super().read_bytes(a,n)
    b=Backend();m=SonicMemory(b)
    for a,v in ((stage+0x9c,ui),(ui,0x8076CAE4),(ui+0xdc,7),
                (ui+0x114,12345),(ui+0x120,12345),(ui+0x124,2)):
        b.put(a,v.to_bytes(4,'big'))
    b.put(ui+0xf8,struct.pack('>f',30.))
    if change=='animation':
        result=read_result(m,stage,'stg110')
        assert result['final'] and result['grade']==2 and result['score']==12345
    else:
        with pytest.raises(MemoryUnavailable,match='result_context_changed'):read_result(m,stage,'stg110')
