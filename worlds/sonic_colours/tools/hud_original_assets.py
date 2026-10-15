"""Read-only validation of Sonic Colours Wii PAL HUD asset evidence.

Usage: python verify_original_assets.py /path/to/sonic2010_0.cpk

Does not modify the game, extract font files or emit proprietary assets.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path
try:from .hud_cpk import CPK
except ImportError:from hud_cpk import CPK

BASE = 0x20
EXPECTED_CPK = '58bbf2be97a2f08effb5752bd40eea8a1ba76a18349937a32351624d855651bf'


def u32(b, off):
    if off < 0 or off+4 > len(b):
        raise ValueError(f'out-of-range field 0x{off:x}')
    return struct.unpack_from('>I', b, off)[0]


def pointer(b, off):
    val=u32(b,off)
    return BASE+val if val else None


def text(b, off):
    if off is None: return None
    end=b.find(b'\x00',off)
    if off>=len(b) or end<off: raise ValueError(f'bad GNCP string at {off}')
    return b[off:end].decode('ascii')


def u8_members(arc):
    if arc[:4] != bytes.fromhex('55aa382d'): raise ValueError('not a U8 archive')
    fst=u32(arc,4); count=u32(arc,fst+8); strings=fst+count*12
    if count>10000 or strings>=len(arc): raise ValueError('bad U8 directory')
    for j in range(1,count):
        pos=fst+12*j; spec=u32(arc,pos)
        if spec>>24:continue
        name=text(arc,strings+(spec&0xffffff))
        data=u32(arc,pos+4); size=u32(arc,pos+8)
        if data+size>len(arc): raise ValueError('bad U8 file bounds')
        yield name, arc[data:data+size]


def scene_by_name(b, wanted):
    if b[:4]!=b'NGIF' or b[0x20:0x24]!=b'nCPJ':raise ValueError('not a GNCP asset')
    root=pointer(b,BASE+0x10)
    count=u32(b,root); offset_table=pointer(b,root+4); names=pointer(b,root+8)
    if count>100:return None
    for i in range(count):
        if text(b,pointer(b,names+8*i))==wanted:
            return pointer(b,offset_table+4*i)
    raise ValueError(f'scene not found: {wanted}')


def cast_by_name(b, scene, wanted):
    groups=pointer(b,scene+0x28);ngroups=u32(b,scene+0x24)
    dictionary=pointer(b,scene+0x30); count=u32(b,scene+0x2c)
    for j in range(count):
        row=dictionary+12*j
        if text(b,pointer(b,row))!=wanted: continue
        group=u32(b,row+4);cast=u32(b,row+8)
        if group>=ngroups:raise ValueError('invalid GNCP cast group')
        g=groups+16*group
        if cast>=u32(b,g):raise ValueError('invalid GNCP cast index')
        cptr=pointer(b,g+4)
        return pointer(b,cptr+4*cast)
    raise ValueError(f'cast not found: {wanted}')


def fonts(b):
    root=pointer(b,BASE+0x1c)
    count=u32(b,root);ft=pointer(b,root+4);names=pointer(b,root+8)
    result={}
    for j in range(count):
        n=u32(b,ft+8*j);rows=pointer(b,ft+8*j+4)
        name=text(b,pointer(b,names+8*j))
        if n>1024:raise ValueError('suspicious glyph count')
        result[name]=''.join(chr(u32(b,rows+8*k)&255) for k in range(n))
    return result


def find_asset(cpk, arc_name, member):
    rows=[row for row in cpk.toc.rows if row.get('DirName')=='ui' and row.get('FileName')==arc_name]
    if not rows:raise ValueError(f'CPK missing {arc_name}')
    for row in rows:
        arc=cpk.read(row)
        for name,contents in u8_members(arc):
            if name==member:return contents
    raise ValueError(f'{arc_name} missing {member}')


def inspect(cpk):
    b=find_asset(cpk,'ui_cockpit_e.arc','ui_gameplay.gncp')
    sc=scene_by_name(b,'info_bonus')
    word=cast_by_name(b,sc,'word_bonus');number=cast_by_name(b,sc,'num_bonus')
    scene_fonts=fonts(b)
    assert sc == 0x228, hex(sc)
    assert number==0x7cd4 and word==0x7d48
    assert u32(b,word+4)==1 and u32(b,number+4)==2
    assert text(b,pointer(b,number+0x48))=='num_s'
    assert scene_fonts['num_s']=='+-.0123456789:'
    assert (u32(b,number+0x50),u32(b,number+0x54))==(64,10)
    assert (u32(b,word+0x50),u32(b,word+0x54))==(200,24)
    subimages=pointer(b,sc+0x20)
    sprite_material=pointer(b,word+0x40)
    subimage_idx=u32(b,sprite_material)
    assert subimage_idx==78
    real_sprite_texture=u32(b,subimages+subimage_idx*20)
    assert real_sprite_texture==8
    num_font_rows=pointer(b, pointer(b,BASE+0x1c)+4)
    # 'num_s' mappings are known scene subimage 60..73.
    numeric_texture=u32(b,subimages+60*20)
    assert numeric_texture==6
    kb=find_asset(cpk,'ui_name_entry_e.arc','ui_soft_keyboard.gncp')
    common=fonts(kb)['common_text']
    assert len(common)==77 and all(x in common for x in 'Sent Progressive Keyto SM64 Player')
    return {'scene':'info_bonus','scene_offset':sc,
            'word_bonus':{'type':'sprite','record_offset':word,'subimage':subimage_idx,'texture':real_sprite_texture,'width':200,'height':24},
            'num_bonus':{'type':'font','record_offset':number,'font':'num_s','charset':scene_fonts['num_s'],'texture':numeric_texture,'width':64,'height':10},
            'other_alphabet_font':{'asset':'ui_name_entry_e.arc/ui_soft_keyboard.gncp','name':'common_text','charset_length':len(common),'charset':common},
            'live_dolphin_verified':False}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('cpk',type=Path)
    p.add_argument('--skip-hash',action='store_true',help='only if original file is known unmodified')
    a=p.parse_args()
    if not a.skip_hash:
        with a.cpk.open('rb') as f: digest=hashlib.file_digest(f,'sha256').hexdigest()
        if digest!=EXPECTED_CPK:raise SystemExit(f'CPK hash mismatch: {digest}')
    result=inspect(CPK(a.cpk))
    print(json.dumps(result,indent=2,ensure_ascii=False))

if __name__=='__main__':main()
