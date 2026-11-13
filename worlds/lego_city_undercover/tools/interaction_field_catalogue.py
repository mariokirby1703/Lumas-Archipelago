"""Catalogue native action-marker names and relevant prison resource evidence.

Read-only static metadata; does not infer the active field from player context.
"""
import json
from pathlib import Path
import re

from resource_catalogue import sections


def main():
    world = Path(__file__).resolve().parents[1]
    strings = json.loads((world / 'notes/analysis/LEGOLCUR_DX11.exe.strings.json').read_text())
    markers = [dict(name=r['text'], file_offset=r['offset']) for r in strings
               if r['text'].startswith(('Hotspot_Ability_Floor_', 'Icon_ChangeToRobber_'))]
    resources = []
    for path in (world / 'notes/extracted').rglob('*.giz'):
        if '/standalones/prison/' not in path.as_posix():
            continue
        data = path.read_bytes()
        try:
            blocks, _ = sections(data)
        except ValueError:
            continue
        for block in blocks:
            if block['name'] not in ('Techno', 'GizSwitch'):
                continue
            payload = data[block['offset']:block['offset']+block['size']]
            resources.append(dict(resource=path.relative_to(world / 'notes/extracted').as_posix(),
                                  section=block, literal_names=[m.group().decode('ascii')
                                  for m in re.finditer(rb'[ -~]{5,}', payload)]))
    report = dict(markers=markers, prison_resources=resources,
                  active_field_identified=False, native_gate_verified=False, writes_enabled=False)
    (world / 'notes/analysis/interaction_field_catalogue.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(f'{len(markers)} marker names; {len(resources)} prison Techno/switch sections')


if __name__ == '__main__':
    main()
