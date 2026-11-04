from copy import deepcopy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from Options import Visibility, get_option_groups
from ..Options import Luma
from ..world import SonicColoursWorld
from ..Items import ITEM_TABLE
from ..client import red_ring_spawn as spawn
from ..client.item_colors import LUMA, item_color
from ..client.red_ring_colors import RedRingColors, reward_color, trap_color
from ..client.native_dol import Dol, patch_dol, plan
from ..client.memory import SonicMemory, MemoryUnavailable
from ..client.runtime import validate_slot
from ..client.client import slot_identity_digest
from . import generate


EXPECTED = {'progression':'#83D72F', 'useful':'#70218C',
            'filler':'#C66ADB', 'trap':'#30CFC9'}


def test_exact_palette_and_hidden_yaml_option():
    assert LUMA == EXPECTED
    assert spawn.LUMA_RGB[4:] == ((131,215,47),(112,33,140),(198,106,219),(48,207,201))
    assert Luma.visibility == Visibility.none and Luma.default == 0
    assert Luma.from_any(yaml.safe_load('luma: luma')['luma']).value == 1
    assert Luma.from_any('off').value == 0
    groups = get_option_groups(SonicColoursWorld)
    assert not any('luma' in group for group in groups.values())
    for path in (Path(__file__).parents[1] / 'examples').glob('*.yaml'):
        assert 'luma' not in yaml.safe_load(path.read_text())['Sonic Colours (Wii)']


@pytest.mark.parametrize('flags,label', [(0,'filler'),(1,'progression'),(2,'useful'),
                                        (3,'progression'),(4,'trap'),(5,'trap'),(7,'trap')])
@pytest.mark.parametrize('colorblind', [False,True])
def test_reward_mapping_and_palette_precedence(flags,label,colorblind):
    options = {'luma':1,'colorblind_mode':colorblind,'own_item_red_ring_colors':2}
    assert reward_color(1,2,flags,1,options,'Seed',100) == 'luma_' + label
    # Luma also overrides Colorblind Mode for item names in the HUD.
    from ..client import ap_hud_connected as hud
    from ..world_constants import load_data
    owner = {'handle':0x90001000,'boxes':{'ap_title':(2,0x2000)}}
    plain = hud.payloads(owner,[{'kind':'Received','item':'Test','player':'Other','flags':flags,'alpha':255}],
                         load_data('hud_glyph_metrics.json'),colorblind=colorblind,luma=True)
    assert plain[0x2090][:4] == bytes.fromhex(EXPECTED[label][1:]+'ff')


def test_own_items_unknown_rewards_and_forced_colors():
    options = {'luma':1,'own_item_red_ring_colors':0}
    assert reward_color(1,1,1,1,options,'Seed',100) == 'luma_progression'
    options['own_item_red_ring_colors'] = 1
    assert reward_color(ITEM_TABLE['Red Ring'],1,1,1,options,'Seed',100) == 'luma_progression'
    assert reward_color(ITEM_TABLE['Blue Cube Wisp'],1,1,1,options,'Seed',100) == 'luma_progression'
    data = generate({'luma':'luma'}).worlds[1].fill_slot_data()
    colors = RedRingColors(data,1,0)
    assert colors.stage_colors('stg110') == ('red',)*5
    data['options']['red_ring_item_colors'] = 0
    disabled = RedRingColors(data,1,0)
    disabled.receive([(1,1,2,1)])
    assert disabled.stage_colors('stg110') == ('red',)*5
    assert disabled.enabled and disabled.scout_message()['create_as_hint'] == 0


@pytest.mark.parametrize('own_mode',range(3))
@pytest.mark.parametrize('disguise',[0,1])
@pytest.mark.parametrize('master',[0,1])
def test_luma_overrides_all_ring_settings(own_mode,disguise,master):
    options = {'luma':1,'red_ring_item_colors':master,'colorblind_mode':1,
               'own_item_red_ring_colors':own_mode,'trap_red_ring_colors':disguise}
    for receiver in (1,2):
        for flags,name in ((0,'filler'),(1,'progression'),(2,'useful'),(3,'progression'),(4,'trap'),(7,'trap')):
            assert reward_color(ITEM_TABLE['Red Ring'],receiver,flags,1,options,'Seed',123) == 'luma_' + name
    world = generate(options).worlds[1]
    resolved = world.fill_slot_data()['options']
    assert resolved['red_ring_item_colors'] == 1
    assert resolved['own_item_red_ring_colors'] == 2
    assert resolved['trap_red_ring_colors'] == 0



@pytest.mark.parametrize('revision', [10,11,12,13])
def test_legacy_seed_and_journal_identity(revision):
    old = deepcopy(generate().worlds[1].fill_slot_data())
    old['options_revision'] = revision
    old['options'].pop('luma')
    if revision < 13: old['options'].pop('sixty_fps')
    if revision < 12: old['options'].pop('colorblind_mode')
    if revision < 11:
        for key in ('red_ring_item_colors','own_item_red_ring_colors','trap_red_ring_colors'):
            old['options'].pop(key)
    expected = slot_identity_digest(old)
    upgraded = validate_slot(old)
    assert upgraded['options']['luma'] == 0
    assert slot_identity_digest(upgraded) == expected
    assert slot_identity_digest(validate_slot(upgraded)) == expected


@pytest.mark.parametrize('colorblind', [False,True])
def test_palette_does_not_change_generation_or_normal_colors(colorblind):
    normal = generate({'colorblind_mode':colorblind},33,fill=True)
    luma = generate({'luma':'luma','colorblind_mode':colorblind},33,fill=True)
    assert normal.can_beat_game() and luma.can_beat_game()
    def items(multi):
        return [(loc.name,loc.item.name,loc.item.classification) for loc in multi.get_locations()]
    assert items(normal) == items(luma)
    assert normal.worlds[1].fill_slot_data()['locations'] == luma.worlds[1].fill_slot_data()['locations']
    options = normal.worlds[1].fill_slot_data()['options']
    disabled = {**options,'luma':0}
    for flags in range(8):
        assert reward_color(1,2,flags,1,options,'Seed',123) == reward_color(1,2,flags,1,disabled,'Seed',123)
    assert plan()[2].hex() == 'c93c8e318a2b66d0f09716d0b9628d42027ebe94c733914dc348355b62c3cfa6'


@pytest.mark.parametrize('checks', ['singles','per_level'])
def test_luma_patch_prefill_roundtrip(tmp_path,checks):
    from ..patch import load_patch
    multi = generate({'luma':'luma','red_ring_checks':checks,'own_item_red_ring_colors':2},22,fill=True)
    world = multi.worlds[1]
    world.generate_output(tmp_path)
    patch = load_patch(next(tmp_path.glob('*.apsoniccolours')))
    assert patch.slot_data['options']['luma'] == 1
    assert patch.ring_colors
    assert any(c.startswith('luma_') for row in patch.ring_colors.values() for c in row)
    for mission,row in patch.ring_colors.items():
        spawn.encode(row,luma=True)
    with pytest.raises(ValueError): spawn.validate_colors(patch.ring_colors)


@pytest.mark.parametrize('mission',['stg110','stg660'])
@pytest.mark.parametrize('color',range(4,8))
@pytest.mark.parametrize('ring',range(5))
def test_luma_native_constructor_keeps_material_and_registers(color,ring,mission):
    from .test_red_ring_spawn import test_native_spawn_executes_before_return_preserving_registers as execute
    execute(color,ring,mission,luma=True)


def test_luma_original_sdk_shading():
    from .test_red_ring_spawn import test_native_spawn_executes_before_return_preserving_registers as execute
    execute(4,0,'stg110',real_sdk=True,luma=True)


@pytest.mark.parametrize('sixty_fps', [False,True])
def test_private_luma_dol_validation_and_tamper_rejection(sixty_fps):
    source = Path('build/sonic_colours_reference/memdumps_and_more/main.dol')
    if not source.exists(): pytest.skip('private verified original main.dol absent')
    colors = {m:['red','luma_progression','luma_useful','luma_filler','luma_trap'] for m in spawn.missions()}
    data,registry = patch_dol(source.read_bytes(),'LumaTest',colors,{'luma':1,'sixty_fps':sixty_fps})
    image = Dol(data)
    class Backend:
        def read_bytes(self,address,size):
            if address == 0x80000000: return (b'SNCE8P'+bytes(26))[:size]
            if address == 0x80000007: return bytes(size)
            try: return image.read(address,size)
            except ValueError: return bytes(size)
    memory = SonicMemory(Backend())
    memory.verify_revision()
    assert memory.native_patch['luma_ring_colors']
    assert memory.native_patch['accessible_ring_colors']
    assert registry['native_sha256'] == memory.native_patch['code_sha256']
    for address,old,new in spawn.patches(luma=True):
        if new[:4] == bytes((131,215,47,0)):
            image.data[image.offset(address,8)] ^= 1
            break
    else: pytest.fail('missing Luma progression table row')
    with pytest.raises(MemoryUnavailable): memory.verify_revision()


def test_luma_publish_requires_matching_palette_and_scouts():
    data = generate({'luma':'luma','own_item_red_ring_colors':2}).worlds[1].fill_slot_data()
    colors = RedRingColors(data,1,0)
    colors.receive([(1,colors.locations['stg110',ring],2,flag) for ring,flag in enumerate((1,2,0,4,1),1)])
    cells = {}; writes = []
    memory = SimpleNamespace(error=MemoryUnavailable,native_patch={'red_ring_spawn':True,
        'accessible_ring_colors':True,'luma_ring_colors':True,
        'seed_digest':hashlib.sha256(data['seed_name'].encode()).digest()[:16].hex(),'code_sha256':'test'})
    memory.read_bytes = lambda a,n: cells.get(a,bytes(n))
    guard = SimpleNamespace(journal=SimpleNamespace(identity=dict(zip(('seed','team','slot'),colors.identity))))
    def write(a,value,expected,operation):
        assert expected == memory.read_bytes(a,len(value))
        spawn.authorize(memory,guard,a,len(value))
        cells[a] = value; writes.append(a)
    memory.write_bytes_verified = write
    runtime = SimpleNamespace(red_ring_colors=colors)
    spawn.publish(runtime,memory)
    address = spawn.layout()[1]['stg110']+2
    assert cells[address] == spawn.encode(colors.stage_colors('stg110'),luma=True).to_bytes(2,'big')
    count = len(writes)
    spawn.publish(runtime,memory)
    assert len(writes) == count
    memory.native_patch['luma_ring_colors'] = False
    spawn.publish(runtime,memory)
    assert len(writes) == count
    assert 'Repatch' in colors.renderer.status['reason']


def test_new_slot_requires_explicit_luma_and_rejects_invalid_values():
    data = generate().worlds[1].fill_slot_data()
    assert data['options_revision'] == 14 and data['options']['luma'] == 0
    missing = deepcopy(data)
    missing['options'].pop('luma')
    with pytest.raises(ValueError): validate_slot(missing)
    for value in (-1,2,'luma',True):
        bad = deepcopy(data)
        bad['options']['luma'] = value
        with pytest.raises(ValueError): validate_slot(bad)


def test_luma_constructor_rejects_partial_publication():
    from .test_red_ring_spawn import test_native_spawn_executes_before_return_preserving_registers as execute
    execute(4,0,'stg110',publish_race=True,luma=True)


def test_luma_encode_reuses_three_bit_entries_and_rejects_wrong_palette():
    row = ['red','luma_progression','luma_useful','luma_filler','luma_trap']
    encoded = spawn.encode(row,luma=True)
    assert encoded == spawn.encode(['red','gold','accessible_blue','gray','orange'])
    assert encoded <= 0xffff
    with pytest.raises(ValueError): spawn.encode(row)
    with pytest.raises(ValueError): spawn.encode(row,extended=False,luma=True)
    with pytest.raises(ValueError): spawn.encode(['gold']*5,luma=True)


@pytest.mark.parametrize('own',[False,True])
def test_luma_hud_changes_only_item_names(own):
    from ..client import ap_hud_connected as hud
    from ..world_constants import load_data
    owner = {'handle':0x90001000,'boxes':{'ap_prefix0':(1,0x1000),'ap_title':(2,0x2000),
              'ap_subtitle':(3,0x3000),'ap_subtitle_outline0':(4,0x4000)}}
    event = {'kind':'Received','item':'Test','player':'Player','flags':7,'own':own,'alpha':128}
    metrics = load_data('hud_glyph_metrics.json')
    plain = hud.payloads(owner,[event],metrics,colorblind=True)
    luma = hud.payloads(owner,[event],metrics,colorblind=True,luma=True)
    target = 0x3090 if own else 0x2090
    assert luma[target][:4] == bytes.fromhex('30cfc980')
    for address,value in luma.items():
        if address == target: assert value[4:] == plain[address][4:]
        else: assert value == plain[address]
