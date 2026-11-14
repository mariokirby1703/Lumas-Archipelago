"""Named activities identified by specific native reward objects, never totals."""
import json
from pathlib import Path
ACTIVITY_REWARDS=json.loads((Path(__file__).parent/'activity_rewards.json').read_text(encoding='utf-8'))

def completed_activity_rewards(snapshot):
    state=snapshot.get('native_pickups',{})
    if state.get('status')!='read':return {}
    result={}
    for reward in ACTIVITY_REWARDS:
        matches=[row for row in state.get('objects',[]) if
                 row.get('tile_name','').upper()==reward['scene'].upper() and
                 row.get('name')==reward['pickup_name'] and
                 row.get('native_type')==reward['native_type'] and
                 row.get('source_key') in (None,reward['source_key'])]
        if len(matches)==1 and matches[0].get('native_collected'):
            result[reward['key']]=reward
    return result
