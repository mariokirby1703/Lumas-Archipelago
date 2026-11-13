"""Serializable event evidence and clipboard export; no game operations."""
import json


def event_evidence(event, before, after):
    kind, value = event['identity'].split(':', 1)
    evidence = dict(location=after.get('location', {}), stats=after.get('stats', {}),
                    identity_is_native_not_ap=True)
    if kind == 'objective':
        key = int(value)
        old = next(r for r in before['objectives']['records'] if r['name_hash'] == key)
        new = next(r for r in after['objectives']['records'] if r['name_hash'] == key)
        evidence.update(before=old, after=new, manager=after['objectives'].get('manager_pointer'))
    elif kind == 'pickup':
        bit = int(value)
        evidence.update(bit_index=bit, byte_offset=bit//8, mask=1<<(bit%8),
                        before=before.get('pickup_bytes', [])[bit//8] if before.get('pickup_bytes') else None,
                        after=after.get('pickup_bytes', [])[bit//8] if after.get('pickup_bytes') else None,
                        payload_address=after.get('pickup_address'))
        evidence['native_object_observations']=[dict(phase=phase,**r)
            for phase,snapshot in (('before',before),('after',after))
            for r in snapshot.get('native_pickups',{}).get('objects',[])
            if r.get('collection_bit')==bit]
        cached=[r for r in after.get('pickup_memory',{}).get('objects',[]) if r.get('collection_bit')==bit]
        evidence['cached_object_observations']=cached
        evidence['native_identity_conflict']=bit in after.get('pickup_memory',{}).get('conflicts',[])
        if len(cached)==1 and not evidence['native_identity_conflict']:
            row=cached[0]
            event=dict(event,text=f"Superbaustein {bit}: {row['name']} · {row.get('tile_name','?')}")
    elif kind in ('found','owned','pending'):
        key = int(value)
        evidence.update(model_id=key,
                        before=next((r for r in before['characters'] if r['model_id'] == key), None),
                        after=next(r for r in after['characters'] if r['model_id'] == key))
    elif kind == 'ability':
        evidence.update(ability=value, before=before['abilities'].get(value), after=after['abilities'].get(value),
                        raw_after=after.get('ability_raw', {}).get(value))
    return dict(event, evidence=evidence)


def export_report(records):
    return json.dumps(dict(format='LCU monitor log', version=2, writes_enabled=False,
                           ap_connected=False, records=records), ensure_ascii=False, indent=2)
