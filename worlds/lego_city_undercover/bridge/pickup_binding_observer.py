"""Two-observation structural pickup proofs, scoped to a bound client journal.

Never guess by distance, resource ordering or an assumed global index offset.
Stable registration is binding evidence, not a successful live collection test.
"""
from copy import deepcopy

HASH='624fed07274bbd105d1d571ecb97a290df6f6f0aff76898c516890da6d136f76'
TYPES={80:12,106:29}


class BindingObserver:
    def __init__(self, locations, static_bindings):
        self.locations=locations;self.static=static_bindings
        self.identity=None;self.previous={}

    def observe(self,snapshot,journal):
        process=snapshot.get('process') or {};binding=snapshot.get('native_binding') or {}
        identity=(journal.binding_token,process.get('pid'),process.get('sha256'),binding.get('bank'))
        if identity!=self.identity:
            self.identity=identity;self.previous={}
        if process.get('sha256')!=HASH or not process.get('pid'):
            self.previous={};return False
        state=snapshot.get('native_pickups') or {}
        if state.get('status')!='read':
            self.previous={};return False
        groups={};current={};changed=False
        for row in state.get('objects',[]):
            bit=row.get('collection_bit')
            if type(bit) is int and 0<=bit<12800:groups.setdefault(bit,[]).append(row)
        for bit,rows in groups.items():
            sources={row.get('source_key') for row in rows if row.get('source_key')}
            if len(rows)!=1 or bit in (5848,5849,5850):
                journal.pickup_conflict(bit,sources,'multiple registrations or known ambiguous native bit')
                changed=True
                continue
            row=rows[0];source=row.get('source_key')
            location=self.locations.get('source_pickup:'+str(source),{})
            if ('/levels/lego_city/lego_city/' not in str(source) or
                location.get('category')!='super_bricks' or
                TYPES.get(location.get('source_type_code'))!=row.get('native_type') or
                row.get('status')!='native_writer_derived_binding' or
                row.get('local_index')!=bit%8 or not row.get('address') or
                row.get('source_candidates')!=[source]):continue
            signature=(source,row['native_type'],row['address'],row.get('tile_name'),bit,row.get('local_index'))
            current[bit]=(signature,deepcopy(row),bit in set(snapshot.get('pickup_bits',())))
            prior=self.previous.get(bit)
            if not prior or prior[0]!=signature:continue
            proof=dict(source_key=source,bit=bit,source_type=location['source_type_code'],
                native_type=row['native_type'],resource=location['source'],name=row['name'],
                instance_address=row['address'],tile_name=row.get('tile_name'),position=row.get('position'),
                local_index=row['local_index'],verification='native_binding_verified',
                evidence='two stable native registration observations; exact tile/name/type source; writer-derived bit',
                collection_transition_observed=not prior[2] and current[bit][2],
                before_collected=prior[2],after_collected=current[bit][2],game_mutated=False)
            proof.update(process=dict(pid=process['pid'],sha256=process['sha256']),native_bank=binding.get('bank'),
                journal_binding=journal.binding_token.hex(),tile_xy=row.get('tile_xy'),
                native_flags=dict(type_flags=row.get('type_flags'),instance_flags=row.get('instance_flags')))
            known=self.static.get(str(bit))
            other=[int(b) for b,r in self.static.items() if r.get('source_key')==source and int(b)!=bit]
            if known and known.get('source_key')!=source or other:
                journal.pickup_conflict(bit,{source,*( [known['source_key']] if known else [])},'conflict with packaged binding')
                for old_bit in other:journal.pickup_conflict(old_bit,{source},'source registered at another bit')
                changed=True;continue
            changed=journal.store_pickup_binding(proof) or changed
        self.previous=current
        return changed


def binding_overlay(journal,static):
    bindings=deepcopy(static);blocked=journal.pickup_conflicts()
    for row in journal.pickup_bindings():
        bit=str(row['bit'])
        if bit in bindings and bindings[bit]['source_key']!=row['source_key']:
            blocked.add(int(bit))
        else:bindings[bit]=row
    return {b:r for b,r in bindings.items() if int(b) not in blocked},blocked
