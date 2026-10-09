"""Only this adapter may interpret native gameplay structures.

The selected-save flags are inline. Only individually validated clear bits
are authoritative reads; native scene/identity and every writer remain gated.
"""
from .memory import MemoryUnavailable
from .versions import VERSION
from .state import Snapshot
from ..world_constants import load_data


class NativeHooks:
    def __init__(self):
        self.chain = None
        self.stable_polls = 0
        self.session_epoch = 0
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
        trace = memory.trace_save_chain()
        chain = trace['chain']
        if chain is None:
            self.chain = None
            self.stable_polls = 0
            return Snapshot(f'pal-unresolved-{self.session_epoch}', None, None, 'unclassified', None,
                            status=f"save_container_unavailable: {trace['status']}; prologue/menu state needs native tracing",
                            evidence={'manager_global': 'code-derived: 0x808F3628', 'save_chain_trace': trace})
        if chain != self.chain:
            self.chain = chain
            self.session_epoch += 1
            self.stable_polls = 0
        self.stable_polls += 1
        bank = bytes.fromhex(trace['steps'][-1]['hex'])
        def candidate_set(bit):
            offset = (bit // 32) * 4
            return bool(int.from_bytes(bank[offset:offset + 4], 'big') & (1 << (bit % 32)))
        candidates = frozenset(row['mission'] for row in self.progress_rows
                               if candidate_set(int(row['bank_C'])))
        validated = frozenset(self.read_validation['clear_bits'])
        # The chain and validated subset are real reads. No scene, UI-slot number or
        # stable save identity can be inferred from their heap addresses alone.
        return Snapshot(f'pal-chain-{self.session_epoch}', None, None, 'unclassified', None,
                        stable_polls=self.stable_polls, candidate_clears=candidates,
                        progress_verified=bool(validated), persisted_clears=candidates & validated,
                        evidence={'chain': chain, 'save_chain_trace': trace, 'progress_c': 'only listed subset live-read validated; remaining bits code-derived',
                                  'validated_clear_missions': sorted(validated),
                                  'internal_selected_index': chain[2]},
                        status='validated_clear_subset_read: native New Game, scene and stable save identity unresolved')

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
