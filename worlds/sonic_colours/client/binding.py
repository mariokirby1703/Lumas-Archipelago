"""Seed attribution witnessed through the mandatory native intro records.

The ID belongs to the AP journal, not an invented Wii field. Resume requires
the selected native slot, profile and exact previously witnessed intro records.
No guest padding, NAND file or unrelated save is modified to make a marker.
"""
from dataclasses import replace


INTRO = ('stg110', 'stg130')


def anchors(saved):
    return {mission: {key: saved['rank_records'][mission][key]
                      for key in ('raw_rank', 'score', 'time_raw')} for mission in INTRO}


class SaveBinding:
    def __init__(self, journal):
        self.journal = journal
        self.intro_session = None
        self.second_act_seen = False
        self.first_record = None
        self.last_attributed_mission = None
        self.replay_result = None

    def attribute(self, snapshot, saved):
        bootstrap = self.journal.data.get('bootstrap')
        binding = self.journal.data.get('native_binding')
        if not saved or not snapshot.progress_verified:
            return snapshot
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
                legitimate_replay = (self.last_attributed_mission in changed and len(changed) == 1
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
        if snapshot.new_game_verified and snapshot.actual_mission == INTRO[0]:
            self.intro_session = snapshot.session
        if not bootstrap or bootstrap['session'] != snapshot.session:
            return snapshot
        if self.intro_session != snapshot.session:
            return snapshot
        if snapshot.actual_mission == INTRO[1] and snapshot.scene in ('gameplay', 'results'):
            self.second_act_seen = True
            record = current[INTRO[0]]
            if INTRO[0] in snapshot.persisted_clears and 0 <= record['raw_rank'] <= 4 and record['time_raw'] > 0:
                self.first_record = record
        if (index <= 2 and self.second_act_seen and self.first_record == current[INTRO[0]]
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
