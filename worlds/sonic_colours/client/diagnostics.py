from .versions import VERSION
from .memory import MemoryUnavailable
from .runtime import inventory
from .evidence import evidence_registry
from .build_info import implementation_info


NATIVE_BLOCKERS = {
    'save_identity': 'Native intro/profile witness binding implemented; no globally unique native ID or in-game resume validation.',
    'stats': 'Guarded native counter delivery and durable deferral implemented; visible HUD effects require live verification.',
    'world_access': 'Sequential / Open Acts permission policy implemented; both modes need live map/boss validation.',
    'wisp_permissions': 'Seven colour save/live fields and the native setter hook enforce AP ownership; White Boost/scripted player grants remain unresolved.',
    'game_land_gates': 'AP ring thresholds project native gate bits without inventing physical collectibles; full Game Land navigation requires gameplay verification.',
    'emeralds': 'Super flag resolved; individual native emerald award inventory and independent boost not resolved.',
    'native_death': 'Player death event observed; safe native invocation and cache-coherent execution not resolved.',
    'swimming': 'No verified reversible swimming state; existing Gecko patch has unresolved goal interference.',
    'stage_shuffle': 'Native mission table read; intro-safe stage dispatch rewrite not implemented.',
    'music': 'Verified original 87-cue CSB in MEM2 can be seed-shuffled without files; all playback paths require live testing.',
    'capsule_open': 'Native instance/open transitions report immediately; live coloured model refresh uses the supplied PAL Gecko hook.',
}


def diagnostic(ctx, memory=None):
    result = {'status': ctx.dolphin_status, 'disc_id': VERSION['disc_id'],
              'expected_revision': VERSION['revision'], 'live_verified': VERSION['live_verified'],
              'capabilities': VERSION['capabilities'], 'save_armed': False,
              'patches_installed': [], 'death_link': 'disabled: native death unverified'}
    result['operation_status'] = dict(getattr(ctx, 'operation_status', {}))
    result['authenticated_ap_identity'] = getattr(ctx, 'authenticated_identity', None)
    result.update(implementation=getattr(ctx, 'implementation', None) or implementation_info(),
                  current_status_time_utc=getattr(ctx, 'status_time_utc', None),
                  dolphin_instance=getattr(ctx, 'dolphin_instance', None),
                  latest_acknowledged_location=getattr(ctx, 'latest_acknowledged_location', None),
                  experimental_direct_hooks=getattr(ctx, 'direct_hook_status', None),
                  operation_blockers={name: reason for name, reason in NATIVE_BLOCKERS.items()
                                      if not VERSION['capabilities'].get(name, False)})
    # Historical successful accesses remain timestamped; they do not imply that
    # the current Dolphin connection is active or that the current disc is PAL.
    current_memory = memory or getattr(ctx, 'memory', None)
    result.update(latest_successful_read=getattr(current_memory, 'latest_read', None),
                  latest_successful_write=getattr(current_memory, 'latest_write', None),
                  last_revision_observation=getattr(current_memory, 'revision_observation', None))
    instance = result['dolphin_instance'] or {}
    observed = result['last_revision_observation'] or {}
    result['current_disc_verified'] = bool(instance.get('emulation_active') and observed.get('verified'))
    result['native_field_grades'] = {name: evidence.grade.value for name, evidence in evidence_registry().items()}
    from ..world_constants import load_data
    result['validated_read_clear_missions'] = sorted(load_data('native_read_validation.json')['clear_bits'])
    result['write_capabilities'] = VERSION['capabilities']
    if ctx.runtime:
        runtime = ctx.runtime
        owned = inventory([i.item for i in ctx.items_received])
        result.update({'save_armed': runtime.guard.armed, 'ap_red_rings': owned['red_rings'],
                       'emerald_count': len(owned['emeralds']), 'wisps': owned['wisps'],
                       'white_boost': 'White Boost Wisp' in owned['wisps'],
                       'history_ready': ctx.history_ready, 'pending_effects': runtime.pending_effects(),
                       'item_receipts': runtime.item_details()})
        result.update({'playthrough_state': runtime.guard.state.value, 'identity_status': runtime.guard.reason,
                       'bootstrap_checks': len(runtime.journal.data.get('bootstrap', {}).get('checks', [])),
                       'super_sonic_ap_permission': owned['super_sonic_allowed']})
        if runtime.snapshot:
            stage = next(iter(runtime.snapshot.evidence.get('native_data', {}).get('stage_objects', [])), {})
            player = stage.get('player', {})
            result.update(rings=player.get('rings'), lives=stage.get('lives'), boost=player.get('boost'),
                          clicked_slot=runtime.snapshot.clicked_slot, real_stage_id=stage.get('real_stage_id'),
                          native_bgm_cue=stage.get('bgm_cue'),
                          held_wisp=player.get('held_wisp'), death_state=runtime.snapshot.death_state,
                          physical_red_ring_mask=stage.get('current_red_ring_mask'),
                          native_death_count=stage.get('death_count'))
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
        from .capsule_refresh import installed
        try:
            result['capsule_refresh_hook'] = installed(memory)
        except MemoryUnavailable as error:
            result['capsule_refresh_hook'] = str(error)
        result['save_chain_trace'] = memory.trace_save_chain()
        try:
            chain = memory.resolve_flags_ptr()
            result['candidate_chain'] = dict(zip(('manager', 'container', 'selected_index', 'selected_save', 'flags'), chain))
            result['candidate_chain_status'] = 'static chain only; visible slot and semantics unverified'
        except MemoryUnavailable as error:
            result['candidate_chain_status'] = str(error)
    return result
