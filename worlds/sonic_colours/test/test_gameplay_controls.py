"""Execute emitted PPC gates; native PAL callers and private dump tests are separate."""
import struct
import pytest
from ..client.gameplay_controls import payload, HOOKS, installed
from ..client.memory import SonicMemory, MemoryUnavailable
from ..client.runtime import inventory
from ..Items import ITEM_TABLE, GAME_LAND_SPEED
from .test_memory import FakeBackend
from .test_pickup_integration import Overlay
from .test_native_originals import PAIRS
from . import generate


def run(kind, selected=4, maximum=0, locked=1, colour=0, profile=1, expected_profile=1, mode=0):
    words, data = payload(kind); base=0x80002000
    regs=[0]*32;regs[1]=0x90001000;regs[3]=0x90002000;regs[4]=colour if kind=='boost' else selected
    regs[0]=selected;regs[27]=0x90003000;regs[29]=0x90004000
    regs[30]=0x90006000
    mem={0x90005000:profile,regs[3]+4:selected,regs[3]+0x2c:1,regs[29]+0x114:0}
    mem.update({regs[3]+8:float(selected),regs[30]+0x8c:0x90007000,0x90007024:mode})
    for i,v in enumerate((0x90005000,expected_profile,maximum,regs[3],locked,0.)):mem[base+data+i*4]=v
    before=regs[:];lr,cr=0x80010000,0x12345678;original=(lr,cr);cmp=0;pc=0;f1=5.0
    for _ in range(300):
        w=words[pc];pc+=1
        if not w:break
        op=w>>26;rt=w>>21&31;ra=w>>16&31;u=w&0xffff;imm=u if u<0x8000 else u-0x10000
        if op==14:regs[rt]=((regs[ra] if ra else 0)+imm)&0xffffffff
        elif op in (32,34):regs[rt]=mem.get((regs[ra]+imm)&0xffffffff,0)
        elif op==48:f1=mem[regs[ra]+imm]
        elif w==0xec20082a:f1=float(selected)+f1
        elif op in (36,37):
            addr=(regs[ra]+imm)&0xffffffff;mem[addr]=regs[rt]
            if op==37:regs[ra]=addr
        elif op in (46,47):
            addr=regs[ra]+imm
            for r in range(rt,32):
                if op==47:mem[addr+(r-rt)*4]=regs[r]
                else:regs[r]=mem[addr+(r-rt)*4]
        elif op==11:cmp=(regs[ra]>imm)-(regs[ra]<imm)
        elif op==16:
            take={0x41820000:cmp==0,0x40820000:cmp!=0,0x40810000:cmp<=0}[w&0xffff0000]
            if take:pc=pc-1+imm//4
        elif op==18:
            delta=w&0x3fffffc
            if delta&0x2000000:delta-=0x4000000
            if w&1:lr=base+pc*4
            pc=pc-1+delta//4
        elif w==0x7c0802a6:regs[0]=lr
        elif w==0x7c000026:regs[0]=cr
        elif w==0x7d8802a6:regs[12]=lr
        elif w==0x7ccff120:cr=regs[6]
        elif w==0x7cc803a6:lr=regs[6]
        elif w==0x7c0ff120:cr=regs[0]
        elif w==0x7c0803a6:lr=regs[0]
        elif op==31 and w&0x7ff==0x378:regs[ra]=regs[rt]|regs[w>>11&31]
        elif op==31 and w&0x7ff==0:
            lhs=regs[ra];rhs=regs[w>>11&31];cmp=(lhs>rhs)-(lhs<rhs)
        elif w==0x60000000:pass
        else:raise AssertionError(hex(w))
    else:raise AssertionError('thunk loop')
    outputs={3} if kind in ('boost','speed_get') else {0} if kind=='speed_ui' else set()
    assert (lr,cr)==original
    assert all(regs[i]==before[i] for i in range(32) if i not in outputs)
    return f1 if kind in ('boost_use','boost_query','boost_add') else regs[3] if kind in ('boost','speed_get') else mem[before[3]+4] if kind=='speed_set' else mem[before[27]+0x118]


@pytest.mark.parametrize('kind',['speed_get','speed_set','speed_ui'])
@pytest.mark.parametrize('maximum',range(5))
@pytest.mark.parametrize('selected',range(5))
def test_native_ui_setter_and_simulation_all_five_tiers(kind,maximum,selected):
    assert run(kind,selected,maximum)==min(selected,maximum)
    assert run(kind,selected,maximum,profile=2)==selected


def test_white_boost_gate_preserves_other_colour_and_unrelated_profile():
    assert run('boost',locked=1)==1
    assert run('boost',locked=0)==1
    assert run('boost',locked=1,profile=2)==1
    # Other Wisp queries read their original native availability byte.
    assert run('boost',locked=1,colour=1)==1


def test_ordinary_boost_query_changes_result_without_writing_gauge():
    assert run('boost_use',selected=35,locked=1)==0.
    assert run('boost_use',selected=35,locked=0)==35.
    assert run('boost_use',selected=35,locked=1,profile=2)==35.
    assert run('boost_use',selected=35,locked=1,mode=1)==35.


def install(b, kind, target):
    hook,_=HOOKS[kind];words,offset=payload(kind)
    words[-1]=0x48000000 | (hook+4-(target+len(words)*4-4))&0x3fffffc
    b.write_bytes(target,struct.pack('>'+'I'*len(words),*words))
    b.write_bytes(hook,(0x48000000 | (target-hook)&0x3fffffc).to_bytes(4,'big'))
    return target+offset


@pytest.mark.skipif(not PAIRS,reason='original PAL dumps unavailable')
def test_all_real_pal_control_sites_normalize_only_exact_known_thunks():
    b=Overlay(PAIRS[0]);m=SonicMemory(b)
    for i,kind in enumerate(HOOKS):
        data=install(b,kind,0x80002000+i*0x240)
        assert installed(m,kind)==data
    m.verify_revision()
    b.write_bytes(0x80002000+20,bytes(4))
    with pytest.raises(MemoryUnavailable,match='unknown_revision'):m.verify_revision()


def test_progressive_speed_pool_has_four_useful_items_without_new_option():
    for value in ({},{'game_land_checks':False,'chaos_emerald_checks':False}):
        m=generate(value,fill=True);w=m.worlds[1]
        speeds=[i for i in m.itempool if i.name==GAME_LAND_SPEED]
        assert len(speeds)==(4 if w.game_land_speed_items else 0)
        assert all(i.useful and not i.advancement for i in speeds)
        assert m.can_beat_game()


@pytest.mark.parametrize('kind', ['boost_use', 'boost_query'])
def test_white_lock_gates_ordinary_queries_only(kind):
    assert run(kind, selected=42, locked=1) == 0.
    assert run(kind, selected=42, locked=0) == 42.
    assert run(kind, selected=42, locked=1, profile=2) == 42.


def test_white_pickup_and_script_grants_preserve_existing_gauge_when_locked():
    assert run('boost_add', selected=35, locked=1) == 35.
    assert run('boost_add', selected=35, locked=0) == 40.
    assert run('boost_add', selected=35, locked=1, profile=2) == 40.


@pytest.mark.parametrize('kind', ['boost', 'boost_use', 'speed_get', 'speed_set', 'speed_ui'])
def test_known_previous_gecko_payload_is_still_accepted(kind):
    from ..world_constants import load_data
    b = FakeBackend(); m = SonicMemory(b)
    legacy = load_data('gameplay_hook_legacy.json')[kind]
    target = 0x80002000; hook, _ = HOOKS[kind]
    words = legacy['words'][:]
    words[-1] = 0x48000000 | ((hook+4-(target+len(words)*4-4)) & 0x3fffffc)
    b.write_bytes(target, struct.pack('>'+'I'*len(words), *words))
    b.write_bytes(hook, (0x48000000 | ((target-hook) & 0x3fffffc)).to_bytes(4, 'big'))
    assert installed(m, kind) == target + legacy['offset']
    b.write_bytes(target+20, bytes(4))
    with pytest.raises(MemoryUnavailable, match='unknown_revision'):
        installed(m, kind)


@pytest.mark.parametrize('kind', list(HOOKS))
def test_pre_compaction_payload_is_still_accepted(kind):
    b = FakeBackend(); m = SonicMemory(b); target=0x80002000
    hook,_=HOOKS[kind]; words,offset=payload(kind,compact=False)
    words[-1]=0x48000000|((hook+4-(target+len(words)*4-4))&0x3fffffc)
    b.put(target,struct.pack('>'+'I'*len(words),*words))
    b.put(hook,(0x48000000|((target-hook)&0x3fffffc)).to_bytes(4,'big'))
    assert installed(m,kind)==target+offset


@pytest.mark.parametrize('historical', [False, True])
def test_host_neutralizes_coloured_gate_without_disabling_white_lock(historical):
    from types import SimpleNamespace
    from ..client.gameplay_controls import configure
    from ..world_constants import load_data
    b = FakeBackend(); m = SonicMemory(b, write_guard=lambda *args: 'test owned control')
    for i, kind in enumerate(HOOKS):
        target = 0x80002000 + i*0x240
        if historical and kind in load_data('gameplay_hook_legacy.json'):
            legacy = load_data('gameplay_hook_legacy.json')[kind]
            hook, _ = HOOKS[kind]; words = legacy['words'][:]
            words[-1] = 0x48000000 | ((hook+4-(target+len(words)*4-4)) & 0x3fffffc)
            b.write_bytes(target, struct.pack('>'+'I'*len(words), *words))
            b.write_bytes(hook, (0x48000000 | ((target-hook) & 0x3fffffc)).to_bytes(4, 'big'))
        else:
            install(b, kind, target)
    m.resolve_flags_ptr = lambda **kw: (0x90001000, 0x90002000, 1, 0x90003000)
    configure(m, SimpleNamespace(boost_address=0x90004008), inventory([]),
              {'options': {'boost_lock': 1}, 'game_land_speed_items': True})
    assert m.read_u32(installed(m, 'boost')+16) == 0
    for kind in ('boost_use', 'boost_query', 'boost_add'):
        assert m.read_u32(installed(m, kind)+16) == 1


def test_temporary_boost_allows_use_but_denies_vanilla_add():
    assert run('boost_use', selected=25, locked=2) == 25
    assert run('boost_query', selected=25, locked=2) == 25
    assert run('boost_add', selected=25, locked=2) == 25
    assert run('boost_use', selected=0, locked=2) == 0
    assert run('boost_add', selected=25, locked=0) == 30
