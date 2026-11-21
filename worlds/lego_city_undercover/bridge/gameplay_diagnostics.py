"""Bounded, change-only observed gameplay evidence; never emits AP checks."""
from story_points import completed_story_points
class GameplayDiagnostics:
    def __init__(self):self.identity=None;self.previous=None

    def observe(self,snapshot,journal):
        process=snapshot.get('process') or {};bank=snapshot.get('native_binding') or {}
        identity=(journal.binding_token,process.get('pid'),bank.get('bank'),process.get('profile'),
                  (snapshot.get('actor') or {}).get('address'))
        if identity!=self.identity:self.identity=identity;self.previous=None
        old=self.previous
        # A loading/read failure is not an empty collection. Retain the last
        # successful observation independently for every readable section.
        state=dict(old or {})
        location=snapshot.get('location') or {};shield=snapshot.get('mission_shield') or {}
        if location.get('area_status')=='native_tile' or location.get('native_tile'):
            state['area']=location['native_tile']
        if shield.get('status')=='read' or shield.get('scene'):
            state['scene']=shield.get('scene');state['assignment']=shield.get('assignment',shield.get('mission'))
        if 'pickup_bits' in snapshot:state['bits']=set(snapshot['pickup_bits'])
        objectives=snapshot.get('objectives') or {}
        if objectives.get('status') in (None,'read','experimental_snapshot') and 'records' in objectives:
            state['objectives']={r['name_hash'] for r in objectives['records'] if r.get('candidate_complete')}
        if 'characters' in snapshot:
            state['models']={r.get('internal_name'):(r.get('found_bit'),r.get('owned_byte')) for r in snapshot['characters']}
        pickups=snapshot.get('native_pickups') or {}
        if pickups.get('status')=='read':
            state['collections']={r['source_key'] for r in pickups.get('objects',[])
                                  if r.get('source_key') and r.get('native_collected')}
        if snapshot.get('story',{}).get('status')=='read':state['story_points']=completed_story_points(snapshot['story'])
        actor=snapshot.get('actor') or {}
        if actor.get('status')=='read':state['context']=(actor.get('context') or {}).get('name')
        details=dict(position=location.get('player_position'),area=state.get('area'),scene=state.get('scene'),
                     assignment=state.get('assignment'),verification='native_binding_candidate',mutation=False)
        if old is None:
            journal.diagnostic(dict(details,kind='snapshot_baseline',collected_bits=len(state.get('bits',()))))
        else:
            for field in ('area','scene','assignment','context'):
                if field in state and field in old and state[field]!=old[field]:
                    journal.diagnostic(dict(details,kind=field+'_transition',before=old[field],after=state[field]))
            if 'bits' in old and 'bits' in state:
                for bit in sorted(state['bits']-old['bits']):
                    objects=[r for r in snapshot.get('pickup_memory',{}).get('objects',[]) if r.get('collection_bit')==bit]
                    journal.diagnostic(dict(details,kind='pickup_bit_transition',bit=bit,objects=objects[:4]))
            if 'objectives' in old and 'objectives' in state:
                for objective in sorted(state['objectives']-old['objectives']):
                    journal.diagnostic(dict(details,kind='objective_complete',native_hash=objective,
                                            verification='native_binding_verified'))
            if 'collections' in old and 'collections' in state:
                for source in sorted(state['collections']-old['collections']):
                    rows=[r for r in pickups.get('objects',[]) if r.get('source_key')==source]
                    journal.diagnostic(dict(details,kind='native_pickup_collection',source_key=source,objects=rows[:2]))
            if 'story_points' in old and 'story_points' in state:
                for key in sorted(state['story_points']-old['story_points']):
                    journal.diagnostic(dict(details,kind='story_point_complete',key=key,verification='native_binding_verified'))
            if 'models' in old and 'models' in state:
                for name,flags in state['models'].items():
                    if old['models'].get(name)!=flags:
                        journal.diagnostic(dict(details,kind='model_state_change',model=name,before=old['models'].get(name),after=flags))
        self.previous=state
