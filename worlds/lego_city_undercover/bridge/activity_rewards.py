"""Named activities identified by specific native reward objects, never totals."""
import json
from research_profile import symbol_hash
from pathlib import Path
ACTIVITY_REWARDS=json.loads((Path(__file__).parent/'activity_rewards.json').read_text(encoding='utf-8'))

def completed_activity_rewards(snapshot):
    state=snapshot.get('native_pickups',{})
    objective_state=snapshot.get('objectives',{})
    completed={row['name_hash'] for row in objective_state.get('records',[]) if row.get('candidate_complete')}
    if objective_state.get('status') not in ('read','experimental_snapshot',None):completed=set()
    result={}
    for reward in ACTIVITY_REWARDS:
        objective=reward.get('completion_objective')
        if objective and symbol_hash(objective) in completed:
            result[reward['key']]=reward
            continue
        if state.get('status')!='read':continue
        matches=[row for row in state.get('objects',[]) if
                 row.get('tile_name','').upper()==reward['scene'].upper() and
                 row.get('name')==reward['pickup_name'] and
                 row.get('native_type')==reward['native_type'] and
                 row.get('source_key') in (None,reward['source_key'])]
        if len(matches)==1 and matches[0].get('native_collected'):
            result[reward['key']]=reward
    return result
