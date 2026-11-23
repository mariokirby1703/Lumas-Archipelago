import os
import faulthandler
import struct

import pytest

from ..client.native_dol import plan, Dol, patch_dol
from ..client import oneup_hook, oneup_capture, progression_hook
from ..oneups import ONEUPS
from ..world_constants import STAGES, load_data
from ..client.runtime import detect_checks
from ..Locations import LOCATION_TABLE
from .test_runtime import snapshot
from .test_logic_v3 import State, world, MANIFEST
from .. import logic


def cpu_for_plan(fps=False):
    u = pytest.importorskip('unicorn')
    cpu = u.Uc(u.UC_ARCH_PPC, u.UC_MODE_32 | u.UC_MODE_BIG_ENDIAN)
    enabled = faulthandler.is_enabled()
    try:
        faulthandler.disable(); cpu.mem_map(0x80000000, 0x1800000)
    finally:
        if enabled: faulthandler.enable()
    selected = plan(include_sixty_fps=fps)
    for address, _, raw in selected[0]: cpu.mem_write(address, raw)
    from ..client.native_dol import ARENA
    cpu.mem_write(ARENA, selected[1])
    return cpu, selected


def word(cpu, address, value): cpu.mem_write(address, struct.pack('>I', value))
def read(cpu, address): return int.from_bytes(cpu.mem_read(address, 4), 'big')


@pytest.mark.parametrize('allowed', [False, True])
def test_native_super_permission_ignores_completed_game_land_and_old_save_bit(allowed):
    r = pytest.importorskip('unicorn.ppc_const')
    cpu, selected = cpu_for_plan()
    hook = next(h for h in selected[3] if h['hook'] == progression_hook.HOOK)
    control = hook['target'] + progression_hook.payload()[1]
    word(cpu, control + 8, 0x80 if allowed else 0x7f)
    # Every saved Game Land flag and the old native unlock can be set.
    cpu.mem_write(0x81010000, b'\xff' * 256)
    word(cpu, 0x81000000, 0x81010000)
    cpu.reg_write(r.UC_PPC_REG_3, 0x81000000)
    cpu.reg_write(r.UC_PPC_REG_4, 7)
    cpu.reg_write(r.UC_PPC_REG_LR, 0x80010000)
    cpu.emu_start(0x8015ED0C, 0x80010000, count=300)
    assert cpu.reg_read(r.UC_PPC_REG_PC) == 0x80010000
    assert cpu.reg_read(r.UC_PPC_REG_3) == int(allowed)


@pytest.mark.parametrize('allowed', [False, True])
def test_super_transformation_plugin_cannot_bypass_ap_permission(allowed):
    r = pytest.importorskip('unicorn.ppc_const')
    cpu, selected = cpu_for_plan()
    hook=next(h for h in selected[3] if h['hook']==progression_hook.HOOK)
    control=hook['target']+progression_hook.payload()[1]
    word(cpu,control+8,0x80 if allowed else 0x7f)
    cpu.reg_write(r.UC_PPC_REG_1,0x81700000)
    cpu.reg_write(r.UC_PPC_REG_3,0x81000000)
    cpu.reg_write(r.UC_PPC_REG_4,0x81001000)
    cpu.reg_write(r.UC_PPC_REG_LR,0x80010000)
    stop=0x803125CC if allowed else 0x80010000
    cpu.emu_start(0x803125C8,stop,count=300)
    assert cpu.reg_read(r.UC_PPC_REG_PC)==stop
    assert cpu.reg_read(r.UC_PPC_REG_3)==(0x81000000 if allowed else 0)
    assert cpu.reg_read(r.UC_PPC_REG_4)==0x81001000
    assert cpu.reg_read(r.UC_PPC_REG_1)==0x81700000-(16 if allowed else 0)


@pytest.mark.parametrize('index,row', list(enumerate(ONEUPS.values())))
def test_oneup_contact_is_latched_without_host_actor_poll(index, row):
    r = pytest.importorskip('unicorn.ppc_const')
    cpu, selected = cpu_for_plan(fps=True)
    hook = next(h for h in selected[3] if h['hook'] == oneup_hook.HOOK)
    control = hook['target'] + oneup_hook.payload()[1]
    actor, wrapper, record, descriptor, stage = 0x81000000, 0x81001000, 0x81002000, 0x81003000, 0x81004000
    app, document, module, mission = 0x81005000, 0x81006000, 0x81007000, 0x81008000
    for address, value in ((control,1),(actor,oneup_hook.VTABLE),(actor+0x64,wrapper),
                           (wrapper+8,record),(wrapper+12,descriptor),(record,row['object_id']),
                           (0x808F336C,app),(app+4,document),(document+0x1c,module),
                           (module+0x34,stage),(stage,0x80759438),(stage+0x4c,mission),
                           (actor+0x34,0x81009000),(stage+0x18,0x81009000),(actor+0xbc,0x12345678)):
        word(cpu,address,value)
    cpu.mem_write(mission,row['mission_id'].encode()+b'\0')
    cpu.reg_write(r.UC_PPC_REG_1,0x81700000)
    cpu.reg_write(r.UC_PPC_REG_30,actor)
    cpu.reg_write(r.UC_PPC_REG_CR,0x12345678)
    for _ in range(2):
        cpu.emu_start(oneup_hook.HOOK,oneup_hook.HOOK+4,count=3000)
        assert cpu.reg_read(r.UC_PPC_REG_PC)==oneup_hook.HOOK+4
        assert read(cpu,control+12)==1<<index
        assert cpu.reg_read(r.UC_PPC_REG_1)==0x81700000
        assert cpu.reg_read(r.UC_PPC_REG_30)==actor
        assert cpu.reg_read(r.UC_PPC_REG_CR)==0x12345678
        assert cpu.reg_read(r.UC_PPC_REG_0)==0x12345678


@pytest.mark.parametrize('interval', [0,1,2])
def test_native_fps_switch_updates_vi_interval_and_physics_delta(interval):
    r = pytest.importorskip('unicorn.ppc_const')
    cpu, selected = cpu_for_plan(fps=True)
    hook = next(h for h in selected[3] if h['hook']==oneup_hook.HOOK)
    control=hook['target']+oneup_hook.payload()[1]+8
    word(cpu,control,interval)
    actual=2 if interval==2 else 1
    word(cpu,0x808F2D94,actual)
    cpu.mem_write(0x808F2D98,struct.pack('>f',actual/60))
    cpu.mem_write(0x8090DB08,b'\x12\x34\x56\x78')
    cpu.reg_write(r.UC_PPC_REG_1,0x81700000)
    cpu.reg_write(r.UC_PPC_REG_13,0x808F9520)
    cpu.reg_write(r.UC_PPC_REG_LR,0x80010000)
    cpu.emu_start(0x803E19E4,0x80010000,count=1000)
    actual=2 if interval==2 else 1
    assert cpu.reg_read(r.UC_PPC_REG_PC)==0x80010000
    assert cpu.reg_read(r.UC_PPC_REG_3)==actual
    assert read(cpu,0x808F2D94)==actual
    assert struct.unpack('>f',cpu.mem_read(0x808F2D98,4))[0]==pytest.approx(actual/60)
    assert bytes(cpu.mem_read(0x8090DB08,4))==b'\x12\x34\x56'+bytes([actual])


@pytest.mark.parametrize('interval,requested,actual', [(0,2,1),(1,2,1),(2,2,2),(2,1,1),(2,3,3)])
def test_frame_setter_computes_correct_delta_before_gameplay_update(pal_dol_bytes,interval,requested,actual):
    r=pytest.importorskip('unicorn.ppc_const')
    cpu,selected=cpu_for_plan(fps=True)
    image=Dol(pal_dol_bytes)
    # The real frame callback calls the setter and immediately consumes dt,
    # before the getter/presentation path. Testing only the getter misses this.
    cpu.mem_write(0x803E19B4,image.read(0x803E19B4,0x30))
    hook=next(h for h in selected[3] if h['hook']==oneup_hook.HOOK)
    control=hook['target']+oneup_hook.payload()[1]+8
    word(cpu,control,interval);word(cpu,0x808F2D90,0x42700000)
    cpu.mem_write(0x81010790,struct.pack('>d',float(1<<52)))
    cpu.reg_write(r.UC_PPC_REG_MSR,cpu.reg_read(r.UC_PPC_REG_MSR)|0x2000)
    cpu.reg_write(r.UC_PPC_REG_1,0x81700000)
    cpu.reg_write(r.UC_PPC_REG_2,0x81010000)
    cpu.reg_write(r.UC_PPC_REG_13,0x808F9520)
    cpu.reg_write(r.UC_PPC_REG_3,requested)
    cpu.reg_write(r.UC_PPC_REG_LR,0x80010000)
    cpu.emu_start(0x803E19B0,0x80010000,count=1000)
    assert cpu.reg_read(r.UC_PPC_REG_PC)==0x80010000
    assert read(cpu,control)==0x10000|interval
    assert read(cpu,0x808F2D94)==actual
    assert struct.unpack('>f',cpu.mem_read(0x808F2D98,4))[0]==pytest.approx(actual/60)
    # One emulated second must advance one gameplay second in either mode.
    assert (60/actual)*struct.unpack('>f',cpu.mem_read(0x808F2D98,4))[0]==pytest.approx(1)


@pytest.mark.parametrize('group', range(1,8))
def test_emerald_needs_exactly_its_three_completed_stages(group):
    rows=[s['mission_id'] for s in STAGES if s['zone_index']==group+6]
    assert len(rows)==3
    name,data=next((name,row) for name,row in LOCATION_TABLE.items() if row.kind=='emerald' and row.index==group)
    slot={'locations':{name:data.code},'options':{}}
    assert data.code not in detect_checks(slot,snapshot(persisted_clears=frozenset(rows[:2])))
    assert data.code in detect_checks(slot,snapshot(persisted_clears=frozenset(rows)))


def test_new_oneup_padding_is_unreferenced_and_after_an_unconditional_branch(pal_dol_bytes):
    image=Dol(pal_dol_bytes)
    sites=load_data('oneup_capture_sites.json')
    references=set()
    for index,offset,address,size in image.sections:
        raw=image.read(address,size)
        for k in range(0,size-3,4):
            value=int.from_bytes(raw[k:k+4],'big');references.add(value)
            if index<7 and value>>26 in (16,18):
                mask,sign=(0xfffc,0x8000) if value>>26==16 else (0x3fffffc,0x2000000)
                delta=value&mask
                if delta&sign:delta-=2*sign
                references.add(delta if value&2 else address+k+delta)
    for site in sites:
        address=site['address']
        before=int(site['before'],16)
        assert before>>26==18 and before&3==0
        assert image.read(address-4,4)==bytes.fromhex(site['before'])
        assert image.read(address,12)==bytes(12)
        assert image.read(address+12,4)==bytes.fromhex(site['after'])
        assert not set(range(address,address+12,4))&references
    patch_dol(pal_dol_bytes,'all-features',options={'sixty_fps':1,'luma':1})


@pytest.mark.parametrize('key', ['stg510:ring:2','stg510:ring:3','stg510:ring:5','stg510:one_up','stg510'])
def test_new_aquarium_route_needs_all_three_items(key):
    items=['Swim','Progressive Breathing','Progressive Yellow Drill Wisp']
    assert logic.check(world(),State(*items),MANIFEST,key)
    for missing in range(3):
        assert not logic.check(world(),State(*(items[:missing]+items[missing+1:])),MANIFEST,key)


@pytest.mark.parametrize('key,base,extra', [
    ('stg440:ring:4',('Purple Frenzy Wisp',),('Stomp',)),
    ('stg220:ring:5',('Progressive Rail',),('Progressive Rail',)),
    ('stg310:ring:4',('Blue Cube Wisp','Homing Attack'),('Double Jump',)),
    ('stgB10',('Homing Attack','Progressive Yellow Drill Wisp','Progressive Rail'),('Progressive Rail',)),
    ('stg120',('Progressive Crouch','Progressive Crouch','Stomp'),('Homing Attack',)),
    ('stg120:ring:5',('Progressive Crouch','Progressive Crouch','Cyan Laser Wisp','Double Jump'),('Homing Attack',)),
])
def test_added_requirements_are_required_in_movement_logic(key,base,extra):
    assert not logic.check(world(),State(*base),MANIFEST,key)
    assert logic.check(world(),State(*base,*extra),MANIFEST,key)


@pytest.mark.parametrize('key', ['stg120','stg120:ring:5'])
@pytest.mark.parametrize('move', ['Double Jump','Mid-Air Boost'])
def test_tropical_three_laser_route_without_stomp(key,move):
    items=('Progressive Crouch','Progressive Crouch','Cyan Laser Wisp','Homing Attack',move)
    assert logic.check(world(),State(*items),MANIFEST,key)
    if key=='stg120':
        for rank in (None,'C','B'):
            assert logic.check(world(),State(*items),MANIFEST,key,rank)


def test_starlight_three_oneup_has_mid_air_boost_alternative():
    assert logic.check(world(),State('Mid-Air Boost'),MANIFEST,'stg340:one_up')


def test_aquarium_six_last_ring_uses_the_clear_routes():
    for mode in ('normal','movement','advanced_normal','advanced_movement'):
        assert MANIFEST['locations']['stg520:ring:5'][mode]==MANIFEST['locations']['stg520'][mode]


@pytest.mark.skipif(os.name != 'nt', reason='Windows Cygwin path translation')
def test_unicode_wit_paths_are_temporary_and_do_not_rename_the_original(tmp_path,monkeypatch):
    from contextlib import contextmanager
    from ..client import wit_paths
    directory=tmp_path/'Pokémon';directory.mkdir()
    original=directory/'original.iso';original.write_bytes(b'original')
    active=[]
    @contextmanager
    def alias(parent):
        active.append(parent)
        try: yield type(parent)('Z:/')
        finally: active.remove(parent)
    monkeypatch.setattr(wit_paths,'ascii_directory',alias)
    with wit_paths.arguments(directory/'wit.exe',['EXTRACT',original,directory/'new'/'source']) as argv:
        assert active
        assert all(value.isascii() for value in argv)
        assert argv[1]=='EXTRACT'
    assert not active
    assert original.read_bytes()==b'original'


@pytest.mark.skipif(os.name != 'nt', reason='Windows Cygwin path translation')
def test_unicode_source_filename_is_linked_or_copied_without_modifying_source(tmp_path):
    from ..client.wit_paths import arguments
    source=tmp_path/'é.iso';source.write_bytes(b'original')
    with arguments('wit.exe',['VERIFY',source]) as argv:
        assert all(value.isascii() for value in argv)
        assert __import__('pathlib').Path(argv[2]).read_bytes()==b'original'
        staged=__import__('pathlib').Path(argv[2])
    assert not staged.exists()
    assert source.read_bytes()==b'original'


def test_fps_control_rejects_other_values_before_backend_write():
    from ..client.memory import SonicMemory, MemoryUnavailable
    from .test_memory import FakeBackend
    backend=FakeBackend();memory=SonicMemory(backend,lambda *args:'context')
    memory._fps_interval=2
    for value in (0,1,3,0xffffffff):
        with pytest.raises(MemoryUnavailable,match='FPS control only accepts'):
            memory.write_u32(0x90001000,value,expected=0,operation='fps_control')
    assert not backend.writes
    memory.write_u32(0x90001000,2,expected=0,operation='fps_control')
    assert memory.read_u32(0x90001000)==2


def test_fps_policy_only_authorizes_the_verified_mailbox(monkeypatch):
    import hashlib
    from types import SimpleNamespace
    from ..client.state import WritePolicy
    from ..client.memory import MemoryUnavailable
    from ..client import fps_control
    seed='fps-test'
    native={'seed_digest':hashlib.sha256(seed.encode()).digest()[:16].hex(),'correct_fps_setter':True}
    memory=SimpleNamespace(verify_revision=lambda:None,_fps_interval=2,native_patch=native)
    def forbidden(*args):
        raise AssertionError('FPS control must not require a selected/bound save or gameplay snapshot')
    guard=SimpleNamespace(check=forbidden,journal=SimpleNamespace(identity={'seed':seed}))
    monkeypatch.setattr(fps_control,'address',lambda mem:0x80002000)
    policy=WritePolicy(memory,guard,forbidden)
    assert policy('fps_control',0x80002000,4)
    for address,size in ((0x80002004,4),(0x80002000,8),(0x803E19E4,4)):
        with pytest.raises(MemoryUnavailable,match='invalid FPS control'):
            policy('fps_control',address,size)
    guard.journal.identity['seed']='other seed'
    with pytest.raises(MemoryUnavailable,match='connected seed ISO'):
        policy('fps_control',0x80002000,4)


def test_fps_apply_waits_for_native_confirmation_and_does_not_repeat_writes(monkeypatch):
    from types import SimpleNamespace
    from ..client import fps_control,oneup_hook
    control=0x80002008
    values={control:0,0x808F2D94:1,0x8090DB0B:1}
    writes=[]
    def write(address,value,*,expected,operation):
        assert expected==values[address]
        assert operation=='fps_control'
        writes.append((address,value));values[address]=value
    memory=SimpleNamespace(native_patch={'fps_control':True,'correct_fps_setter':True},read_u32=values.__getitem__,
                           read_u8=values.__getitem__,write_u32=write)
    monkeypatch.setattr(oneup_hook,'installed_data',lambda mem:control-8)
    runtime=SimpleNamespace(fps_interval=2)
    assert not fps_control.apply(runtime,memory)['applied']
    assert values[control]==2
    values[0x808F2D94]=2;values[0x8090DB0B]=2
    assert fps_control.apply(runtime,memory)['applied']
    assert writes==[(control,2)]


@pytest.mark.parametrize('luma', [False,True])
def test_old_getter_only_fps_iso_is_recognized_but_cannot_enable_slow_motion(luma):
    from types import SimpleNamespace
    from ..client.native_dol import plan_for_digest
    from ..client import fps_control
    from ..client.memory import MemoryUnavailable
    old=plan(include_sixty_fps=True,include_luma_colors=luma,correct_fps_setter=False,quick_step_forward=False)
    assert plan_for_digest(old[2].hex())==old
    memory=SimpleNamespace(native_patch={'fps_control':True,'correct_fps_setter':False})
    with pytest.raises(MemoryUnavailable,match='slows gameplay'):
        fps_control.apply(SimpleNamespace(fps_interval=2),memory)


def test_native_fps_ack_handles_a_menu_running_at_its_native_60_fps(monkeypatch):
    from types import SimpleNamespace
    from ..client import fps_control,oneup_hook
    control=0x80002008
    values={control:0x10002,0x808F2D94:1,0x8090DB0B:1}
    memory=SimpleNamespace(native_patch={'fps_control':True,'correct_fps_setter':True,'native_fps_switch':True},
                           read_u32=values.__getitem__,read_u8=values.__getitem__)
    monkeypatch.setattr(oneup_hook,'installed_data',lambda mem:control-8)
    status=fps_control.apply(SimpleNamespace(fps_interval=2,_fps_native_restore_done=True),memory)
    assert status['applied'] and status['native_timing']


def test_native_fps_consumption_ack_is_not_a_failed_host_write():
    from ..client.memory import SonicMemory
    from .test_memory import FakeBackend
    class Backend(FakeBackend):
        def write_bytes(self,address,data):
            super().write_bytes(address,(int.from_bytes(data,'big')|0x10000).to_bytes(4,'big'))
    backend=Backend();memory=SonicMemory(backend,lambda *args:'context')
    memory.native_patch={'native_fps_switch':True};memory._fps_interval=2
    memory.write_u32(0x90001000,2,expected=0,operation='fps_control')
    assert memory.read_u32(0x90001000)==0x10002


def test_fps_disable_restores_both_original_frame_values_before_confirming(monkeypatch):
    from types import SimpleNamespace
    from ..client import fps_control as f,oneup_hook
    control=0x80002008
    values={control:0x10002,f.FRAME_INTERVAL:1,f.OWNER_INTERVAL:1,f.FRAME_DELTA:1/60}
    writes=[]
    def write(target,value,*,expected,operation):
        assert operation=='fps_native_restore' and value==2 and expected==values[target]
        writes.append(target);values[target]=value
    memory=SimpleNamespace(native_patch={'fps_control':True,'correct_fps_setter':True,'native_fps_switch':True},
                           read_u32=values.__getitem__,read_f32=values.__getitem__,
                           read_u8=lambda address:values[f.OWNER_INTERVAL],write_u32=write)
    monkeypatch.setattr(oneup_hook,'installed_data',lambda mem:control-8)
    runtime=SimpleNamespace(fps_interval=2)
    assert not f.apply(runtime,memory)['applied']
    assert writes==[f.FRAME_INTERVAL,f.OWNER_INTERVAL]
    # The original frame setter must have consumed the new owner interval.
    values[f.FRAME_DELTA]=1/30
    assert f.apply(runtime,memory)['applied']
    assert runtime._fps_native_restore_done
    assert writes==[f.FRAME_INTERVAL,f.OWNER_INTERVAL]


def test_native_fps_restore_is_seed_and_field_bounded(monkeypatch):
    import hashlib
    from types import SimpleNamespace
    from ..client import fps_control as f
    from ..client.memory import MemoryUnavailable
    control=0x80002008;seed='fps-restore'
    native={'native_fps_switch':True,'seed_digest':hashlib.sha256(seed.encode()).digest()[:16].hex()}
    values={control:0x10002,0x808F336C:f.FRAME_OWNER,f.FRAME_OWNER:0x80758DB8}
    memory=SimpleNamespace(native_patch=native,_fps_interval=2,read_u32=values.__getitem__)
    guard=SimpleNamespace(journal=SimpleNamespace(identity={'seed':seed}))
    monkeypatch.setattr(f,'address',lambda mem:control)
    for field in (f.FRAME_INTERVAL,f.OWNER_INTERVAL):assert f.authorize(memory,guard,field,4,restore=True)
    for field in (control,f.FRAME_DELTA,f.FRAME_OWNER):
        with pytest.raises(MemoryUnavailable):f.authorize(memory,guard,field,4,restore=True)
    values[0x808F336C]=0
    with pytest.raises(MemoryUnavailable):f.authorize(memory,guard,f.OWNER_INTERVAL,4,restore=True)
