import importlib.util
from pathlib import Path
import struct
import sys
import pytest

TOOLS=Path(__file__).resolve().parents[1]/'tools'
def module(name):
    spec=importlib.util.spec_from_file_location(name,TOOLS/(name+'.py'))
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


def tpl():
    b=bytearray(128);struct.pack_into('>IIIII',b,0,0x20af30,1,12,20,0)
    struct.pack_into('>HHII',b,20,8,8,2,64)
    b[64:128]=bytes(range(64));return bytes(b)


def test_tls_import_keeps_original_pixels_and_indices():
    m=module('hud_tpl');original=tpl();new=m.append_texture(original,original,0)
    assert len(m.textures(new))==2
    assert new[12:len(original)]==original[12:]
    t=m.textures(new)[1];assert new[t['data']:t['data']+t['size']]==original[64:]
    with pytest.raises(ValueError):m.append_texture(original,original,1)
    damaged=bytearray(original);struct.pack_into('>I',damaged,28,65)
    with pytest.raises(ValueError):m.textures(damaged)

def test_game_land_overlay_preserves_other_native_scenes(monkeypatch):
    monkeypatch.syspath_prepend(str(TOOLS))
    source=Path(__file__).parents[1]/'notes/memdumps_and_more/sonic2010_0.cpk'
    if not source.exists():pytest.skip('private original CPK absent')
    cpk=module('hud_cpk').CPK(source);assets=module('hud_original_assets');m=module('hud_gncp')
    original=assets.find_asset(cpk,'ui_cockpit_multi_e.arc','ui_gameplay_multi.gncp')
    keyboard=assets.find_asset(cpk,'ui_name_entry_e.arc','ui_soft_keyboard.gncp')
    tls=assets.find_asset(cpk,'ui_name_entry_e.arc','ui_soft_keyboard.tls')
    new=m.overlay(original,keyboard,texture_index=13,keyboard_tls=tls,scene_name='info_1',ap_connected=True)
    scene=m.scene(new,'info_1')
    assert m.u(new,scene+44)==96 and m.u(new,scene+36)==7
    for name in ('info_2','info_bonus','info_1_2p'):
        old=m.scene(original,name)
        assert new[old:old+76]==original[old:old+76]
    for name in ('ap_title','ap_subtitle'):
        record=m.cast(new,scene,name);box=m.ptr(new,record+64)
        assert m.u(new,box+152)==0x41504d42


def test_owned_original_gncp_roundtrip_if_available():
    root=Path(__file__).resolve().parents[3]/'build'/'ap_hud_assets'
    if not root.exists():pytest.skip('private original resources not supplied')
    m=module('hud_gncp');a=(root/'ui_gameplay.gncp').read_bytes();b=(root/'ui_soft_keyboard.gncp').read_bytes()
    tls=(root/'ui_soft_keyboard.tls').read_bytes();new=m.overlay(a,b,keyboard_tls=tls);s=m.scene(a,'info_2');bonus=m.scene(a,'info_bonus')
    assert new[bonus:bonus+76]==a[bonus:bonus+76]
    assert m.u(new,s+36)==8 and m.u(new,s+44)==103 and m.u(new,s+20)==13
    for name in ('num_score','word_score'):
        try:old=m.cast(a,s,name)
        except ValueError:continue
        assert m.cast(new,s,name)==old and new[old:old+116]==a[old:old+116]
    for i,name in enumerate(('ap_title','ap_subtitle')):
        c=m.cast(new,s,name);assert m.u(new,c+4)==2
        assert m.string(new,m.ptr(new,c+72))=='ap_common_text'
        info=m.ptr(new,c+48)
        assert struct.unpack_from('>ff',new,info+16)==pytest.approx((0.45,0.45))
        x,y=struct.unpack_from('>ff',new,c+104)
        assert y==140.+i*17. and x>=m.HUD_LEFT
        assert m.u(new,info+0x1c)==(0xAF70FFFF if i==0 else 0xffffffff)
        assert struct.unpack_from('>f',new,c+12)[0]==0.
    # Native 805DE874 uses bsearch for font names, as does cast lookup.
    # A linear parser alone would miss an appended, unsorted dictionary.
    for table,count,stride in [(m.ptr(new,s+48),103,12),
                               (m.ptr(new,m.ptr(new,60)+8),3,8)]:
        names=[m.string(new,m.ptr(new,table+i*stride)) for i in range(count)]
        assert names==sorted(names)
        for wanted in names:
            lo=0;hi=len(names)
            while lo<hi:
                mid=(lo+hi)//2
                if names[mid]<wanted:lo=mid+1
                else:hi=mid
            assert names[lo]==wanted
    assert new==m.overlay(a,b,keyboard_tls=tls)

    for message in range(5):
        for line,name in enumerate(('ap_title','ap_subtitle')):
            c=m.cast(new,s,name+('_'+str(message) if message else ''))
            assert m.string(new,m.ptr(new,c+68))==(m.SAMPLE_MESSAGES[message][line].split(' ',1)[1] if line==0 else m.SAMPLE_MESSAGES[message][line])
            assert struct.unpack_from('>ff',new,c+104)[1]==140.+message*40.+line*17.
    # Every cropped non-space cell retains opaque source columns and baseline.
    source_scene=m.scene(b,'Scene_soft_keyboad_bg');target_sub=m.ptr(new,s+32)
    old_count=m.u(a,s+28)
    ft=m.ptr(b,60);mapping=m.ptr(b,m.ptr(b,ft+4)+4);source_sub=m.ptr(b,source_scene+32)
    for i in range(77):
        index=m.u(b,mapping+8*i+4)
        original=struct.unpack_from('>ffff',b,source_sub+index*20+4)
        cropped=struct.unpack_from('>ffff',new,target_sub+(old_count+i)*20+4)
        assert cropped[1]==original[1] and cropped[3]==original[3]
        assert cropped[2]-cropped[0]<=original[2]-original[0]+1e-7

    groups=m.ptr(new,s+40);animation=m.ptr(new,s+56)
    assert m.u(new,animation)==8
    animation_groups=m.ptr(new,animation+4)
    for i in range(2,7):
        assert m.u(new,groups+i*16)==15
        assert m.u(new,animation_groups+i*8)==15
        tree=m.ptr(new,groups+i*16+12)
        assert struct.unpack_from('>ii',new,tree)==(-1,1)
        assert struct.unpack_from('>ii',new,tree+14*8)==(-1,-1)

def test_owned_map_parent_preserves_original_ring_and_rank_casts():
    root=Path(__file__).resolve().parents[3]/'build'/'ap_hud_assets'
    if not (root/'ui_worldmap.gncp').exists():pytest.skip('private map resource not supplied')
    m=module('hud_gncp');a=(root/'ui_worldmap.gncp').read_bytes()
    keyboard=(root/'ui_soft_keyboard.gncp').read_bytes();tls=(root/'ui_soft_keyboard.tls').read_bytes()
    new=m.overlay(a,keyboard,texture_index=13,keyboard_tls=tls,scene_name='info_1',base_y=176.)
    parent=m.scene(a,'info_1')
    assert m.u(new,parent+36)==9 and m.u(new,parent+44)==111 and m.u(new,parent+20)==14
    for name in ('num_life','num_rank','num_ring'):
        old=m.cast(a,parent,name)
        assert m.cast(new,parent,name)==old and new[old:old+116]==a[old:old+116]
    for message in range(5):
        c=m.cast(new,parent,'ap_subtitle'+('_'+str(message) if message else ''))
        assert struct.unpack_from('>ff',new,c+104)==(m.HUD_LEFT,193.+message*40.)

def test_connected_assets_start_blank_with_bounded_shared_mailboxes():
    root=Path(__file__).resolve().parents[3]/'build'/'ap_hud_assets'
    if not root.exists():pytest.skip('private source assets not supplied')
    m=module('hud_gncp');a=(root/'ui_gameplay.gncp').read_bytes();b=(root/'ui_soft_keyboard.gncp').read_bytes()
    new=m.overlay(a,b,keyboard_tls=(root/'ui_soft_keyboard.tls').read_bytes(),ap_connected=True)
    parent=m.scene(new,'info_2');dictionary=m.ptr(new,parent+48);controls=set()
    for i in range(m.u(new,parent+44)):
        name=m.string(new,m.ptr(new,dictionary+i*12))
        if not name.startswith('ap_'):continue
        record=m.cast(new,parent,name);box=m.ptr(new,record+64)
        assert m.string(new,m.ptr(new,record+68))==' '
        assert m.u(new,box)==0 and m.u(new,box+152)==0x41504d42
        assert m.string(new,m.ptr(new,box+12))==name
        assert new[box+16:box+144]==b' '+b'\0'*127
        assert m.u(new,box+8)==0
        controller=m.ptr(new,box+4);controls.add(controller)
        assert [m.u(new,controller+j*4) for j in range(4)]==[0x41504844,0,128,90]
        info=m.ptr(new,record+48)
        assert m.u(new,info+0x20)==(0x000000ff if '_outline' in name else 0xffffffff)
    assert len(controls)==1
