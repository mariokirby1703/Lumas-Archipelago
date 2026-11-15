"""Stable-key enrichment; Sheet requirements stay explicitly unverified."""
import json
import pkgutil
from pathlib import Path


def data(name):
    raw=pkgutil.get_data(__package__,name) if __package__ else Path(__file__).with_name(name).read_bytes()
    return json.loads(raw)


def enrich_catalogue(catalogue):
    design=data('location_design.json');relations=data('token_relationships.json')
    seen=set()
    for source in design['rows']:
        row=catalogue['locations'].get(source.get('native_key'))
        if row is None:continue
        if source['native_key'] in seen:
            row.setdefault('design_references',[]).append(source['sheet_row']);continue
        seen.add(source['native_key'])
        row.update(display_name=source['display_name'],display_area=source['display_area'],
                   design_requirements=source['design'],design_order=source['number'],sheet_row=source['sheet_row'])
        amount=source['design']['building_bricks']
        row['building_brick_cost']=dict(amount=amount if type(amount) is int else None,evidence='unverified_user_design',logic_enforced=False)
    for key,relationship in relations.items():
        if key in catalogue['locations']:catalogue['locations'][key]['token_relationship']=relationship
    try:
        from .area_passes import canonical
    except ImportError:
        from area_passes import canonical
    area_names=data('area_names.json')
    labels={'Ability: EnergyGun':'Color Gun','Ability: GrappleGun':'Grapple Gun','Ability: Scanner':'Criminal Scan','Ability: Criminal Scan':'Criminal Scan',
            'Ability: Wiretap':'Listening Scan / Wiretap','Ability: FireAxe':'Fire Axe'}
    for name,row in catalogue['items'].items():
        if name in labels:row['display_name']=labels[name]
        if row['category']=='area_pass':
            district=canonical(name.removeprefix('Area Pass: '))
            if district:
                row.update(native_name=district,effect='area_access',classification='progression',native_status='experimental_near_boundary_return',
                           display_name='Area Pass: '+area_names.get(district,district))
    return catalogue
