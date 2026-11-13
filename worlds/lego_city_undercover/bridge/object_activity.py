"""Object-specific raw transitions, independent of persistent check detection."""
from copy import deepcopy


class ObjectActivityTracker:
    def __init__(self):
        self.level=None
        self.previous={}

    def update(self,state):
        if state.get('status')!='read':
            # Do not bridge uncertain load/reset intervals as gameplay actions.
            self.level=None;self.previous={}
            return []
        rows={r['address']:r for r in state['fields']}
        events=[]
        if self.level==state['level']:
            for address,row in rows.items():
                old=self.previous.get(address)
                if old is None or old['name']!=row['name']:continue
                changes={k:dict(before=old.get(k),after=row.get(k))
                         for k in ('requirement_flags','state_flags','object_flags')
                         if old.get(k)!=row.get(k)}
                if changes:
                    events.append(dict(kind='native_object_state_change',automatic_check=False,
                                       identity=f"native_object:{address}:{row['name']}",
                                       name=row['name'],family=row['family'],changes=changes,
                                       object_position=row['position'],player_position=state['player_position'],
                                       marker=row.get('marker'),
                                       evidence='raw native flags changed; not proof of completion'))
        self.level=state['level'];self.previous=deepcopy(rows)
        return events
