import struct
from pathlib import Path

import pytest

from ..client import red_ring_spawn as spawn
from ..client.native_dol import plan,Dol


def test_padding_is_disjoint_and_has_no_arena_cost():
    old=plan(include_ring_spawn=False,include_boot_guards=False,include_accessible_colors=False)
    current=plan(include_boot_guards=False)
    assert current[1]==old[1]
    for address,original,replacement in spawn.patches():
        assert len(original)==len(replacement)
        assert not any(a<address+len(original) and address<a+len(n) for a,o,n in old[0])
    assert len(spawn.layout()[1])==36


@pytest.mark.parametrize('colors',[None,{}, {'stg110':['purple']*5}])
def test_incomplete_prefill_is_rejected(colors):
    if colors is None:assert spawn.validate_colors(colors) is None
    else:
        with pytest.raises(ValueError):spawn.validate_colors(colors)


def test_private_original_padding_and_model_boundary():
    path=Path('build/sonic_colours_reference/memdumps_and_more/main.dol')
    if not path.exists():pytest.skip('private original PAL main.dol absent')
    dol=Dol(path.read_bytes())
    for site in spawn.load_data('red_ring_spawn_sites.json'):
        address,size=site['address'],site['size']
        assert dol.read(address-4,4)==bytes.fromhex('4e800020')
        assert dol.read(address,size)==bytes(size)
        assert dol.read(address+size,4)==bytes.fromhex(site['after'])
    assert dol.read(spawn.HOOK,4)==spawn.ORIGINAL.to_bytes(4,'big')
    assert dol.read(spawn.COPY_MATERIAL,8)==bytes.fromhex('9421ffa07c0802a6')
    assert dol.read(spawn.CACHE_FLUSH,4)==bytes.fromhex('28040000')


def test_prefilled_dol_roundtrip_and_palette_integrity():
    from ..client.native_dol import patch_dol
    from ..client.memory import SonicMemory,MemoryUnavailable
    path=Path('build/sonic_colours_reference/memdumps_and_more/main.dol')
    if not path.exists():pytest.skip('private original PAL main.dol absent')
    colors={mission:list(spawn.PALETTE[1:4])+['red','purple'] for mission in spawn.missions()}
    data,registry=patch_dol(path.read_bytes(),'SpawnTest',colors)
    dol=Dol(data)
    class Backend:
        def read_bytes(self,address,size):
            if address==0x80000000:return (b'SNCP8P\0\0'+bytes(24))[:size]
            if address==0x80000007:return bytes(size)
            try:return dol.read(address,size)
            except ValueError:return bytes(size)
    memory=SonicMemory(Backend())
    memory.verify_revision()
    assert memory.native_patch['red_ring_spawn']
    header,rows,_=spawn.layout()
    assert dol.read(header+4,4)==(2).to_bytes(4,'big')
    assert all(dol.read(address+2,2)==spawn.encode(colors[name]).to_bytes(2,'big') for name,address in rows.items())
    offset=dol.offset(next(iter(rows.values()))+2,2)
    dol.data[offset:offset+2]=bytes.fromhex('7fff')
    with pytest.raises(MemoryUnavailable,match='ring color row'):memory.verify_revision()


@pytest.mark.parametrize('checks',('singles','per_level'))
def test_generated_patch_contains_authenticated_prefill(tmp_path,checks):
    from . import generate
    from ..patch import load_patch
    multi=generate({'red_ring_item_colors':True,'own_item_red_ring_colors':'item_classification',
                    'movement_unlocks':False,'game_land_checks':False,'red_ring_checks':checks},19,fill=True)
    world=multi.worlds[1]
    world.generate_output(tmp_path)
    patch=load_patch(next(tmp_path.glob('*.apsoniccolours')))
    assert set(patch.ring_colors)==set(spawn.missions())
    from ..client.red_ring_colors import reward_color
    from ..Locations import LOCATION_TABLE
    for name,code in patch.slot_data['locations'].items():
        row=LOCATION_TABLE[name]
        if row.kind not in ('ring','rings'):continue
        item=multi.get_location(name,1).item
        expected=reward_color(item.code, item.player,item.flags,1,patch.slot_data['options'],
                              (multi.seed_name,0,1),code)
        indices=(row.index-1,) if row.kind=='ring' else range(5)
        assert all(patch.ring_colors[row.mission][index]==expected for index in indices)


def test_palette_publication_requires_authenticated_seed_and_scouts():
    from types import SimpleNamespace
    from .test_red_ring_colors import data_for
    from ..client.red_ring_colors import RedRingColors
    from ..client.memory import MemoryUnavailable
    import hashlib
    data=data_for();colors=RedRingColors(data,1,0)
    code=colors.locations['stg110',1]
    colors.receive([(1,colors.locations['stg110',ring],2,1) for ring in range(1,6)])
    identity=(data['seed_name'],0,1)
    address=spawn.layout()[1]['stg110']+2
    tx={'source':colors,'identity':identity,'values':{address:spawn.encode(['purple']*5).to_bytes(2,'big')}}
    memory=SimpleNamespace(error=MemoryUnavailable,_ring_spawn_transaction=tx,native_patch={
        'red_ring_spawn':True,'seed_digest':hashlib.sha256(identity[0].encode()).digest()[:16].hex(),
        'code_sha256':'test'})
    guard=SimpleNamespace(journal=SimpleNamespace(identity=dict(zip(('seed','team','slot'),identity))))
    assert spawn.authorize(memory,guard,address,2)
    with pytest.raises(MemoryUnavailable):spawn.authorize(memory,guard,address-2,2)
    tx['values'][address]=spawn.encode(['blue']*5).to_bytes(2,'big')
    with pytest.raises(MemoryUnavailable,match='scout'):spawn.authorize(memory,guard,address,2)
    memory.native_patch['seed_digest']='0'*32
    with pytest.raises(MemoryUnavailable,match='unauthenticated'):spawn.authorize(memory,guard,address,2)


@pytest.mark.parametrize('color',range(8))
@pytest.mark.parametrize('ring',range(5))
@pytest.mark.parametrize('mission',('stg110','stg660'))
def test_native_spawn_executes_before_return_preserving_registers(color,ring,mission,real_sdk=False,publish_race=False):
    uc=pytest.importorskip('unicorn')
    from unicorn import ppc_const as reg
    machine=uc.Uc(uc.UC_ARCH_PPC,uc.UC_MODE_32|uc.UC_MODE_BIG_ENDIAN)
    import faulthandler
    enabled=faulthandler.is_enabled()
    try:
        faulthandler.disable()  # Unicorn's Windows mapping probes use handled SEH faults.
        machine.mem_map(0x80000000,0x1800000)
        machine.mem_map(0x90000000,0x4000000)
    finally:
        if enabled:faulthandler.enable()
    if real_sdk:
        source=Path('build/sonic_colours_reference/memdumps_and_more/main.dol')
        brres=Path('build/redring_original.brres')
        if not source.exists() or not brres.exists():pytest.skip('private PAL DOL/BRRES absent')
        image=Dol(source.read_bytes())
        for index,offset,address,size in image.sections:machine.mem_write(address,image.read(address,size))
        resource=brres.read_bytes()
        machine.mem_write(0x92000000,resource)
    colors={mission:['red']*5 for mission in spawn.missions()}
    colors[mission][ring]=spawn.PALETTE[color]
    for address,old,new in spawn.patches():
        machine.mem_write(address,spawn.prefill(address,new,colors))
    def word(address,value):machine.mem_write(address,struct.pack('>I',value))
    actor,gfx,model,regs,stages,dirty,record,wrapper=(0x90001000,0x90002000,0x90003000,
        0x90003400,0x90003480,0x900033A0,0x90005000,0x90006000)
    for address,value in {actor:0x8076F8D0,actor+0x64:wrapper,wrapper+8:record,record+0x24:ring,
        gfx+0x1C:model,model:0x807AA950,model+0x168:regs,model+0x174:stages,model+0x140:dirty,
        0x808F336C:0x80010000,0x80010004:0x80020000,0x8002001C:0x80030000,
        0x80030034:0x90010000,0x90010000:0x80759438,0x9001004C:0x90008000}.items():word(address,value)
    if real_sdk:word(model+0xE8,0x92086740)
    machine.mem_write(0x90008000,mission.encode()+b'\0')
    originals={reg.UC_PPC_REG_0+i:0x11110000+i for i in range(32)}
    originals[reg.UC_PPC_REG_0]=gfx
    originals[reg.UC_PPC_REG_1]=0x917F0000
    originals[reg.UC_PPC_REG_28]=actor
    originals.update({reg.UC_PPC_REG_LR:0x80011000,reg.UC_PPC_REG_CTR:0x12345678,
                      reg.UC_PPC_REG_CR:0xA5A5A5A5})
    for register,value in originals.items():machine.reg_write(register,value)
    machine.reg_write(reg.UC_PPC_REG_MSR,0x2000)
    fprs={reg.UC_PPC_REG_FPR0+i:0x3FF0000000000000+i for i in range(14)}
    for register,value in fprs.items():machine.reg_write(register,value)
    calls=[]
    initial_regs=bytes(128)
    initial_stages=bytes(512)
    if real_sdk:
        mdl=0x86740
        group=mdl+struct.unpack_from('>i',resource,mdl+0x30)[0]
        mat=group+struct.unpack_from('>i',resource,group+36)[0]
        display=mat+struct.unpack_from('>i',resource,mat+0x3C)[0]
        shader=mat+struct.unpack_from('>i',resource,mat+0x28)[0]
        initial_regs=resource[display+32:display+160]
        initial_stages=resource[shader:shader+512]
    def hook(machine,address,size,user):
        if publish_race and bytes(machine.mem_read(address,4))==struct.pack('>I',40<<26 | 15<<21 | 16<<16 | 2):
            word(spawn.layout()[0]+4,3)
        if address==spawn.CACHE_FLUSH:
            assert (machine.reg_read(reg.UC_PPC_REG_3),machine.reg_read(reg.UC_PPC_REG_4)) in ((regs,128),(stages,512))
            machine.reg_write(reg.UC_PPC_REG_PC,machine.reg_read(reg.UC_PPC_REG_LR))
        if address==spawn.COPY_MATERIAL:
            assert machine.reg_read(reg.UC_PPC_REG_3)==model
            assert machine.reg_read(reg.UC_PPC_REG_4)==0
            assert machine.reg_read(reg.UC_PPC_REG_5)==0x900
            calls.append(address)
            if real_sdk:return
            machine.mem_write(regs,initial_regs);machine.mem_write(stages,initial_stages)
            return_to=machine.reg_read(reg.UC_PPC_REG_LR)
            stack=machine.reg_read(reg.UC_PPC_REG_1)
            for offset in range(4,0x30,4):
                machine.mem_write(stack+offset,(0xDEAD0000+offset).to_bytes(4,'big'))
            for i in (0,*range(3,13)):machine.reg_write(reg.UC_PPC_REG_0+i,0xFFFF0000+i)
            for register in fprs:machine.reg_write(register,0)
            machine.reg_write(reg.UC_PPC_REG_CR,0)
            machine.reg_write(reg.UC_PPC_REG_CTR,0xBAD00000)
            machine.reg_write(reg.UC_PPC_REG_PC,return_to)
    machine.hook_add(uc.UC_HOOK_CODE,hook)
    machine.emu_start(spawn.HOOK,spawn.HOOK+4,count=20000)
    assert machine.reg_read(reg.UC_PPC_REG_PC)==spawn.HOOK+4
    assert int.from_bytes(machine.mem_read(actor+0xB4,4),'big')==gfx
    for register,value in originals.items():assert machine.reg_read(register)==value
    for register,value in fprs.items():assert machine.reg_read(register)==value
    if real_sdk:assert bytes(machine.mem_read(0x92000000,len(resource)))==resource
    if publish_race:
        assert not calls
        return
    if color:
        assert calls==[spawn.COPY_MATERIAL]
        red,green,blue=spawn.RGB[color]
        expected=bytearray(initial_regs)
        for offset,value in ((68,red),(71,0x80|(green>>4)),(72,(green&15)<<4),(73,blue)):expected[offset]=value
        assert bytes(machine.mem_read(regs,128))==expected
        expected=bytearray(initial_stages)
        for offset,value in ((101,0),(111,12),(210,252),(233,192),(258,140)):expected[offset]=value
        assert bytes(machine.mem_read(stages,512))[32:]==expected[32:]
    else:assert not calls


def test_native_spawn_with_original_sdk_material_copy():
    test_native_spawn_executes_before_return_preserving_registers(1,0,'stg110',real_sdk=True)


def test_native_constructor_never_uses_a_partially_published_palette():
    test_native_spawn_executes_before_return_preserving_registers(1,0,'stg110',publish_race=True)


@pytest.mark.parametrize('extended',[False,True])
def test_palette_generation_recovers_after_interruption_without_repeated_writes(extended):
    from types import SimpleNamespace
    from .test_red_ring_colors import data_for
    from ..client.red_ring_colors import RedRingColors
    from ..client.memory import MemoryUnavailable
    import hashlib
    colors=RedRingColors(data_for(),1,0)
    colors.receive([(1,colors.locations['stg110',ring],2,1) for ring in range(1,6)])
    header=spawn.layout()[0]
    cells={}
    writes=[]
    memory=SimpleNamespace(error=MemoryUnavailable,native_patch={'red_ring_spawn':True,
        'accessible_ring_colors':extended,
        'seed_digest':hashlib.sha256(colors.identity[0].encode()).digest()[:16].hex(),'code_sha256':'test'})
    memory.read_bytes=lambda address,size:cells.get(address,bytes(size))
    guard=SimpleNamespace(journal=SimpleNamespace(identity=dict(zip(('seed','team','slot'),colors.identity))))
    fail=[True]
    def write(address,data,expected,operation):
        assert operation=='red_ring_spawn'
        assert memory.read_bytes(address,len(data))==expected
        spawn.authorize(memory,guard,address,len(data))
        if address!=header+4 and fail[0]:
            fail[0]=False
            raise MemoryUnavailable('interrupted')
        cells[address]=data;writes.append((address,data))
    memory.write_bytes_verified=write
    runtime=SimpleNamespace(red_ring_colors=colors)
    spawn.publish(runtime,memory)
    assert int.from_bytes(cells[header+4],'big')&1
    spawn.publish(runtime,memory)
    assert int.from_bytes(cells[header+4],'big')==4
    count=len(writes)
    spawn.publish(runtime,memory)
    assert len(writes)==count
