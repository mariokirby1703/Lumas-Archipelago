from types import SimpleNamespace
from ..oneups import ONEUPS
from ..Locations import LOCATION_TABLE,enabled
from ..Options import OneUpSanity

def test_asset_catalog_and_stable_ids():
    assert len(ONEUPS)==31
    assert len({row['code'] for row in ONEUPS.values()})==31
    assert len({d.code for d in LOCATION_TABLE.values()})==len(LOCATION_TABLE)
    absent={'stg540','stg560','stg630','stg650','stg620'}
    assert not absent & {r['mission_id'] for r in ONEUPS.values()}
    assert all(r['layer']=='00' and r['instance']==0 for r in ONEUPS.values())
    assert sum(d.kind=='ring' for d in LOCATION_TABLE.values())==180

def test_oneup_toggle_defaults_off():
    assert OneUpSanity.default==0
    rows=[d for d in LOCATION_TABLE.values() if d.kind=='one_up']
    assert len(rows)==31
    assert not any(enabled(d,SimpleNamespace(one_up_sanity=0)) for d in rows)
    assert all(enabled(d,SimpleNamespace(one_up_sanity=1)) for d in rows)


import pytest
@pytest.mark.parametrize('matching',[True,False])
@pytest.mark.parametrize('initial',[0,1,0x40000000])
def test_native_event_latch_preserves_prior_pickups(matching,initial):
    from ..client.oneup_hook import payload,ORIGINAL
    words,off=payload();base=0x80002000;actor=0x90010000
    regs=[0]*32;regs[30]=actor;mem={base+off:actor,base+off+4:123 if matching else 124,
        base+off+12:initial,base+off+16:2,actor+12:123,actor+0xbc:0}
    pc=0;lr=0;cmp=0
    for _ in range(100):
        w=words[pc];pc+=1
        if w==ORIGINAL:break
        op=w>>26;rt=w>>21&31;ra=w>>16&31;rb=w>>11&31;imm=w&65535
        if op==18:
            delta=w&0x3fffffc
            if w&1:lr=base+pc*4
            pc+=delta//4-1
        elif w==0x7d8802a6:regs[12]=lr
        elif op==32:regs[rt]=mem.get(regs[ra]+imm,0)
        elif op==36:mem[regs[ra]+imm]=regs[rt]
        elif op==31 and ((w>>1)&1023)==0:cmp=regs[ra]-regs[rb]
        elif op==31 and ((w>>1)&1023)==444:regs[ra]=regs[rt]|regs[rb]
        elif op==16:
            if cmp!=0:pc+=(imm if imm<32768 else imm-65536)//4-1
        else:raise AssertionError(hex(w))
    assert mem[base+off+12]==(initial|2 if matching else initial)
