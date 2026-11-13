"""Pure snapshot transition detection for the read-only live monitor."""


class EventTracker:
    def __init__(self, labels):
        self.labels = labels
        self.previous = None
        self.seen = set()

    def update(self, snapshot):
        if self.previous is None:
            self.seen.update(f"objective:{r['name_hash']}" for r in snapshot['objectives']['records'] if r['candidate_complete'])
            self.seen.update(f"pickup:{bit}" for bit in snapshot['pickup_bits'])
            self.seen.update(f"found:{r['model_id']}" for r in snapshot['characters'] if r.get('found_bit') or r.get('pending_grant'))
            self.seen.update(f"owned:{r['model_id']}" for r in snapshot['characters'] if r.get('owned_byte') or r.get('pending_grant'))
            self.seen.update(f"ability:{name}" for name, value in snapshot['abilities'].items() if value)
            self.previous = snapshot
            return []
        prior = self.previous
        events = []

        def emit(key, kind, text):
            if key not in self.seen:
                self.seen.add(key)
                events.append(dict(kind=kind, text=text, identity=key))

        def model_name(row):
            display=self.labels.get('models',{}).get(str(row['model_id']),{}).get('display_name')
            return f"{display} ({row['internal_name']})" if display else row['internal_name']

        old = {r['name_hash']: r for r in prior['objectives']['records']}
        for row in snapshot['objectives']['records']:
            key = row['name_hash']
            if key in old and row['candidate_complete'] and not old[key]['candidate_complete']:
                label = self.labels['objectives'].get(str(key))
                name = (f"{label['instanceName']} · {label['objectiveTypeId']} · {label['cityDistrict']}"
                        if label else f"Bit {row['bit_index']} · Hash {key}")
                emit(f"objective:{key}", 'city_flag', f"Stadtaktivität / Flag: {name}")
        for bit in sorted(set(snapshot['pickup_bits']) - set(prior['pickup_bits'])):
            label = self.labels['superbricks'].get(str(bit))
            name = f"{label['name']} · {label['resource']}" if label else "Objekt noch nicht zugeordnet"
            emit(f"pickup:{bit}", 'superbrick', f"Superbaustein-Sammelbit {bit}: {name}")
        old_chars = {r['model_id']: r for r in prior['characters']}
        for row in snapshot['characters']:
            previous = old_chars.get(row['model_id'], {})
            if row.get('pending_grant') and not previous.get('pending_grant') and not previous.get('owned_byte'):
                emit(f"pending:{row['model_id']}", 'unlock',
                      f"Freischaltung verfügbar ({row['group']}): {model_name(row)} · Modell {row['model_id']} · Speicherung ausstehend")
                self.seen.add(f"found:{row['model_id']}")
                self.seen.add(f"owned:{row['model_id']}")
            if row.get('found_bit') and not previous.get('found_bit'):
                emit(f"found:{row['model_id']}", 'discovery',
                      f"Begleitfund ({row['group']}): {model_name(row)} · Modell {row['model_id']}")
            elif row.get('owned_byte') and not previous.get('owned_byte') and not previous.get('pending_grant'):
                emit(f"owned:{row['model_id']}", 'ownership', f"Jetzt im Besitz: {model_name(row)}")
        for name, unlocked in snapshot['abilities'].items():
            if unlocked and not prior['abilities'].get(name, False):
                emit(f"ability:{name}", 'ability', f"Fähigkeit freigeschaltet: {name}")
        old_jobs = prior.get('story', {}).get('jobs', {})
        for job in ('Standalones.Prison', 'Flow_Saves.Act_1.Meet_Blue_at_Prison'):
            for field, value in snapshot.get('story', {}).get('jobs', {}).get(job, {}).items():
                previous = old_jobs.get(job, {}).get(field)
                if previous is not None and previous != value:
                    events.append(dict(kind='mission_state', identity=f'mission:{job}.{field}',
                                       text=f'Missionswert (Diagnose): {job}.{field}: {previous} → {value}',
                                       before=previous, after=value, persistent_completion_verified=False))
        self.previous = snapshot
        return events
