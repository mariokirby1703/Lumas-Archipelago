"""Only this adapter may interpret native gameplay structures.

The selected-save flags are inline. Three clear bits have individual live
validation; the shared native accessor decodes all 66. Other reads have original-capture
regressions. Persistent save identity and every writer remain gated.
"""
import uuid

from .memory import MemoryUnavailable
from .versions import VERSION
from .state import Snapshot
from .native_read import read_saved_progress, read_stage_objects
from ..world_constants import load_data


class NativeHooks:
    def __init__(self):
        self.chain = None
        self.stable_polls = 0
        self.session_epoch = 0
        self.instance = uuid.uuid4().hex
        self.application = None
        self.context_key = None
        self.progress_rows = load_data('progress_bits.json')
        self.read_validation = load_data('native_read_validation.json')
        bits = {row['mission']: int(row['bank_C']) for row in self.progress_rows}
        if (self.read_validation['disc_id'] != VERSION['disc_id'] or
                self.read_validation['revision'] != VERSION['revision'] or
                any(bits.get(mission) != record['bit'] or not record['proof']
                    for mission, record in self.read_validation['clear_bits'].items())):
            raise ValueError('native clear validation does not match PAL catalog')

    def snapshot(self, memory):
        memory.verify_revision()
        native = {}
        # Document/scene objects exist independently of a selected save. Failure
        # here must not hide previously validated clear reads.
        try:
            native['stage_objects'] = read_stage_objects(memory)
        except MemoryUnavailable as error:
            native['stage_objects_error'] = str(error)
        stage = next(iter(native.get('stage_objects', [])), {})
        application = stage.get('application')
        if application is not None and application != self.application:
            self.application = application
            self.session_epoch += 1
        session = f'pal-{self.instance}-{self.session_epoch}'
        active_rings = ({stage['mission']: frozenset(i + 1 for i in range(5)
                         if stage.get('current_red_ring_mask', 0) & (1 << i))}
                        if stage.get('mission') and stage.get('scene') in ('gameplay', 'results', 'dying') else {})
        trace = memory.trace_save_chain()
        chain = trace['chain']
        if chain is None:
            self.chain = None
            self.context_key = None
            self.stable_polls = 0
            return Snapshot(session, None, None, stage.get('scene', 'unclassified'), stage.get('mission'),
                            clicked_slot=stage.get('clicked_slot'),
                            scene_verified=stage.get('scene', 'unclassified') != 'unclassified',
                            rings_address=stage.get('player', {}).get('rings_address'),
                            lives_address=stage.get('lives_address'),
                            active_rings=active_rings,
                            death_state='dying' if stage.get('scene') == 'dying' else
                                        'alive' if stage.get('scene') == 'gameplay' and stage.get('player') else 'unknown',
                            status=f"save_container_unavailable: {trace['status']}; prologue/menu state needs native tracing",
                            evidence={'manager_global': 'code-derived: 0x808F3628', 'save_chain_trace': trace,
                                      'native_data': native})
        context_key = (application, stage.get('context'), stage.get('mission'), stage.get('scene'),
                       stage.get('player_actor_id'), chain)
        if chain != self.chain or context_key != self.context_key:
            self.chain = chain
            self.context_key = context_key
            self.stable_polls = 0
        self.stable_polls += 1
        bank = bytes.fromhex(trace['steps'][-1]['hex'])
        def candidate_set(bit):
            offset = (bit // 32) * 4
            return bool(int.from_bytes(bank[offset:offset + 4], 'big') & (1 << (bit % 32)))
        candidates = frozenset(row['mission'] for row in self.progress_rows
                               if candidate_set(int(row['bank_C'])))
        validated = frozenset(self.read_validation['clear_bits'])
        try:
            native['saved_progress'] = read_saved_progress(memory, self.progress_rows)
        except MemoryUnavailable as error:
            native['saved_progress_error'] = str(error)
        saved = native.get('saved_progress', {})
        # The trace and the bounded accessor are separate reads. Do not credit
        # an old slot's trace if selection changed before the accessor ran.
        coherent_progress = bool(saved) and saved['chain'] == chain
        if coherent_progress:
            bank = bytes.fromhex(saved['flag_words_hex'])
            candidates = frozenset(row['mission'] for row in self.progress_rows
                                   if candidate_set(int(row['bank_C'])))
        else:
            saved = {}
        scene = stage.get('scene', 'unclassified')
        # Factory defaults from 8015EBC0, corroborated by original Act 1
        # captures. Neither a command nor a selected-slot number proves New Game.
        # 8016DEF8 also sets bank B (entered) for the mandatory first act.
        initial_bits = (20, 27, 30, 90, *(210 + i * 3 for i in range(7)))
        initial_words = [0] * 16
        for bit in initial_bits:
            initial_words[bit // 32] |= 1 << (bit % 32)
        initial_bank = b''.join(word.to_bytes(4, 'big') for word in initial_words).hex()
        fresh_flags = saved.get('flag_words_hex') == initial_bank
        fresh_records = bool(saved) and all(record['raw_rank'] == 255 and record['score'] == record['time_raw'] == 0
                                            for record in saved['rank_records'].values())
        new_game = scene == 'gameplay' and stage.get('mission') == 'stg110' and fresh_flags and fresh_records
        player = stage.get('player', {})
        # The chain and validated subset are real reads. No scene, UI-slot number or
        # stable save identity can be inferred from their heap addresses alone.
        return Snapshot(session, None, None, scene, stage.get('mission'),
                        clicked_slot=stage.get('clicked_slot'),
                        stable_polls=self.stable_polls, candidate_clears=candidates,
                        progress_verified=coherent_progress,
                        persisted_clears=candidates if coherent_progress else frozenset(),
                        persisted_rings={mission: frozenset(rings) for mission, rings in saved.get('physical_red_rings', {}).items()},
                        active_rings=active_rings,
                        # 8019DF48 returns rank-table index 0..3 (S,A,B,C),
                        # 4 for D; 8015F86C initializes unused records to FF.
                        # Read the awarded record byte, never infer from score.
                        awarded_ranks={mission: record['raw_rank'] for mission, record in saved.get('rank_records', {}).items()
                                       if 0 <= record['raw_rank'] <= 3},
                        new_game_verified=new_game, fresh_fields=(fresh_flags, fresh_records),
                        scene_verified=scene != 'unclassified',
                        death_state='dying' if scene == 'dying' else 'alive' if scene == 'gameplay' and player else 'unknown',
                        rings_address=player.get('rings_address'), lives_address=stage.get('lives_address'),
                        evidence={'chain': chain, 'save_chain_trace': trace,
                                  'progress_c': '66 native bank C reads; only listed subset live-read validated',
                                  'validated_clear_missions': sorted(validated),
                                  'internal_selected_index': chain[2], 'native_data': native},
                        status=('native scene/stats/physical rings read; stable save identity and writes remain blocked'
                                if coherent_progress else
                                'save trace only; coherent native progress unavailable; checks and writes blocked'))

    def invalidate_session(self):
        if self.application is not None or self.chain is not None:
            self.session_epoch += 1
        self.application = self.chain = self.context_key = None
        self.stable_polls = 0

    def require(self, capability):
        if not VERSION['capabilities'].get(capability, False):
            raise MemoryUnavailable(f'WRITE_BLOCKED: requires_verified_hook: {capability}')

    def project_permissions(self, memory, snapshot, inventory, slot_data):
        self.require('world_access')
        self.require('wisp_permissions')
        self.require('game_land_gates')
        self.require('emeralds')
        raise MemoryUnavailable('WRITE_BLOCKED: native permission projection not implemented')

    def kill(self, memory, snapshot):
        self.require('native_death')
        raise MemoryUnavailable('WRITE_BLOCKED: native kill routine not resolved')

    def swim(self, memory, snapshot, enabled):
        self.require('swimming')
        raise MemoryUnavailable('WRITE_BLOCKED: reversible swimming state not resolved')
