from .versions import VERSION
from .memory import MemoryUnavailable
from .runtime import inventory
from .evidence import evidence_registry


def diagnostic(ctx, memory=None):
    result = {'status': ctx.dolphin_status, 'disc_id': VERSION['disc_id'],
              'expected_revision': VERSION['revision'], 'live_verified': VERSION['live_verified'],
              'capabilities': VERSION['capabilities'], 'save_armed': False,
              'patches_installed': [], 'death_link': 'disabled: native death unverified'}
    result['native_field_grades'] = {name: evidence.grade.value for name, evidence in evidence_registry().items()}
    from ..world_constants import load_data
    result['validated_read_clear_missions'] = sorted(load_data('native_read_validation.json')['clear_bits'])
    result['write_capabilities'] = VERSION['capabilities']
    if ctx.runtime:
        runtime = ctx.runtime
        owned = inventory([i.item for i in ctx.items_received])
        result.update({'save_armed': runtime.guard.armed, 'ap_red_rings': owned['red_rings'],
                       'emerald_count': len(owned['emeralds']), 'wisps': owned['wisps'],
                       'white_boost': 'White Boost Unlock' in owned['wisps'],
                       'history_ready': ctx.history_ready, 'pending_effects': runtime.pending_effects()})
        result.update({'playthrough_state': runtime.guard.state.value, 'identity_status': runtime.guard.reason,
                       'bootstrap_checks': len(runtime.journal.data.get('bootstrap', {}).get('checks', [])),
                       'super_sonic_ap_permission': owned['super_sonic_allowed'] if
                       runtime.slot_data['options']['chaos_emerald_items'] else 'vanilla'})
        if runtime.snapshot:
            result.update({'scene': runtime.snapshot.scene, 'actual_mission': runtime.snapshot.actual_mission,
                           'native_status': runtime.snapshot.status, 'native_evidence': runtime.snapshot.evidence,
                           'candidate_clears': sorted(runtime.snapshot.candidate_clears),
                           'validated_persisted_clears': sorted(runtime.snapshot.persisted_clears),
                           'missing_native_fields': [name for name, ready in (
                               ('new_game_indicator', runtime.snapshot.new_game_verified),
                               ('scene', runtime.snapshot.scene_verified),
                               ('actual_mission', runtime.snapshot.actual_mission is not None),
                               ('stable_save_identity', runtime.snapshot.save_identity_verified)) if not ready],
                           'progress_verified': runtime.snapshot.progress_verified})
    if memory:
        result['save_chain_trace'] = memory.trace_save_chain()
        try:
            chain = memory.resolve_flags_ptr()
            result['candidate_chain'] = dict(zip(('manager', 'container', 'selected_index', 'selected_save', 'flags'), chain))
            result['candidate_chain_status'] = 'static chain only; visible slot and semantics unverified'
        except MemoryUnavailable as error:
            result['candidate_chain_status'] = str(error)
    return result
