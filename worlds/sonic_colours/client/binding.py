"""Seed attribution witnessed through the mandatory native intro records.

The ID belongs to the AP journal, not an invented Wii field. Resume requires
the selected native slot, profile and exact previously witnessed intro records.
No guest padding, NAND file or unrelated save is modified to make a marker.
"""
from dataclasses import replace
import json
from copy import deepcopy


INTRO = ('stg110', 'stg130')


def anchors(saved):
    return {mission: {key: saved['rank_records'][mission][key]
                      for key in ('raw_rank', 'score', 'time_raw')} for mission in INTRO}


class SaveBinding:
    def __init__(self, journal):
        self.journal = journal
        self.intro_session = None
        self.intro_stage_epoch = None
        self.second_act_seen = False
        self.first_record = None
        self.last_attributed_mission = None
        self.replay_result = None

    def recover_prior_binding(self, snapshot, saved):
        """Recover an exact native witness after client slot-data normalization changes."""
        if self.journal.data.get('native_binding') or not snapshot.progress_verified:
            return
        path=getattr(self.journal,'path',None)
        if path is None:return
        identity=self.journal.identity
        matches=[]
        for candidate in path.parent.glob('*.json'):
            if candidate==path:continue
            try:
                old=json.loads(candidate.read_text(encoding='utf-8'))
                other=old.get('identity',{})
                if any(other.get(k)!=identity.get(k) for k in ('seed','team','slot','revision','game')):continue
                binding=old.get('native_binding')
                if not binding or old.get('save_identity')!=binding['id']:continue
                if (binding['profile_hex']!=saved['profile_hex']
                    or binding['selected_index']!=saved['chain'][2]
                    or anchors(saved) not in binding['intro_record_witnesses']
                    or not set(old.get('native_monotonic_clears',[]))<=snapshot.persisted_clears):continue
                matches.append(old)
            except (OSError,ValueError,KeyError,TypeError):continue
        if len({old['native_binding']['id'] for old in matches})!=1:return
        old=matches[0]
        if old.get('ap_hud') and not self.journal.data.get('ap_hud',{}).get('events_received'):
            self.journal.data['ap_hud']=deepcopy(old['ap_hud'])
        if old.get('bootstrap'):
            self.journal.data['bootstrap']=deepcopy(old['bootstrap'])
        self.journal.data['native_binding']=deepcopy(old['native_binding'])
        self.journal.data['save_identity']=old['save_identity']
        self.journal.data['native_monotonic_clears']=old.get('native_monotonic_clears',[])
        self.journal.data['binding_recovery']='exact native witness from prior slot-data digest'
        # Previously delivered effects must not become eligible a second time.
        for index,effect in old.get('effects',{}).items():
            i=int(index)
            receipts=self.journal.data.get('receipts',[])
            previous=old.get('receipts',[])
            if i<len(receipts) and i<len(previous) and receipts[i]==previous[i]:
                self.journal.data.setdefault('effects',{}).setdefault(index,deepcopy(effect))
        self.journal.save()

    def observe_intro(self, snapshot):
        # This is valid even while the native save index is unavailable. Never
        # infer or create a persistent save ID from the heap or a menu label.
        if snapshot.new_game_verified and snapshot.actual_mission == INTRO[0]:
            if self.intro_stage_epoch != snapshot.stage_epoch or self.intro_session != snapshot.session:
                self.second_act_seen = False
                self.first_record = None
                self.last_attributed_mission = self.replay_result = None
                self.intro_stage_epoch = snapshot.stage_epoch
            self.intro_session = snapshot.session

    def attribute(self, snapshot, saved):
        self.observe_intro(snapshot)
        bootstrap = self.journal.data.get('bootstrap')
        binding = self.journal.data.get('native_binding')
        if not saved or not snapshot.progress_verified:
            return snapshot
        self.recover_prior_binding(snapshot,saved)
        binding = self.journal.data.get('native_binding')
        current = anchors(saved)
        profile, index = saved['profile_hex'], saved['chain'][2]
        if binding:
            if snapshot.scene not in ('gameplay', 'results', 'world_map', 'global_map'):
                self.last_attributed_mission = self.replay_result = None
            if profile != binding['profile_hex'] or index != binding['selected_index']:
                return replace(snapshot, status='native binding: selected slot or profile differs from seeded playthrough')
            if current not in binding['intro_record_witnesses']:
                # Replays can improve the two witness records. Only admit that
                # change after observing this already attributed intro act; no
                # unrelated loaded save may establish a new witness by itself.
                old = binding['intro_record_witnesses'][-1]
                changed = {mission for mission in INTRO if old[mission] != current[mission]}
                # Native best rank, score and time are mutable records, not a
                # save UUID. A legitimate replay can improve all three between
                # polls (or while reconnecting). Retain the profile/slot and
                # monotonic clear checks, and reject any record regression.
                record_improvement = (
                    snapshot.scene in ('gameplay','results','world_map','global_map')
                    and all(0<=current[m]['raw_rank']<=old[m]['raw_rank']<=4
                            and 0<current[m]['time_raw']<=old[m]['time_raw']
                            and current[m]['score']>=old[m]['score'] for m in INTRO)
                    and set(self.journal.data.get('native_monotonic_clears',[]))<=snapshot.persisted_clears)
                legitimate_replay = record_improvement or (self.last_attributed_mission in changed and len(changed) == 1
                                     and (snapshot.scene == 'results' and snapshot.actual_mission == self.last_attributed_mission
                                          or snapshot.scene in ('world_map', 'global_map')
                                          and self.replay_result == self.last_attributed_mission)
                                     and set(self.journal.data.get('native_monotonic_clears', [])) <= snapshot.persisted_clears
                                     and all(0 <= record['raw_rank'] <= 4 and record['time_raw'] > 0
                                             for record in current.values()))
                if not legitimate_replay:
                    return replace(snapshot, status='native binding: intro record witness mismatch; no attribution')
                binding['intro_record_witnesses'].append(current)
                self.journal.save()
            if snapshot.scene == 'results' and snapshot.actual_mission == self.last_attributed_mission:
                self.replay_result = snapshot.actual_mission
            if snapshot.scene == 'gameplay':
                self.last_attributed_mission = snapshot.actual_mission
                self.replay_result = None
            return replace(snapshot, save_identity=binding['id'], save_identity_verified=True,
                           new_save_selected=self.journal.data['save_identity'] is None,
                           visible_slot=index + 1,
                           evidence={**snapshot.evidence, 'save_binding_proof': binding['kind']},
                           status='seeded native save/profile/intro records attributed; live gameplay verification pending')
        if not bootstrap:
            return snapshot
        same_intro_session = (bootstrap['session'] == snapshot.session
                              and self.intro_session == snapshot.session)
        if same_intro_session and snapshot.actual_mission == INTRO[1] and snapshot.scene in ('gameplay', 'results'):
            self.second_act_seen = True
            record = current[INTRO[0]]
            if INTRO[0] in snapshot.persisted_clears and 0 <= record['raw_rank'] <= 4 and record['time_raw'] > 0:
                self.first_record = record
        # When New Game runs before a native save index exists, no rank-table
        # read is possible during the intro. Instead match the two *durably*
        # observed native UI result events against the subsequently saved rank
        # and score records. This does not accept old save data by itself.
        witnesses = [e for e in self.journal.data.get('pickup_events', ())
                     if e.get('kind') == 'result' and e.get('mission') in INTRO
                     and e.get('playthrough_epoch') == bootstrap['epoch']
                     and e.get('session') == bootstrap['session']
                     and e.get('provenance') == 'stage9C_native_UI_state7_grade124']
        witnessed = {}
        for e in witnesses:
            witnessed.setdefault(e['mission'], e)
        saved_matches_witnesses = (set(witnessed) == set(INTRO)
            and all(type(witnessed[m].get('score')) is int
                    and witnessed[m]['score'] == current[m]['score']
                    and witnessed[m]['grade'] == current[m]['raw_rank']
                    and current[m]['time_raw'] > 0 for m in INTRO))
        # A reboot may occur after saving but before the first map poll. Only
        # the two durable results from this bootstrap's original session may
        # bridge that gap; session-local observations cannot cross a reboot.
        old_verified_route = (same_intro_session and self.second_act_seen
                              and self.first_record == current[INTRO[0]])
        if (index <= 2 and (old_verified_route or saved_matches_witnesses)
                and snapshot.scene in ('global_map', 'world_map') and snapshot.scene_verified
                and snapshot.persisted_clears == frozenset(INTRO)
                and 0 <= current[INTRO[1]]['raw_rank'] <= 4 and current[INTRO[1]]['time_raw'] > 0):
            binding = {'kind': 'native_intro_record_witness_v1', 'id': bootstrap['epoch'],
                       'bootstrap_epoch': bootstrap['epoch'], 'selected_index': index,
                       'profile_hex': profile, 'intro_record_witnesses': [current]}
            self.journal.data['native_binding'] = binding
            self.journal.save()
            return self.attribute(snapshot, saved)
        return snapshot
