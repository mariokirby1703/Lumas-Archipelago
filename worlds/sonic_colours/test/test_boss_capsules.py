import struct
import pytest
from ..client import boss_capsules as b, native_events as n
from ..client.native_dol import plan
from ..client import capsule_refresh,progression_hook
from .test_native_events import Machine


def machine(monkeypatch,colour,mask=0,white=0,index=1):
    hooks=plan()[3]
    m=Machine('death');m.kind='boss_drop'
    monkeypatch.setitem(n.HOOKS,'boss_drop',(b.HOOK,b.ORIGINAL))
    for address,old,new in b.planned_patches():m.b.put(address,new)
    hooks=plan()[3]
    capsule=next(h for h in hooks if h['hook']==capsule_refresh.HOOK)
    story=next(h for h in hooks if h['hook']==progression_hook.HOOK)
    cap=capsule['target']+capsule_refresh.data_offset(capsule_refresh.payload_words(
        compact_abi=True,epilogue_abi=True,cache_permissions=True))
    prog=story['target']+progression_hook.payload()[1]
    actor=0x900c0000;owner=0x900d0000
    m.r[3]=actor;m.r[4]=0x900e0000
    m.put(actor,b.VTABLE);m.put(actor+0x60,colour);m.b.put(actor+0x74,b'\0')
    m.put(cap,owner);m.put(cap+4,index);m.put(cap+8,white);m.b.put(owner,bytes([index]))
    m.put(prog,owner+0x24+index*0x19608);m.put(prog+8,mask)
    m.b.put(b.BLOCKED,bytes.fromhex('4e800020'))
    original_get=m.get;m.denied=False
    def get(address):
        if address==b.BLOCKED:m.denied=True
        return original_get(address)
    m.get=get;m.before=m.r[:]
    return m,cap,prog


@pytest.mark.parametrize('colour',range(7))
@pytest.mark.parametrize('owned',[False,True])
def test_real_scattered_ppc_gate_checks_exact_colour(monkeypatch,colour,owned):
    m,_,_=machine(monkeypatch,colour,(1<<colour) if owned else (127^(1<<colour)))
    m.run();assert m.denied is not owned
    assert m.r[3:5]==m.before[3:5] and m.r[7:12]==m.before[7:12]
    assert m.r[13:]==m.before[13:]
    assert m.lr==0x80001234 and m.ctr==0x80005678 and m.f==m.before_f
    assert m.read(m.r[3]+0x74,1)==b'\0' # never consumes or mutates the drop


@pytest.mark.parametrize('permission',[0,1,2,3])
def test_white_requires_white_bit_not_random_capsules(monkeypatch,permission):
    m,_,_=machine(monkeypatch,-1,127,permission);m.run()
    assert m.denied == (not bool(permission&1))


@pytest.mark.parametrize('failure',['unconfigured','wrong_save','wrong_story_owner','unknown_colour','wrong_actor'])
def test_drop_gate_rejects_missing_or_wrong_ownership(monkeypatch,failure):
    m,cap,prog=machine(monkeypatch,1,127,1)
    if failure=='unconfigured':m.put(cap,0)
    elif failure=='wrong_save':m.put(cap+4,2)
    elif failure=='wrong_story_owner':m.put(prog,0)
    elif failure=='unknown_colour':m.put(m.r[3]+0x60,7)
    else:m.put(m.r[3],0x80761534)
    m.run();assert m.denied


def test_drop_unlock_without_recreating_actor(monkeypatch):
    m,cap,prog=machine(monkeypatch,1,0,0);m.run();assert m.denied
    m.put(prog+8,2);m.denied=False;m.run();assert not m.denied


@pytest.mark.parametrize('colour',[-1,0,1,2,3,4,5,6])
@pytest.mark.parametrize('owned',[False,True])
def test_spawn_selects_native_ghost_mode_without_changing_colour(monkeypatch,colour,owned):
    m,_,_=machine(monkeypatch,colour,127 if owned else 0,int(owned))
    m.kind='boss_create';monkeypatch.setitem(n.HOOKS,m.kind,(b.CREATE_HOOK,b.CREATE_ORIGINAL))
    m.r[30]=m.r[3];m.r[3]=colour&0xffffffff
    before=m.r[:];m.run()
    assert m.r[5]==int(owned) and m.r[3]==before[3] and m.r[30:]==before[30:]
    assert m.lr==0x80001234 and m.f==m.before_f


def visual_machine(monkeypatch,colour,owned,old_mode,allocation=True):
    m,cap,prog=machine(monkeypatch,colour,127 if owned else 0,int(owned))
    m.kind='boss_update';monkeypatch.setitem(n.HOOKS,m.kind,(b.UPDATE_HOOK,b.UPDATE_ORIGINAL))
    actor=m.r[3];model=0x90140000;new_model=0x90150000
    m.r[31]=actor;m.put(actor+0x68,model);m.put(actor+0x6c,0x90160000)
    m.put(actor+0x70,0x90170000);m.put(actor+0x64,0x3f800000)
    m.put(model,b.MODEL_VTABLE);m.put(model+8,actor);m.put(model+0x88,old_mode)
    def call(target):
        # Native callees may spill all eight argument registers in the
        # caller's outgoing parameter area. Model args must live above it.
        assert m.r[1]%16==0
        for offset in range(8,0x28,4):m.put(m.r[1]+offset,0xabad1dea)
        if target==0x801a3920:
            assert m.r[4]==actor+0x44 and m.r[5]==actor+0x50
            m.b.put(m.r[3],bytes(48))
        elif target==0x80077b04:
            assert m.r[3:5]==[0xc8,0xff]
            return new_model if allocation else 0
        elif target==0x802d5ad0:
            assert m.r[3]==new_model and m.r[4]==actor
            assert m.get(m.r[5])==colour&0xffffffff
            assert m.get(m.r[5]+4)==int(owned) and m.get(m.r[5]+8)==3
            assert m.f[1:3]==[1.,1.]
            m.put(new_model,b.MODEL_VTABLE);m.put(new_model+8,actor)
            m.put(new_model+0x88,int(owned));return new_model
        elif target==0x800d3e54:
            assert m.r[3]==actor+0x68 and m.r[4]==new_model
            m.put(actor+0x68,new_model)
        else:raise AssertionError(hex(target))
    m.native_call=call;m.before=m.r[:]
    return m,actor,model,new_model


@pytest.mark.parametrize('colour',[-1,1])
@pytest.mark.parametrize('owned',[False,True])
def test_visual_transition_uses_native_model_lifetime_and_preserves_drop(monkeypatch,colour,owned):
    m,actor,old,new=visual_machine(monkeypatch,colour,owned,int(not owned))
    m.run()
    assert m.call_targets==[0x801a3920,0x80077b04,0x802d5ad0,0x800d3e54]
    assert m.get(actor+0x68)==new and m.get(new+0x88)==int(owned)
    assert m.get(actor+0x6c)==0x90160000 and m.get(actor+0x70)==0x90170000
    assert m.read(actor+0x74,1)==b'\0' and m.get(actor+0x60)==colour&0xffffffff
    assert m.r[1]==m.before[1] and m.r[28:]==m.before[28:] and m.lr==0x80001234
    m.call_targets.clear();m.run();assert m.call_targets==[] # stable mode never reallocates


@pytest.mark.parametrize('case',['already_correct','consumed','bad_model','wrong_owner','bad_mode','allocation_failed','bad_actor','unknown_colour'])
def test_visual_refresh_defers_without_destroying_existing_model(monkeypatch,case):
    m,actor,old,new=visual_machine(monkeypatch,1,False,1,allocation=case!='allocation_failed')
    if case=='already_correct':m.put(old+0x88,0)
    elif case=='consumed':m.b.put(actor+0x74,b'\1')
    elif case=='bad_model':m.put(old,0)
    elif case=='wrong_owner':m.put(old+8,0)
    elif case=='bad_mode':m.put(old+0x88,2)
    elif case=='bad_actor':m.put(actor,0)
    elif case=='unknown_colour':m.put(actor+0x60,7)
    m.run()
    assert m.get(actor+0x68)==old
    assert 0x800d3e54 not in m.call_targets
    assert m.r[1]==m.before[1] and m.r[28:]==m.before[28:]


@pytest.mark.parametrize('index',[0,1,2,3])
def test_colour_unlock_uses_actual_selected_save_flag_layout(monkeypatch,index):
    from ..client.memory import SonicMemory
    m,cap,prog=machine(monkeypatch,1,2,index=index)
    memory=SonicMemory(m.b)
    container=m.get(cap)
    monkeypatch.setattr(memory,'resolve_save_container',lambda:(0x900f0000,container))
    native_flags=memory.resolve_flags_ptr(allow_working=True)[-1]
    assert m.get(prog)==native_flags
    assert native_flags!=container
    m.run();assert not m.denied
    # Reproduce the previous erroneous equality: a raw container pointer
    # cannot serve as the progression flag owner, even in the first slot.
    m.put(prog,container);m.run();assert m.denied


@pytest.mark.parametrize('index',[0,1,2,3])
def test_another_slots_flags_never_unlock_colour(monkeypatch,index):
    m,cap,prog=machine(monkeypatch,1,2,index=index)
    m.put(prog,m.get(cap)+0x24+((index+1)%4)*0x19608)
    m.run();assert m.denied
