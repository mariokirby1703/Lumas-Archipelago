"""Inventory extracted popup calls and pinned PE action handlers; read-only."""
import csv
import hashlib
import json
from pathlib import Path
import re
import struct
from inspect_game import inspect_pe

WORLD=Path(__file__).resolve().parents[1]
ACTIONS=('UnlockSequence','UnlockSequenceAndAnim',
    'UI_SetMissionMessage','UI_SetMissionHelpText','UI_RemoveMissionMessage','UI_RemoveMissionHelpText',
    'UI_ShowObjectiveScreen','UI_ShowMissionPrompt','UI_ShowSummaryScreen','UI_ShowLevelSummaryScreen',
    'SetHint','CancelHint','SetHintIconDRC','PrintToScreen','UI_ShowMapUnlock','AwardCharacter','CommitCollectables')


def uncomment(text):
    return re.sub(r'"(?:\\.|[^"\\])*"|//[^\n]*|/\*.*?\*/',
                  lambda m:m.group() if m.group().startswith('"') else '\n'*m.group().count('\n'),text,flags=re.S)


def research():
    extracted=WORLD/'notes/extracted';scripts=sorted(extracted.rglob('*.sf'))
    rows={name:dict(name=name,calls=[],native_handlers=[]) for name in ACTIONS}
    names={name.casefold():name for name in ACTIONS}
    for path in scripts:
        text=uncomment(path.read_text(errors='replace'))
        for m in re.finditer(r'\b([A-Za-z_]\w*)\s*\(',text):
            name=names.get(m.group(1).casefold())
            if name:
                rows[name]['calls'].append(dict(resource=path.relative_to(extracted).as_posix(),
                    line=text.count('\n',0,m.start())+1,example=text[m.start():m.start()+250].split(';')[0].replace('\n',' ')))
    data=(WORLD/'notes/gamefiles/LEGOLCUR_DX11.exe').read_bytes();pe=inspect_pe(data);base=int(pe['image_base'],16)
    def offset_rva(offset):
        s=next(s for s in pe['sections'] if s['raw_offset']<=offset<s['raw_offset']+s['raw_size'])
        return s['rva']+offset-s['raw_offset']
    strings=json.loads((WORLD/'notes/analysis/LEGOLCUR_DX11.exe.strings.json').read_text())
    targets={base+offset_rva(r['offset']):r['text'] for r in strings if r['text'] in rows}
    section=next(s for s in pe['sections'] if s['name']=='.text')
    raw=data[section['raw_offset']:section['raw_offset']+section['raw_size']]
    for i in range(len(raw)-8):
        if raw[i] not in (0x48,0x4c) or raw[i+1]!=0x8d or raw[i+2]&0xc7!=5 or raw[i+7]!=0xc3:continue
        getter=base+section['rva']+i;target=getter+7+struct.unpack_from('<i',raw,i+3)[0]
        if target not in targets:continue
        hit=0
        while (hit:=data.find(struct.pack('<Q',getter),hit))>=0:
            if hit+32<=len(data):
                candidate=struct.unpack_from('<Q',data,hit+24)[0]-base
                if section['rva']<=candidate<section['rva']+section['raw_size']:
                    rows[targets[target]]['native_handlers'].append(dict(getter_rva=hex(getter-base),
                        table_rva=hex(offset_rva(hit)-8),handler_rva=hex(candidate),calling_interface='script context; not a callable text API'))
            hit+=8
    report=dict(executable_sha256=hashlib.sha256(data).hexdigest(),scripts_scanned=len(scripts),
                scope='all extracted .sf files plus native action name-getter/table references; not exhaustive live popup coverage',
                live_calls_performed=False,actions=list(rows.values()))
    out=WORLD/'notes/analysis/popup_systems';out.mkdir(exist_ok=True)
    (out/'catalogue.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    with (out/'calls.csv').open('w',newline='',encoding='utf-8') as f:
        wr=csv.writer(f);wr.writerow(('action','resource','line','example'))
        for row in rows.values():
            for call in row['calls']:wr.writerow((row['name'],call['resource'],call['line'],call['example']))
    print('Scanned',len(scripts),'scripts; no game functions invoked')
    for row in rows.values():print(row['name'],len(row['calls']),[r['handler_rva'] for r in row['native_handlers']])
    return report


if __name__=='__main__':research()
