"""Read-only PAL GNCP/TLS audit for Sonic Colours AP HUD Codex handoff.

Usage: python asset_preflight_live.py /path/to/sonic2010_0.cpk
Requires cpk.py and verify_original_assets.py from prior audited handoff.
Does not modify assets or inject data.
"""
import collections
import hashlib
import json
import struct
import sys
from pathlib import Path
from hud_cpk import CPK
from hud_original_assets import find_asset,scene_by_name,cast_by_name,fonts,u32,pointer,text,EXPECTED_CPK

def scene_font_maps(blob,name):
    scene=scene_by_name(blob,name)
    sub=pointer(blob,scene+0x20)
    nsub=u32(blob,scene+0x1c)
    dictionary=pointer(blob,scene+0x30)
    casts=u32(blob,scene+0x2c)
    groups=pointer(blob,scene+0x28)
    ng=u32(blob,scene+0x24)
    out={}
    ft=pointer(blob,0x3c)
    ftable=pointer(blob,ft+4)
    fnames=pointer(blob,ft+8)
    fm={}
    for j in range(u32(blob,ft)):
        glyphcount=u32(blob,ftable+8*j)
        raw=pointer(blob,ftable+8*j+4)
        nm=text(blob,pointer(blob,fnames+8*j))
        fm[nm]=[(chr(u32(blob,raw+8*k)&255),u32(blob,raw+8*k+4)) for k in range(glyphcount)]
    for i in range(casts):
        entry=dictionary+12*i
        cname=text(blob,pointer(blob,entry))
        g,c=u32(blob,entry+4),u32(blob,entry+8)
        if g>=ng:raise ValueError('bad cast group')
        group=groups+g*16
        if c>=u32(blob,group):raise ValueError('bad cast index')
        rec=pointer(blob,pointer(blob,group+4)+c*4)
        if u32(blob,rec+4)!=2:continue
        fontname=text(blob,pointer(blob,rec+0x48))
        tex=collections.Counter()
        for ch,index in fm[fontname]:
            if index>=nsub:raise ValueError('invalid font subimage index')
            tex[u32(blob,sub+index*20)]+=1
        out[cname]={'font':fontname,'dimensions':[u32(blob,rec+0x50),u32(blob,rec+0x54)],
                    'glyphs':len(fm[fontname]),'texture_indexes':dict(tex)}
    return {'scene':name,'groups':ng,'casts':casts,'animations':u32(blob,scene+0x34),'font_casts':out}

def audit(path):
    path=Path(path)
    with path.open('rb') as fp:sha=hashlib.file_digest(fp,'sha256').hexdigest()
    if sha!=EXPECTED_CPK:raise ValueError('original CPK mismatch: '+sha)
    cpk=CPK(path)
    gp=find_asset(cpk,'ui_cockpit_e.arc','ui_gameplay.gncp')
    kb=find_asset(cpk,'ui_name_entry_e.arc','ui_soft_keyboard.gncp')
    gt=find_asset(cpk,'ui_cockpit_e.arc','ui_gameplay.tls')
    kt=find_asset(cpk,'ui_name_entry_e.arc','ui_soft_keyboard.tls')
    if u32(gt,0)!=0x0020af30 or u32(kt,0)!=0x0020af30:
        raise ValueError('unexpected TLS header; do not construct texture patch')
    if u32(gt,4)!=12 or u32(kt,4)!=4:
        raise ValueError('unexpected TLS texture count; inspect manually')
    if fonts(gp)['num_s']!='+-.0123456789:':raise ValueError('wrong gameplay font')
    if len(fonts(kb)['common_text'])!=77:raise ValueError('wrong keyboard font')
    bonus=scene_font_maps(gp,'info_bonus')
    kbscene=scene_font_maps(kb,'Scene_soft_keyboad_bg')
    sc=scene_font_maps(gp,'info_2')
    assert bonus['font_casts']['num_bonus']['texture_indexes']=={6:14}
    assert kbscene['font_casts']['text_01']['texture_indexes']=={3:77}
    assert sc['font_casts']['num_score']['texture_indexes']=={6:14}
    return {'cpk_sha256':sha,'ui_gameplay_tls':{'bytes':len(gt),'texture_count':u32(gt,4)},
            'ui_soft_keyboard_tls':{'bytes':len(kt),'texture_count':u32(kt,4)},
            'gameplay_alphabetic_font_loaded':False,'keyboard_font_chars':fonts(kb)['common_text'],
            'bonus':bonus,'always_on_candidate':sc,
            'keyboard_reference':{'scene':kbscene['scene'],'text_01':kbscene['font_casts']['text_01']},
            'no_runtime_rendering_claim':True}

if __name__=='__main__':
    try:print(json.dumps(audit(sys.argv[1]),indent=2,ensure_ascii=False))
    except Exception as error:
        print('PREFLIGHT FAILED:',error,file=sys.stderr)
        raise
