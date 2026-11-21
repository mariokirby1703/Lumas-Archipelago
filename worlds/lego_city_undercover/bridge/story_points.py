"""Read-only source-bound story milestones. Active chapter and AP ownership are not completion."""
import json
import pkgutil
from pathlib import Path
raw=pkgutil.get_data(__package__,'story_point_bindings.json') if __package__ else Path(__file__).with_name('story_point_bindings.json').read_bytes()
POINTS=tuple(json.loads(raw)['points'])
COMPLETIONS=tuple(r for r in POINTS if r['new_location'] and r['kind']=='native_job_completion')

def completed_story_points(story):
    if story.get('status')!='read':return set()
    jobs=story.get('jobs',{})
    return {r['ap_key'] for r in COMPLETIONS if jobs.get(r['job'],{}).get(r['field']) is True}

def catalogue_rows():
    return {r['ap_key']:dict(id=r['ap_id'],name='Story: '+r['name'],display_name=r['name'],
        category='story_milestones',chapter=r['chapter'],district=None,coordinates=None,
        source=r['evidence'][0]['resource'],source_evidence=r['evidence'],coordinate_space=None,
        runtime=dict(kind='story_point',job=r['job'],field=r['field'],expected=True),
        status='native_story_point',logic_verified=False,
        evidence='Explicit original end-of-action JobValue write; not current chapter, ability ownership or mission completion inference')
        for r in COMPLETIONS}
