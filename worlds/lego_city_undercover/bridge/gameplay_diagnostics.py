"""Bounded, change-only observed gameplay evidence; never emits AP checks."""
class GameplayDiagnostics:
    def __init__(self):self.identity=None;self.previous=None

    def observe(self,snapshot,journal):
        process=snapshot.get('process') or {};bank=snapshot.get('native_binding') or {}
        identity=(journal.binding_token,process.get('pid'),bank.get('bank'),process.get('profile'))
        if identity!=self.identity:self.identity=identity;self.previous=None
        state=dict(area=(snapshot.get('location') or {}).get('native_tile'),
            scene=(snapshot.get('mission_shield') or {}).get('scene'),
            bits=set(snapshot.get('pickup_bits',())),
            objectives={r['name_hash'] for r in snapshot.get('objectives',{}).get('records',[]) if r.get('candidate_complete')},
            models={r.get('internal_name'):(r.get('found_bit'),r.get('owned_byte')) for r in snapshot.get('characters',[])})
        if self.previous is None:
            journal.diagnostic(dict(kind='snapshot_baseline',area=state['area'],scene=state['scene'],
                collected_bits=len(state['bits']),verification='observation',mutation=False))
        if self.previous is not None:
            old=self.previous
            for field in ('area','scene'):
                if state[field]!=old[field]:journal.diagnostic(dict(kind=field+'_transition',before=old[field],after=state[field],
                    verification='observation',mutation=False,position=snapshot.get('location',{}).get('player_position')))
            for bit in sorted(state['bits']-old['bits']):
                objects=[r for r in snapshot.get('pickup_memory',{}).get('objects',[]) if r.get('collection_bit')==bit]
                journal.diagnostic(dict(kind='pickup_bit_transition',bit=bit,objects=objects[:4],
                    verification='native_binding_candidate',mutation=False))
            for objective in sorted(state['objectives']-old['objectives']):
                journal.diagnostic(dict(kind='objective_complete',native_hash=objective,verification='native_binding_verified',mutation=False))
            for name,flags in state['models'].items():
                if old['models'].get(name)!=(flags):journal.diagnostic(dict(kind='model_state_change',model=name,
                    before=old['models'].get(name),after=flags,verification='observation',mutation=False))
        self.previous=state
