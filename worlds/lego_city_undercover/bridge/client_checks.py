"""Pure binding of observed transitions to active server locations."""
from research_profile import symbol_hash


def changed_checks(catalogue,previous,snapshot):
    objectives={r['name_hash'] for r in snapshot['objectives']['records'] if r['candidate_complete']}
    bits=set(snapshot['pickup_bits'])
    if previous is None:return [],dict(objectives=objectives,pickups=bits)
    new_objectives=objectives-previous['objectives'];new_bits=bits-previous['pickups']
    memory=snapshot.get('pickup_memory',{})
    conflicts=set(memory.get('conflicts',[]))
    source_keys={r['source_key'] for r in memory.get('objects',[])
                 if r.get('collection_bit') in new_bits-conflicts and r.get('source_key')}
    checks=[]
    for key,row in catalogue.items():
        runtime=row.get('runtime') or {}
        if (row.get('status')=='native_objective' and runtime.get('kind')=='objective'
                and symbol_hash(runtime['name']) in new_objectives):checks.append(int(key))
        elif (row.get('status')=='native_pickup' and runtime.get('kind')=='pickup'
              and runtime['bit'] in new_bits-conflicts):checks.append(int(key))
        elif row.get('key','').startswith('source_pickup:') and row['key'][14:] in source_keys:
            checks.append(int(key))
    return sorted(set(checks)),dict(objectives=objectives,pickups=bits)
