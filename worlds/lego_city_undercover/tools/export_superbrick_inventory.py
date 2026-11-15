"""Export EVERY indexed type 80/106 source, including excluded templates and tests."""
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import sys

WORLD=Path(__file__).resolve().parents[1]
ROOT=WORLD.parents[1]
sys.path.insert(0,str(WORLD/'bridge'))
from area_passes import canonical


def main():
    path=WORLD/'notes/analysis/pickup_catalogue.json'
    sources=json.loads(path.read_text(encoding='utf-8'))
    catalogue=json.loads((WORLD/'catalogue.json').read_text(encoding='utf-8'))['locations']
    areas=json.loads((WORLD/'bridge/area_names.json').read_text(encoding='utf-8'))
    bindings=json.loads((WORLD/'bridge/city_pickup_bindings.json').read_text(encoding='utf-8'))
    by_source={row['source_key']:(bit,row) for bit,row in bindings.items()}
    records=[]
    for source in sources:
        if source['type_code'] not in (80,106):continue
        resource=source['resource'];key=source['source_key'];ap=catalogue.get('source_pickup:'+key,{})
        if '/levels/lego_city/lego_city/' in resource:
            scope='Stadt';district=resource.split('/levels/lego_city/lego_city/')[1].split('/')[0]
            area=areas.get(canonical(district),district)
        elif '/levels/standalones/' in resource and 'gamemechanicstestarea' not in resource:
            scope='Mission / HQ';district=resource.split('/levels/standalones/')[1].split('/')[0]
            area='Polizeiquartier' if district=='police_station' else district.replace('_',' ').title()
        else:
            scope='Vorlage / Test / Zusatzbereich'
            district=resource.split('/levels/')[1].split('/')[0] if '/levels/' in resource else 'unbekannt'
            area='Test: Game Mechanics' if 'gamemechanicstestarea' in resource else district
        bit,binding=by_source.get(key,('',{}))
        runtime=ap.get('runtime') or {}
        if bit=='' and runtime.get('kind')=='pickup':bit=runtime.get('bit','')
        xyz=source.get('resource_xyz') or [None,None,None]
        live=binding.get('position') or [None,None,None]
        records.append(dict(Bereich=scope,Area=area,Area_Code=district,
            Typ='GoldPlate / 2x2' if source['type_code']==80 else 'SuperBrick4X2 / 4x2',
            Quelltyp=source['type_code'],Objektname=source['name'],X=xyz[0],Y=xyz[1],Z=xyz[2],
            Koordinatenraum='Ressourcenkoordinaten; Elterntransformationen ungeprüft',
            AP_ID=ap.get('id',''),Pickup_Bit=bit,
            Zuordnung='Exakt zugeordnet' if bit!='' else 'Nicht an ein Pickup-Bit gebunden',
            Live_X=live[0],Live_Y=live[1],Live_Z=live[2],
            AP_Status=ap.get('status','Nicht im AP-Katalog'),Quelldatei=resource,
            Abschnitt_Offset=source['section_offset'],Index=source['index'],
            Parent=json.dumps(source.get('parent'),ensure_ascii=False),Source_Key=key))
    rank={'Stadt':0,'Mission / HQ':1,'Vorlage / Test / Zusatzbereich':2}
    records.sort(key=lambda r:(rank[r['Bereich']],r['Area'].casefold(),r['Quelldatei'],r['Abschnitt_Offset'],r['Index']))
    assert len(records)==len({r['Source_Key'] for r in records})
    assert len(records)==sum(r['type_code'] in (80,106) for r in sources)
    out=ROOT/'outputs/lcu_superbricks';out.mkdir(parents=True,exist_ok=True)
    with (out/'alle_supersteine_nach_area.csv').open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(records[0]),delimiter=';');writer.writeheader();writer.writerows(records)
    counts=Counter((r['Bereich'],r['Area'],r['Typ']) for r in records)
    summary=[]
    for scope,area in dict.fromkeys((r['Bereich'],r['Area']) for r in records):
        small=counts[scope,area,'GoldPlate / 2x2'];large=counts[scope,area,'SuperBrick4X2 / 4x2']
        summary.append([scope,area,small,large,small+large])
    report=dict(source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),records=records,summary=summary,
                counts=dict(total=len(records),by_scope=dict(Counter(r['Bereich'] for r in records)),
                            by_type=dict(Counter(r['Typ'] for r in records))))
    (out/'inventory_data.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    lines=['# Alle indizierten Superstein-Definitionen nach Area','',
        '550 Quelldefinitionen, einschließlich Vorlagen und Testbereichen. Stadt: 471; Mission/HQ: 41; Zusatz: 38.',
        'Vollständig gegenüber pickup_catalogue.json (Typ 80 und 106); keine Behauptung über alle dynamisch erzeugten Weltinstanzen.',
        'Koordinaten sind Ressourcenkoordinaten. Bei Vorlagen können Transformationen und mehrere Instanzen gelten.',
        'GoldPlate ist der kleine Superstein, kein goldener Belohnungsstein. Fehlende Bit-/AP-IDs bleiben leer.','',
        '| Bereich | Area | GoldPlate 2x2 | 4x2 | Gesamt |','|---|---|---:|---:|---:|']
    lines += ['| '+' | '.join(map(str,row))+' |' for row in summary]
    for scope,area in dict.fromkeys((r['Bereich'],r['Area']) for r in records):
        lines += ['',f'## {scope}: {area}','', '| Typ | Objekt | X | Y | Z | AP-ID | Pickup-Bit | Quelle / Abschnitt / Index |',
                  '|---|---|---:|---:|---:|---|---|---|']
        for r in records:
            if (r['Bereich'],r['Area'])!=(scope,area):continue
            lines.append('| '+' | '.join(str(v) for v in [r['Typ'],r['Objektname'],
                *[f'{r[k]:.5f}' if r[k] is not None else '' for k in ('X','Y','Z')],r['AP_ID'],r['Pickup_Bit'],
                f"{r['Quelldatei']}:{r['Abschnitt_Offset']}:{r['Index']}"])+' |')
    (out/'alle_supersteine_nach_area.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    # Read back the CSV to ensure no source rows were lost through formatting.
    with (out/'alle_supersteine_nach_area.csv').open(encoding='utf-8-sig',newline='') as stream:
        reread=list(csv.DictReader(stream,delimiter=';'))
    assert [r['Source_Key'] for r in reread]==[r['Source_Key'] for r in records]
    print(json.dumps(report['counts'],ensure_ascii=False))


if __name__=='__main__':main()
