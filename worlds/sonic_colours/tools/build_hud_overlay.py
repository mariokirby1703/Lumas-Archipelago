"""Build a private PAL static HUD PoC archive, never modify original CPK."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys
import os
import shutil
import tempfile
import xml.etree.ElementTree as ET
try:
    from .hud_tpl import append_texture,textures
    from .hud_gncp import overlay,SAMPLE_MESSAGES
    from .hud_cpk import CPK
    from .hud_original_assets import find_asset,EXPECTED_CPK,u8_members
    from .hud_preflight import audit
except ImportError:
    from hud_tpl import append_texture,textures
    from hud_gncp import overlay,SAMPLE_MESSAGES
    from hud_cpk import CPK
    from hud_original_assets import find_asset,EXPECTED_CPK,u8_members
    from hud_preflight import audit


def riivolution_xml(archive_name,ap_connected=False):
    if Path(archive_name).name!=archive_name:raise ValueError('archive must be beside XML')
    root=ET.Element('wiidisc',version='1')
    ident=ET.SubElement(root,'id',game='SNC',developer='8P',disc='0',version='0')
    ET.SubElement(ident,'region',type='P')
    section=ET.SubElement(ET.SubElement(root,'options'),'section',name='Archipelago HUD test')
    option=ET.SubElement(section,'option',id='ap_hud_connected' if ap_connected else 'ap_hud_static_poc',name='AP Item HUD' if ap_connected else 'Static HUD PoC',default='0')
    ET.SubElement(ET.SubElement(option,'choice',name='Enabled'),'patch',id='ap_hud_assets')
    patch=ET.SubElement(root,'patch',id='ap_hud_assets')
    ET.SubElement(patch,'file',disc='/sonic2010_0.cpk',external=archive_name,resize='true',create='false')
    import importlib.util
    path=Path(__file__).resolve().parents[1]/'client'/'hud_renderer_batch.py'
    spec=importlib.util.spec_from_file_location('hud_batch_patch',path)
    guard=importlib.util.module_from_spec(spec);spec.loader.exec_module(guard)
    ET.SubElement(patch,'memory',offset=hex(guard.ADDRESS),original=guard.ORIGINAL_HEX,
                  value=guard.replacement().hex())
    if ap_connected:
        path=Path(__file__).resolve().parents[1]/'client'/'ap_hud_publisher.py'
        spec=importlib.util.spec_from_file_location('hud_publisher_patch',path)
        publisher=importlib.util.module_from_spec(spec);spec.loader.exec_module(publisher)
        for address,old,new in publisher.patches():
            ET.SubElement(patch,'memory',offset=hex(address),original=old.hex(),value=new.hex())
        path=Path(__file__).resolve().parents[1]/'client'/'rocket_skydiving.py'
        spec=importlib.util.spec_from_file_location('rocket_skydiving_patch',path)
        rocket=importlib.util.module_from_spec(spec);spec.loader.exec_module(rocket)
        for address,old,new in rocket.patches():
            ET.SubElement(patch,'memory',offset=hex(address),original=old.hex(),value=new.hex())
    ET.indent(root)
    return '<?xml version="1.0" encoding="utf-8"?>\n'+ET.tostring(root,encoding='unicode')+'\n'


def publish_aliases(cpk,output,indices,replacement,expected_sha):
    output=Path(output)
    if output.exists() or output.resolve()==cpk.path.resolve():raise ValueError('output must be new')
    with cpk.path.open('rb') as f:
        if hashlib.file_digest(f,'sha256').hexdigest()!=expected_sha:raise ValueError('original hash mismatch')
    row=cpk.header.rows[0]
    if row['Align']!=2048 or row['TocCrc'] or row.get('GtocCrc',0):raise ValueError('unsupported CPK header')
    header=bytearray(cpk.header.data);toc=bytearray(cpk.toc.data)
    append=(cpk.path.stat().st_size+2047)//2048*2048
    def cell(blob,cells,key,value):
        pos,fmt=cells[key]
        if pos is None:raise ValueError('constant CPK field')
        struct.pack_into(fmt,blob,pos,value)
    packed=0;unpacked=0;chunks=[];offsets={};cursor=append
    for i in indices:
        blob=replacement[i] if isinstance(replacement,dict) else replacement
        digest=hashlib.sha256(blob).digest()
        if digest not in offsets:
            cursor=(cursor+2047)//2048*2048;offsets[digest]=cursor
            chunks.append((cursor,blob));cursor+=len(blob)
        position=offsets[digest]
        old=cpk.toc.rows[i];packed+=len(blob)-old['FileSize'];unpacked+=len(blob)-old['ExtractSize']
        for key,value in [('FileOffset',position-cpk.content_base),('FileSize',len(blob)),('ExtractSize',len(blob))]:
            cell(toc,cpk.toc.cells[i],key,value)
    for key,value in [('ContentSize',cursor-row['ContentOffset']),
                      ('EnabledPackedSize',row['EnabledPackedSize']+packed),
                      ('EnabledDataSize',row['EnabledDataSize']+unpacked)]:
        cell(header,cpk.header.cells[0],key,value)
    output.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix='.hud-cpk-',dir=output.parent)
    try:
        with os.fdopen(fd,'w+b') as f,cpk.path.open('rb') as source:
            shutil.copyfileobj(source,f,1024*1024)
            for position,blob in chunks:
                f.write(b'\0'*(position-f.tell()));f.write(blob)
            f.seek(16);f.write(header);f.seek(cpk.toc_offset+16);f.write(toc)
            f.flush();os.fsync(f.fileno())
        os.rename(tmp,output)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)


def replace_u8(arc,replacements):
    if arc[:4]!=bytes.fromhex('55aa382d'):raise ValueError('not U8')
    u=lambda o:struct.unpack_from('>I',arc,o)[0]
    fst=u(4);count=u(fst+8);strings=fst+count*12;out=bytearray(arc);found=set()
    for i in range(1,count):
        row=fst+12*i;spec=u(row)
        if spec>>24:continue
        namepos=strings+(spec&0xffffff);name=arc[namepos:arc.index(0,namepos)].decode('ascii')
        if name not in replacements:continue
        if name in found:raise ValueError('duplicate U8 target')
        found.add(name);blob=replacements[name]
        out.extend(b'\0'*((-len(out))%32));offset=len(out);out.extend(blob)
        struct.pack_into('>II',out,row+4,offset,len(blob))
    if found!=set(replacements):raise ValueError('missing U8 target')
    return bytes(out)


def build(source,output,message_count=5,compact_glyphs=True,include_maps=False,ap_connected=False,music_mapping=None,write_xml=True,music_mapping_version=1):
    report=audit(source);cpk=CPK(source)
    resources={n:find_asset(cpk,arc,n) for arc,n in
        [('ui_cockpit_e.arc','ui_gameplay.gncp'),('ui_cockpit_e.arc','ui_gameplay.tls'),
         ('ui_name_entry_e.arc','ui_soft_keyboard.gncp'),('ui_name_entry_e.arc','ui_soft_keyboard.tls')]}
    replacements={'ui_gameplay.gncp':overlay(resources['ui_gameplay.gncp'],resources['ui_soft_keyboard.gncp'],
                                           keyboard_tls=resources['ui_soft_keyboard.tls'] if compact_glyphs else None,
                                           messages=SAMPLE_MESSAGES[:message_count],ap_connected=ap_connected),
                  'ui_gameplay.tls':append_texture(resources['ui_gameplay.tls'],resources['ui_soft_keyboard.tls'],3)}
    candidates=[i for i,r in enumerate(cpk.toc.rows) if r.get('DirName')=='ui' and r.get('FileName')=='ui_cockpit_e.arc']
    if not candidates:raise ValueError('cockpit archive missing')
    index=candidates[0];original=cpk.read(cpk.toc.rows[index]);patched=replace_u8(original,replacements)
    if any(cpk.read(cpk.toc.rows[i])!=original for i in candidates):raise ValueError('cockpit aliases differ')
    before=dict(u8_members(original));after=dict(u8_members(patched))
    if before.keys()!=after.keys():raise ValueError('U8 member set changed')
    for name,blob in before.items():
        if after[name]!=(replacements.get(name,blob)):raise ValueError('U8 roundtrip differs')
    changes={i:patched for i in candidates}
    if ap_connected:
        multi_gncp=find_asset(cpk,'ui_cockpit_multi_e.arc','ui_gameplay_multi.gncp')
        multi_tls=find_asset(cpk,'ui_cockpit_multi_e.arc','ui_gameplay_multi.tls')
        multi_replacements={
            'ui_gameplay_multi.gncp':overlay(multi_gncp,resources['ui_soft_keyboard.gncp'],
                texture_index=len(textures(multi_tls)),keyboard_tls=resources['ui_soft_keyboard.tls'],
                messages=SAMPLE_MESSAGES[:message_count],scene_name='info_1',base_y=140.,ap_connected=True,
                music_y_offset=-45.),
            'ui_gameplay_multi.tls':append_texture(multi_tls,resources['ui_soft_keyboard.tls'],3)}
        multi_indices=[i for i,r in enumerate(cpk.toc.rows) if r.get('DirName')=='ui' and r.get('FileName')=='ui_cockpit_multi_e.arc']
        original_multi=cpk.read(cpk.toc.rows[multi_indices[0]])
        if any(cpk.read(cpk.toc.rows[i])!=original_multi for i in multi_indices):raise ValueError('Game Land cockpit aliases differ')
        multi_patch=replace_u8(original_multi,multi_replacements)
        before_multi=dict(u8_members(original_multi));after_multi=dict(u8_members(multi_patch))
        if before_multi.keys()!=after_multi.keys() or any(after_multi[n]!=multi_replacements.get(n,b) for n,b in before_multi.items()):
            raise ValueError('Game Land U8 roundtrip differs')
        changes.update({i:multi_patch for i in multi_indices})
        # These screens use separate native resources from gameplay/maps.
        # The background is behind the opaque cabinet artwork. Attach AP
        # casts to the frame itself so they draw after its decorative quads.
        for arc,stem,scene_name in (('ui_title_multi_e.arc','ui_title_multi','multi_frame'),
                                    ('ui_file_select_e.arc','ui_file_select','Scene_GameData'),
                                    ('ui_result_e.arc','ui_result','result')):
            gncp=find_asset(cpk,arc,stem+'.gncp');tls=find_asset(cpk,arc,stem+'.tls')
            additions={stem+'.gncp':overlay(gncp,resources['ui_soft_keyboard.gncp'],
                texture_index=len(textures(tls)),keyboard_tls=resources['ui_soft_keyboard.tls'],
                messages=SAMPLE_MESSAGES[:message_count],scene_name=scene_name,
                base_y=0. if scene_name=='result' else 176.,ap_connected=True,
                music_y_offset=-110. if scene_name=='result' else 0.),
                stem+'.tls':append_texture(tls,resources['ui_soft_keyboard.tls'],3)}
            indices=[i for i,r in enumerate(cpk.toc.rows) if r.get('DirName')=='ui' and r.get('FileName')==arc]
            original=cpk.read(cpk.toc.rows[indices[0]])
            if any(cpk.read(cpk.toc.rows[i])!=original for i in indices):raise ValueError(arc+' aliases differ')
            modified=replace_u8(original,additions)
            before=dict(u8_members(original));after=dict(u8_members(modified))
            if before.keys()!=after.keys() or any(after[n]!=additions.get(n,b) for n,b in before.items()):
                raise ValueError(arc+' U8 roundtrip differs')
            changes.update({i:modified for i in indices})
    if include_maps:
        map_gncp=find_asset(cpk,'ui_worldmap_e.arc','ui_worldmap.gncp')
        map_tls=find_asset(cpk,'ui_worldmap_e.arc','ui_worldmap.tls')
        replacements_map={
            'ui_worldmap.gncp':overlay(map_gncp,resources['ui_soft_keyboard.gncp'],
                texture_index=len(textures(map_tls)),keyboard_tls=resources['ui_soft_keyboard.tls'],
                messages=SAMPLE_MESSAGES[:message_count],scene_name='info_1',base_y=176.,ap_connected=ap_connected),
            'ui_worldmap.tls':append_texture(map_tls,resources['ui_soft_keyboard.tls'],3)}
        map_indices=[i for i,r in enumerate(cpk.toc.rows) if r.get('DirName')=='ui' and r.get('FileName')=='ui_worldmap_e.arc']
        if not map_indices:raise ValueError('map archive missing')
        original_map=cpk.read(cpk.toc.rows[map_indices[0]])
        if any(cpk.read(cpk.toc.rows[i])!=original_map for i in map_indices):raise ValueError('map aliases differ')
        map_patch=replace_u8(original_map,replacements_map)
        before_map=dict(u8_members(original_map));after_map=dict(u8_members(map_patch))
        if before_map.keys()!=after_map.keys():raise ValueError('map U8 members differ')
        if any(after_map[n]!=replacements_map.get(n,b) for n,b in before_map.items()):raise ValueError('map U8 roundtrip differs')
        changes.update({i:map_patch for i in map_indices})
    if music_mapping is not None:
        from ..client.music_bank import rewrite_bank
        music_indices=[i for i,r in enumerate(cpk.toc.rows) if r.get('DirName')=='sound' and r.get('FileName')=='bgm.strm.csb']
        if len(music_indices)!=1:raise ValueError('BGM bank not unique')
        index=music_indices[0]
        changes[index]=rewrite_bank(cpk.read(cpk.toc.rows[index]),music_mapping,mapping_version=music_mapping_version)
    publish_aliases(cpk,output,list(changes),changes,EXPECTED_CPK)
    rebuilt=CPK(output)
    if any(rebuilt.read(rebuilt.toc.rows[i])!=blob for i,blob in changes.items()):raise ValueError('CPK roundtrip differs')
    report.update(static_overlay_built=True,native_renderer_installed=False,live_verified=False,
                  message_count=message_count,compact_glyphs=compact_glyphs,map_overlay_built=include_maps,ap_connected_assets=ap_connected,
                  new_texture_count=len(textures(replacements['ui_gameplay.tls'])),patched_aliases=len(changes),
                  output=str(output),resources={n:hashlib.sha256(b).hexdigest() for n,b in replacements.items()})
    Path(str(output)+'.hud.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    if write_xml:Path(output).with_suffix('.xml').write_text(riivolution_xml(Path(output).name,ap_connected),encoding='utf-8')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',type=Path);p.add_argument('output',type=Path)
    p.add_argument('--messages',type=int,choices=[1,5],default=5)
    p.add_argument('--keep-glyph-cells',action='store_true')
    p.add_argument('--maps',action='store_true')
    p.add_argument('--ap-connected',action='store_true')
    a=p.parse_args();print(json.dumps(build(a.source,a.output,a.messages,not a.keep_glyph_cells,a.maps,a.ap_connected),indent=2))
