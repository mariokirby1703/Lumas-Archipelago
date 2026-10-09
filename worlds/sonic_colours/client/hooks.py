"""Only this adapter may interpret native gameplay structures.

No PAL gameplay adapter is released yet. Static research addresses are leads,
never a substitute for validated scene, save and persistence semantics.
"""
from .memory import MemoryUnavailable
from .versions import VERSION


class NativeHooks:
    def snapshot(self, memory):
        # The chain can be inspected by /sonicdebug without treating it as a
        # recognized save slot or sending irreversible multiplayer checks.
        raise MemoryUnavailable('save_slot_mapping_unverified: manager global candidate 0x808F3628; '
                                'requires visible Slot 1, fresh identity and scene validation')

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
