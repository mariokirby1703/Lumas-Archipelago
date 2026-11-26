"""Authoritative assignment entitlement projection, not a native entrance hook.

Policy is reconstructed from journal receipts and slot data, never completion
flags. Native acknowledgement is deliberately absent until a real gate exists.
"""
import json
import pkgutil
from pathlib import Path

raw=pkgutil.get_data(__package__,'assignment_entries.json') if __package__ else Path(__file__).with_name('assignment_entries.json').read_bytes()
ENTRIES=tuple(json.loads(raw)['entries'])


def build_policy(slot_data,receipts,binding):
    if not isinstance(binding,str) or len(binding)!=32:
        raise ValueError('Expected a nonzero 128-bit save binding')
    try:token=bytes.fromhex(binding)
    except ValueError:raise ValueError('Invalid save binding') from None
    if len(token)!=16 or not any(token):raise ValueError('Invalid save binding')
    enabled=bool(slot_data.get('options',{}).get('story_access_items',False))
    effects=slot_data.get('item_effects',{})
    # Use both ID and canonical identity: a stale/mismatched effect table must
    # never grant another assignment's permission.
    canonical={r['item_id']:r for r in ENTRIES}
    received=set()
    for item in receipts:
        ident=item.get('item')
        if type(ident) is not int:continue
        row=canonical.get(ident);effect=effects.get(str(ident),{})
        if row and effect.get('name')==row['item'] and effect.get('category')=='story_access':
            received.add(ident)
    return dict(version=1,binding=binding.lower(),native_gate_installed=False,
        entries=[dict(assignment=r['assignment'],item_id=r['item_id'],managed=enabled,
                      received=r['item_id'] in received,native_acknowledged=False)
                 for r in ENTRIES])


def permission(policy,assignment,binding):
    """Diagnostic decision only: unknown identity/binding always fails closed."""
    if policy.get('binding')!=binding:return False
    matches=[r for r in policy.get('entries',[]) if r.get('assignment')==assignment]
    return len(matches)==1 and (not matches[0]['managed'] or matches[0]['received'])
