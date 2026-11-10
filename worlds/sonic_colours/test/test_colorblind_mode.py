from .dol_memory import read_dol_memory
from copy import deepcopy
from pathlib import Path
import hashlib
import json
import struct

import pytest

from ..client.item_colors import COLORBLIND,STANDARD,item_color
from ..client.red_ring_colors import reward_color,trap_color
from ..client import red_ring_spawn as spawn
from ..client import ap_hud_connected as hud
from ..client.client import slot_identity_digest
from ..client.runtime import validate_slot
from ..client.native_dol import Dol,plan,ARENA,SIGNATURE,MAGIC,ABI
from ..world_constants import load_data
from . import generate,legacy_rank_slot


@pytest.mark.parametrize('flags,category,label',[
    (0,'filler','gray'),(1,'progression','gold'),(2,'useful','accessible_blue'),
    (3,'progression','gold'),(4,'trap','orange'),(5,'trap','orange'),(6,'trap','orange'),(7,'trap','orange'),
])
def test_ring_and_hud_use_the_same_accessible_rgb(flags,category,label):
    assert item_color(flags,True)==COLORBLIND[category]
    assert item_color(flags)==STANDARD[category]
    color=reward_color(1,2,flags,1,{'colorblind_mode':1,'trap_red_ring_colors':0},'Seed',100)
    assert color==label
    assert spawn.RGB[spawn.PALETTE.index(color)]==tuple(bytes.fromhex(COLORBLIND[category][1:]))


def test_own_red_overrides_and_trap_disguises_still_apply():
    options={'colorblind_mode':1,'own_item_red_ring_colors':0,'trap_red_ring_colors':1}
    assert reward_color(1,1,1,1,options,'Seed',100)=='red'
    expected={'purple':'gold','blue':'accessible_blue','light_blue':'gray'}
    for location in range(40):
        assert reward_color(1,1,4,1,options,'Seed',location)==expected[trap_color('Seed',location)]


@pytest.mark.parametrize('flags',[0,1,2,4,7])
@pytest.mark.parametrize('own',[False,True])
def test_item_hud_changes_only_the_item_color(flags,own):
    boxes={'ap_prefix0':(1,0x1000),'ap_title':(2,0x2000),
           'ap_subtitle':(3,0x3000),'ap_subtitle_outline0':(4,0x4000)}
    owner={'handle':0x90001000,'boxes':boxes}
    event={'kind':'Received','item':'Test Item','player':'Player','flags':flags,'own':own,'alpha':128}
    colors=hud.payloads(owner,[event],load_data('hud_glyph_metrics.json'),colorblind=True)
    target=0x3090 if own else 0x2090
    assert colors[target][:4]==bytes.fromhex(item_color(flags,True)[1:]+'80')
    assert colors[0x1090][:4]==bytes.fromhex('ffffff80')
    assert colors[0x4090][:4]==bytes.fromhex('00000080')
    plain=hud.payloads(owner,[event],load_data('hud_glyph_metrics.json'))
    for address,data in colors.items():
        if address==target:assert data[4:]==plain[address][4:]
        else:assert data==plain[address]


@pytest.mark.parametrize('revision',[10,11])
def test_existing_seed_identity_and_palette_are_preserved(revision):
    old=deepcopy(generate({'red_ring_item_colors':False}).worlds[1].fill_slot_data())
    old['options_revision']=revision
    legacy_rank_slot(old)
    old['options'].pop('colorblind_mode')
    old['options'].pop('sixty_fps')
    old['options'].pop('luma')
    if revision<11:
        for key in ('red_ring_item_colors','own_item_red_ring_colors','trap_red_ring_colors'):old['options'].pop(key)
    expected=hashlib.sha256(json.dumps(old,sort_keys=True).encode()).hexdigest()
    upgraded=validate_slot(old)
    assert upgraded['options']['colorblind_mode']==0
    assert slot_identity_digest(upgraded)==expected


def test_generated_colorblind_patch_bakes_the_accessible_palette(tmp_path):
    from ..patch import load_patch
    multi=generate({'colorblind_mode':True,'red_ring_item_colors':True,
                    'own_item_red_ring_colors':'item_classification','trap_red_ring_colors':'red'},912,fill=True)
    multi.worlds[1].generate_output(tmp_path)
    patch=load_patch(next(tmp_path.glob('*.apsoniccolours')))
    assert patch.slot_data['options']['colorblind_mode']==1
    assert set(color for row in patch.ring_colors.values() for color in row)<={'gold','accessible_blue','gray','orange'}


@pytest.mark.parametrize('kwargs',[
    {'include_accessible_colors':False},
    {'include_accessible_colors':False,'include_boot_guards':False},
    {'include_accessible_colors':False,'include_boot_guards':False,'include_ring_spawn':False},
    {'include_accessible_colors':False,'include_boot_guards':False,'include_ring_materials':False},
])
def test_older_native_isos_pass_full_revision_validation(kwargs):
    source=Path('build/sonic_colours_reference/memdumps_and_more/main.dol')
    if not source.exists():pytest.skip('private original PAL main.dol absent')
    image=Dol(source.read_bytes());patches,payload,digest,hooks=plan(**kwargs)
    for address,old,new in patches:image.replace(address,image.read(address,len(new)) if old is None else old,new)
    native=bytearray(SIGNATURE-ARENA+64);native[:len(payload)]=payload
    native[-64:]=MAGIC+struct.pack('>II',ABI,len(payload))+digest+hashlib.sha256(b'OldSeed').digest()[:16]
    image.add_text(ARENA,native)
    class Backend:
        def read_bytes(self,address,size):
            if address==0x80000000:return (b'SNCP8P\0\0'+bytes(24))[:size]
            if address==0x80000007:return bytes(size)
            return read_dol_memory(image, address, size)
    from ..client.memory import SonicMemory
    memory=SonicMemory(Backend());memory.verify_revision()
    assert memory.native_patch['code_sha256']==digest.hex()
    assert not memory.native_patch['accessible_ring_colors']


def test_legacy_palette_encoding_is_unchanged():
    assert spawn.encode(['purple','blue','light_blue','red','purple'],False)==0x8139
    with pytest.raises(ValueError):spawn.encode(['gold']*5,False)
