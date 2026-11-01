from pathlib import Path
import struct

import pytest

from ..Items import ITEM_TABLE
from ..client import boot_permissions as boot
from ..client import movement_gate, capsule_refresh, gameplay_controls, white_capsule_spawn
from ..client.native_dol import plan, ARENA, Dol, patch_dol


def initialized(movement=True, boost=True, game_land=True, items=()):
    rows,payload,digest,hooks=plan()
    payload,values=boot.initialize(payload,hooks,{
        'movement_unlocks':movement,'boost_lock':boost,'game_land_checks':game_land},items)
    return rows,payload,hooks,values


def controls(payload,hooks,module,size=4,offset=None,hook=None):
    if offset is None:offset=module.payload()[1]
    target=next(h['target'] for h in hooks if h['hook']==(hook or module.HOOK))
    address=target+offset
    return address,struct.unpack('>'+'I'*(size//4),payload[address-ARENA:address-ARENA+size])


@pytest.mark.parametrize('movement',[True,False])
@pytest.mark.parametrize('boost',[True,False])
@pytest.mark.parametrize('game_land',[True,False])
def test_option_matrix_is_active_before_client(movement,boost,game_land):
    _,payload,hooks,_=initialized(movement,boost,game_land)
    _,(armed,mask)=controls(payload,hooks,movement_gate,8,movement_gate.payload(gecko=True)[2])
    assert armed==1
    assert mask & 0x1FFF == (0 if movement else 0x1FFF)
    words=capsule_refresh.payload_words(compact_abi=True,epilogue_abi=True,cache_permissions=True)
    address,(owner,index,allowed)=controls(payload,hooks,capsule_refresh,12,capsule_refresh.data_offset(words))
    assert (owner,index,allowed)==(address+4,0,int(not boost)|int(not game_land)<<1)
    for kind in ('boost_use','boost_query','boost_add'):
        address,values=controls(payload,hooks,gameplay_controls,20,gameplay_controls.payload(kind)[1],gameplay_controls.HOOKS[kind][0])
        assert values==(address+4,0,4,0,int(boost))
    for kind in ('speed_get','speed_set','speed_ui'):
        _,values=controls(payload,hooks,gameplay_controls,12,gameplay_controls.payload(kind)[1],gameplay_controls.HOOKS[kind][0])
        assert values[2]==(0 if movement and game_land else 4)


def test_start_inventory_keeps_progressive_counts():
    items=[ITEM_TABLE[name] for name in ('Double Jump','Progressive Crouch','Progressive Crouch',
        'Progressive Yellow Drill Wisp','White Boost Wisp')]
    _,payload,hooks,_=initialized(items=items)
    _,(_,mask)=controls(payload,hooks,movement_gate,8,movement_gate.payload(gecko=True)[2])
    assert mask==1|16|32
    from ..client import drill_turbo,quick_step
    assert controls(payload,hooks,drill_turbo)[1]==(0,)
    assert controls(payload,hooks,quick_step)[1]==(0,)
    _,payload,hooks,_=initialized(items=items+[ITEM_TABLE['Progressive Yellow Drill Wisp']])
    assert controls(payload,hooks,drill_turbo)[1]==(1,)


def test_generated_container_roundtrip_and_old_container(tmp_path):
    from . import generate
    from ..patch import load_patch,SonicColoursPatch
    multi=generate({'start_inventory':{'Double Jump':1,'Progressive Crouch':2},'red_ring_item_colors':False})
    for name in ('Double Jump','Progressive Crouch','Progressive Crouch'):
        multi.push_precollected(multi.worlds[1].create_item(name))
    multi.worlds[1].generate_output(tmp_path)
    patch=load_patch(next(tmp_path.glob('*.apsoniccolours')))
    assert sorted(patch.initial_items)==sorted([ITEM_TABLE['Double Jump'],*[ITEM_TABLE['Progressive Crouch']]*2])
    old=SonicColoursPatch(str(tmp_path/'old.apsoniccolours'),1,'Test',slot_data=patch.slot_data)
    old.write()
    assert load_patch(old.path).initial_items==[]
    with pytest.raises(ValueError):boot.validate_items([True])
    with pytest.raises(ValueError):boot.validate_items([123])


def test_boot_dol_passes_complete_revision_inspection():
    path=Path('build/sonic_colours_reference/memdumps_and_more/main.dol')
    if not path.exists():pytest.skip('private original PAL main.dol absent')
    from ..client.memory import SonicMemory
    data,registry=patch_dol(path.read_bytes(),'BootTest',options={
        'movement_unlocks':True,'boost_lock':True,'game_land_checks':True})
    image=Dol(data)
    class Backend:
        def read_bytes(self,address,size):
            if address==0x80000000:return (b'SNCP8P\0\0'+bytes(24))[:size]
            if address==0x80000007:return bytes(size)
            try:return image.read(address,size)
            except ValueError:return bytes(size)
    memory=SonicMemory(Backend());memory.verify_revision()
    assert memory.native_patch['white_capsule_spawn']
    assert registry['boot_permissions']
    assert gameplay_controls.installed(memory,'boost_add')
    assert memory.boost_consumption_safe


def machine_for(movement=True,boost=True):
    uc=pytest.importorskip('unicorn')
    from unicorn import ppc_const as r
    machine=uc.Uc(uc.UC_ARCH_PPC,uc.UC_MODE_32|uc.UC_MODE_BIG_ENDIAN)
    import faulthandler
    enabled=faulthandler.is_enabled()
    try:
        faulthandler.disable()
        machine.mem_map(0x80000000,0x1800000)
        machine.mem_map(0x90000000,0x4000000)
    finally:
        if enabled:faulthandler.enable()
    rows,payload,hooks,_=initialized(movement,boost)
    machine.mem_write(ARENA,payload)
    for address,old,new in rows:machine.mem_write(address,new)
    original={r.UC_PPC_REG_0+i:0x11110000+i for i in range(32)}
    original.update({r.UC_PPC_REG_1:0x917F0000,r.UC_PPC_REG_30:0x90001000,
                     r.UC_PPC_REG_CR:0xA5A5A5A5,r.UC_PPC_REG_CTR:0x12345678,r.UC_PPC_REG_LR:0x80011000})
    for register,value in original.items():machine.reg_write(register,value)
    machine.reg_write(r.UC_PPC_REG_MSR,0x2000)
    return machine,original,payload,hooks


@pytest.mark.parametrize('kind',['white','cyan','random','egg'])
@pytest.mark.parametrize('boost',[True,False])
def test_white_capsule_chooses_ghost_before_graphics_or_collision(kind,boost):
    uc=pytest.importorskip('unicorn')
    from unicorn import ppc_const as r
    machine,original,payload,hooks=machine_for(boost=boost)
    actor=original[r.UC_PPC_REG_30]
    machine.mem_write(actor+0x114,struct.pack('>i',0 if kind=='cyan' else -1))
    machine.mem_write(actor+0x148,bytes([kind=='random']))
    machine.mem_write(actor+0x14A,bytes([kind=='egg']))
    stops=(white_capsule_spawn.GHOST,white_capsule_spawn.HOOK+4)
    machine.hook_add(uc.UC_HOOK_CODE,lambda m,a,s,u:m.emu_stop() if a in stops else None)
    machine.emu_start(white_capsule_spawn.HOOK,0,count=4000)
    assert machine.reg_read(r.UC_PPC_REG_PC)==(stops[0] if boost and kind=='white' else stops[1])
    for register,value in original.items():
        if register!=r.UC_PPC_REG_CR:assert machine.reg_read(register)==value
    assert machine.reg_read(r.UC_PPC_REG_CR)&0x0FFFFFFF==original[r.UC_PPC_REG_CR]&0x0FFFFFFF


@pytest.mark.parametrize('kind',['boost_use','boost_query','boost_add'])
@pytest.mark.parametrize('locked',[True,False])
@pytest.mark.parametrize('known_gauge',[True,False])
def test_boost_is_denied_before_host_has_seen_the_gauge(kind,locked,known_gauge):
    pytest.importorskip('unicorn')
    from unicorn import ppc_const as r
    machine,original,payload,hooks=machine_for(boost=locked)
    gauge=0x90002000
    machine.reg_write(r.UC_PPC_REG_3,gauge)
    machine.reg_write(r.UC_PPC_REG_2,0x808FC5C0)
    machine.mem_write(0x808F6040,bytes(4))
    machine.mem_write(gauge+8,struct.pack('>f',0 if kind=='boost_add' else 60))
    machine.reg_write(r.UC_PPC_REG_FPR0,0)
    machine.reg_write(r.UC_PPC_REG_FPR1,int.from_bytes(struct.pack('>d',60),'big'))
    machine.reg_write(r.UC_PPC_REG_FPR2,0)
    wrapper=original[r.UC_PPC_REG_30]
    for address,value in ((wrapper+0x28,0x90003000),(0x9000308C,0x90004000)):
        machine.mem_write(address,struct.pack('>I',value))
    hook=gameplay_controls.HOOKS[kind][0]
    address,_=controls(payload,hooks,gameplay_controls,20,gameplay_controls.payload(kind)[1],hook)
    if known_gauge:machine.mem_write(address+12,struct.pack('>I',gauge))
    machine.emu_start(hook,hook+4,count=4000)
    assert machine.reg_read(r.UC_PPC_REG_PC)==hook+4
    result=struct.unpack('>d',machine.reg_read(r.UC_PPC_REG_FPR1).to_bytes(8,'big'))[0]
    assert result==(0 if locked else 60)
    assert machine.reg_read(r.UC_PPC_REG_CTR)==original[r.UC_PPC_REG_CTR]
    assert machine.reg_read(r.UC_PPC_REG_1)==original[r.UC_PPC_REG_1]


@pytest.mark.parametrize('state_id,bit',[(8,0),(13,2),(39,3),(41,4),(44,6),(29,9),(30,10),(110,12)])
def test_move_cannot_start_until_the_permission_word_is_updated(state_id,bit):
    uc=pytest.importorskip('unicorn')
    from unicorn import ppc_const as r
    machine,original,payload,hooks=machine_for()
    state,actor,wrapper=0x90005000,0x90006000,0x90007000
    for address,value in ((state,movement_gate.STATE_MACHINE_VTABLE),(state+0x28,actor),
        (actor,movement_gate.PLAYER_VTABLE),(actor+0x70,wrapper),(wrapper+8,state),
        (actor+0x88,0x90008000),(actor+0x8C,0x90009000)):
        machine.mem_write(address,struct.pack('>I',value))
    stops=(original[r.UC_PPC_REG_LR],movement_gate.HOOK+4)
    machine.hook_add(uc.UC_HOOK_CODE,lambda m,a,s,u:m.emu_stop() if a in stops else None)
    def run():
        for register,value in original.items():machine.reg_write(register,value)
        machine.reg_write(r.UC_PPC_REG_3,state+0x14)
        machine.reg_write(r.UC_PPC_REG_4,state_id)
        machine.emu_start(movement_gate.HOOK,0,count=4000)
        return machine.reg_read(r.UC_PPC_REG_PC)
    assert run()==stops[1 if state_id==41 else 0]
    if state_id==41:assert machine.reg_read(r.UC_PPC_REG_4)==3
    address,_=controls(payload,hooks,movement_gate,8,movement_gate.payload(gecko=True)[2])
    machine.mem_write(address+4,struct.pack('>I',1<<bit))
    assert run()==stops[1]


def test_actor_transition_and_permission_update_never_disarm_movement(monkeypatch):
    from collections import Counter
    from types import SimpleNamespace
    from ..client import skydiving
    address=0x80002000
    values={address:1,address+4:0};writes=[]
    class Memory:
        def read_u32(self,where):return values[where]
        def write_u32(self,where,value,**kwargs):
            assert values[where]==kwargs['expected']
            values[where]=value;writes.append((where,value))
    monkeypatch.setattr(movement_gate,'installed_data',lambda *args:(address,'native'))
    monkeypatch.setattr(skydiving,'configure',lambda *args:{})
    snapshot=SimpleNamespace(evidence={},scene='loading',scene_verified=False,
                             stable_polls=0,stage_epoch=None,death_state='unknown')
    movement_gate.configure(Memory(),snapshot,{'counts':Counter({'Double Jump':1})})
    assert values=={address:1,address+4:1}
    assert writes==[(address+4,1)]
