"""Authoritative per-build persistent job progress, independent of loaded gizmos."""
import json
from pathlib import Path
from research_profile import symbol_hash
BINDINGS=tuple(json.loads((Path(__file__).parent/'superbuild_jobs.json').read_text()))

def reconcile_superbuild_objectives(objectives,story):
    result=set(objectives)
    if story.get('status')!='read':return result
    jobs=story.get('jobs',{})
    for row in BINDINGS:
        state=jobs.get(row['job'],{})
        if (type(state.get('nID')) is not int or state['nID']!=row['native_id'] or
                type(state.get('nState')) is not int or state['nState'] not in (0,1,2)):continue
        key=symbol_hash(row['objective']);result.discard(key)
        if state['nState']==row['completed_state']:result.add(key)
    return result
