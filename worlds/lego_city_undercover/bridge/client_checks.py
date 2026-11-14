"""Reconcile completed native state with active server locations."""
from research_profile import symbol_hash
from activity_rewards import completed_activity_rewards
from level_progress import completed_level_keys
from red_bricks import redbrick_location_key

# These source tiles alias the same native bits. Block them before either tile
# has been observed; runtime conflict detection alone is too late.
KNOWN_AMBIGUOUS_PICKUP_BITS=frozenset((5848,5849,5850))

def changed_checks(catalogue,previous,snapshot,checked_locations=()):
    objective_state=snapshot.get('objectives',{})
    if objective_state.get('status') not in (None,'experimental_snapshot','read') or 'records' not in objective_state or 'pickup_bits' not in snapshot:
        # An incomplete read cannot establish that any location is complete.
        return [],None
    objectives={r['name_hash'] for r in snapshot['objectives']['records'] if r['candidate_complete']}
    builds=snapshot.get('superbuilds',{})
    if builds.get('status')=='read':
        objectives.update(symbol_hash(r['objective_name']) for r in builds.get('records',[])
                          if r.get('complete') and r.get('objective_name'))
    bits=set(snapshot['pickup_bits'])
    baseline=dict(objectives=objectives,pickups=bits)
    # Reconcile the complete readable state, including offline progress and
    # records loaded after connection. The server acknowledgement is authoritative.
    acknowledged=set(checked_locations)
    memory=snapshot.get('pickup_memory',{})
    conflicts=set(memory.get('conflicts',[])) | KNOWN_AMBIGUOUS_PICKUP_BITS
    source_keys={r['source_key'] for r in memory.get('objects',[])
                 if r.get('collection_bit') in bits-conflicts and r.get('source_key')}
    native=snapshot.get('native_pickups',{})
    red_brick_missions=set()
    if native.get('status')=='read':
        source_keys.update(r['source_key'] for r in native.get('objects',[])
            if r.get('native_collected') and r.get('native_type') in (12,29)
            and '/levels/standalones/' in (r.get('source_key') or ''))
        for row in native.get('objects',[]):
            source=row.get('source_key') or ''
            if not row.get('native_collected') or row.get('native_type')!=7 or not source:continue
            if '/levels/standalones/' in source:
                location_key=redbrick_location_key(source)
                if location_key:red_brick_missions.add(location_key)
            elif '/levels/lego_city/lego_city/' in source:source_keys.add(source)
    activities=completed_activity_rewards(snapshot)
    checks=[]
    persistent_keys=completed_level_keys(snapshot.get('level_progress',{}))
    persistent_keys.update(red_brick_missions)
    found_models={r['internal_name'].upper() for r in snapshot.get('characters',[])
                  if (r.get('found_bit') or r.get('pending_grant')) and r.get('group') in ('character','vehicle')}
    if snapshot.get('mission_tokens',{}).get('status')=='read':
        found_models.update(r['internal_name'].upper() for r in snapshot['mission_tokens']['records'])
    for key,row in catalogue.items():
        if row.get('key') in persistent_keys:checks.append(int(key))
        runtime=row.get('runtime') or {}
        hero=snapshot.get('mission_hero',{})
        if (hero.get('status')=='read' and hero.get('complete') and hero.get('mission')
            and row.get('key')=='mission:'+hero['mission']+':LEGO City Hero'):
            checks.append(int(key))
        shield=snapshot.get('mission_shield',{})
        if shield.get('status')=='read' and shield.get('mission'):
            prefix='mission:'+shield['mission']+':'
            location_key=row.get('key','')
            if location_key.startswith(prefix):
                part=location_key[len(prefix):]
                if (part in shield.get('parts',[]) or
                    (part=='Police Shield' and set(shield.get('parts',[]))=={'TL','TR','BL','BR'})):
                    checks.append(int(key))
        if runtime.get('kind')=='activity_reward' and runtime.get('reward_key') in activities:
            checks.append(int(key))
        if (row.get('status')=='native_objective' and runtime.get('kind')=='objective'
                and symbol_hash(runtime['name']) in objectives):checks.append(int(key))
        elif (row.get('status')=='native_pickup' and runtime.get('kind')=='pickup'
              and runtime['bit'] in bits-conflicts):checks.append(int(key))
        elif row.get('key','').startswith('source_pickup:') and row['key'][14:] in source_keys:
            checks.append(int(key))
        elif (row.get('status')=='experimental_model_found' and runtime.get('kind')=='model_found'
              and runtime['native_name'].upper() in found_models):checks.append(int(key))
    return sorted(set(checks)-acknowledged),baseline
