"""Only this adapter may interpret native gameplay structures.

Candidate chain/C-bank reads are implemented; native scene, identity and
persistence promotion still require live proof. Static addresses are not setters.
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

    def snapshot(self, memory):
        memory.verify_revision()
        try:
            chain = memory.resolve_flags_ptr()
        except MemoryUnavailable as error:
            self.chain = None
            self.stable_polls = 0
            return Snapshot(f'pal-unresolved-{self.session_epoch}', None, None, 'unclassified', None,
                            status=f'save_container_unavailable: {error}; prologue/menu state needs native tracing',
                            evidence={'manager_global': 'code-derived: 0x808F3628'})
        if chain != self.chain:
            self.chain = chain
            self.session_epoch += 1
            self.stable_polls = 0
        self.stable_polls += 1
        flags = chain[-1]
        candidates = frozenset(row['mission'] for row in self.progress_rows
                               if memory.read_progress_bit(flags, int(row['bank_C'])))
        if memory.resolve_flags_ptr() != chain:
            self.chain = None
            self.stable_polls = 0
            raise MemoryUnavailable('read_context_changed: candidate save chain changed during polling')
        # The chain and clear bits are real reads. No scene, UI-slot number or
        # stable save identity can be inferred from their heap addresses alone.
        return Snapshot(f'pal-chain-{self.session_epoch}', None, None, 'unclassified', None,
                        stable_polls=self.stable_polls, candidate_clears=candidates,
                        evidence={'chain': chain, 'progress_c': 'code-derived; live persistence pending',
                                  'internal_selected_index': chain[2]},
                        status='candidate_progress_read: native New Game, scene and stable save identity unresolved')

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
