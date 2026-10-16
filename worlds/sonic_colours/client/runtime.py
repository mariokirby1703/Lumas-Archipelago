from collections import Counter
import logging
import time
import hashlib
import json
import math
import struct
from ..Items import BY_ID, ITEM_TABLE, RING_VALUES, EMERALDS, WISP_ITEMS, ALL_WISP_ITEMS, FILLER, LEGACY_FILLER, TRAPS
from ..Locations import LOCATION_TABLE, enabled
from ..Options import SonicColoursOptions, OPTION_NAMES
from ..world_constants import GAME, SCHEMA_VERSION, STAGES, BY_MISSION, game_land_gates
from .memory import MemoryUnavailable

logger = logging.getLogger('Client')
from . import quiet_logging
DELIVERY_ITEMS = FILLER + LEGACY_FILLER + TRAPS


def rings_amount(journal, index):
    """One seed/receipt-owned roll, persisted before any native attempt."""
    key = str(index)
    effect = journal.data['effects'].get(key, {})
    if 'rolled_amount' not in effect:
        # Rejection sampling avoids modulo bias over the 100 possible amounts.
        identity = json.dumps(journal.identity, sort_keys=True, separators=(',', ':'))
        nonce = 0
        while True:
            value = int.from_bytes(hashlib.sha256(f'{identity}:rings:{index}:{nonce}'.encode()).digest(), 'big')
            ceiling = (1 << 256) // 100 * 100
            if value < ceiling:
                break
            nonce += 1
        effect = {'state': 'queued', **effect, 'rolled_amount': value % 100 + 1}
        journal.data['effects'][key] = effect
        journal.save()
    return effect['rolled_amount']


def validate_slot(data):
    if not isinstance(data, dict) or data.get('game') != GAME or data.get('schema_version') != SCHEMA_VERSION:
        raise ValueError('Sonic Colours schema 7 required: movement/Swim/Breath item IDs and options. Regenerate seed and .apsonic; do not reuse old seed journals.')
    if not isinstance(data.get('seed_name'), str) or not data['seed_name']:
        raise ValueError('slot seed identity missing')
    revision=data.get('options_revision',0)
    if type(revision) is not int or not 0<=revision<=7:raise ValueError('unsupported slot options revision')
    options = data.get('options')
    # Old seeds have no physical 1-Up locations; adding the optional toggle
    # must not force regeneration or change their selected location set.
    if isinstance(options,dict) and 'one_up_sanity' not in options:
        options={**options,'one_up_sanity':0}
        data={**data,'options':options}
    legacy_options=data.get('options_revision',0)<2
    if isinstance(options,dict):
        options={k:v for k,v in options.items() if k not in ('ap_item_hud','swim_trap_weight','swim_trap_duration')}
        options.setdefault('score_reset_trap_weight',0)
        options.setdefault('dead_weight_trap_weight',0)
        if data.get('options_revision',0)<5:options.setdefault('native_feature_tests',0)
        if data.get('options_revision',0)<3:
            options.setdefault('super_sonic',1)
        data={**data,'options':options}
    if not isinstance(options, dict) or set(options) != set(OPTION_NAMES):
        raise ValueError('slot options missing or unexpected')
    resolved = {}
    for name in OPTION_NAMES:
        value = options[name]
        if type(value) is not int:
            raise ValueError(f'slot option {name} must be resolved integer')
        cls = SonicColoursOptions.type_hints[name]
        # Retired Game Land goal: readable only in already generated slots.
        if name=='goal' and value==3 and revision<7:
            resolved[name]=cls(value)
            continue
        # Previously generated Super Sonic goal seeds remain playable.
        # New generators no longer offer this goal.
        if name=='goal' and value==4 and data.get('options_revision',0)<3:
            resolved[name]=cls(value)
            continue
        option = cls.from_any(value)
        if getattr(option, 'options', None) and value not in option.options.values():
            raise ValueError(f'invalid choice {name}')
        if hasattr(option, 'range_start') and not option.range_start <= value <= option.range_end:
            raise ValueError(f'invalid range {name}')
        resolved[name] = option
    from ..world_constants import legacy_game_land_gates
    current_gates=game_land_gates(options['game_land_requirement_reduction'])
    previous_gates={**current_gates,'1-1':1}
    if data.get('game_land_gates') not in (current_gates,previous_gates,legacy_game_land_gates(options['game_land_requirement_reduction'])):
        raise ValueError('slot Game Land gates mismatch')
    data={**data,'game_land_gates':{**data['game_land_gates'],'1-1':0}}
    expected_speed = (bool(options['game_land_checks'] or options['chaos_emerald_checks'] or options['goal'] == 3 or options['wisp_capsules'] or options['eggman_heart_sanity'])
                      if legacy_options else bool(options['game_land_checks']))
    if type(data.get('game_land_speed_items')) is not bool or data['game_land_speed_items'] != expected_speed:
        raise ValueError('slot Game Land speed pool contract mismatch')
    expected_mapping = {s['stage_slot_id']: s['mission_id'] for s in STAGES}
    if data.get('stage_mapping') != expected_mapping:
        raise ValueError('unsupported native stage permutation')
    from types import SimpleNamespace
    if revision>=6 and not options['game_land_checks'] and (options['eggman_heart_sanity'] or options['chaos_emerald_checks']):
        raise ValueError('Game Land master switch requires disabled Heart/Emerald checks')
    expected_locations = {n: d.code for n, d in LOCATION_TABLE.items()
                          if enabled(d, SimpleNamespace(**resolved),respect_game_land=revision>=6)}
    # Display-name migration only; stable IDs and enabled location set must
    # still match exactly. Existing servers may retain the old Discovery label.
    legacy_discoveries = {n.removesuffix(' Discovery')+' - First Discovery':n
                          for n in expected_locations if n.endswith(' Discovery')}
    if isinstance(data.get('locations'), dict):
        data = {**data, 'locations':{legacy_discoveries.get(n,n):code
                                    for n,code in data['locations'].items()}}
    if data.get('locations') != expected_locations:
        raise ValueError('slot locations do not match option-selected stable IDs')
    if options['wisp_capsules'] and not any(LOCATION_TABLE[n].kind == 'capsule' for n in expected_locations):
        raise ValueError('wisp_capsules: no validated accessible capsule instances')
    if data.get('logic_policy') != ('sheet_v2' if data.get('options_revision',0)>=5 else 'provisional_clears_conservative_pickups'):
        raise ValueError('slot logic policy mismatch; regenerate with matching world/client')
    if data.get('mandatory_prologue') != ['stg110', 'stg130']:
        raise ValueError('unsupported native prologue contract')
    if data.get('starting_world') != 0 or 'starting_slot' in data:
        raise ValueError('expected fixed Tropical Resort starting world and vanilla intro')
    for name in ('death_link',):
        from .versions import VERSION
        if options[name] and not options.get('native_feature_tests') and not VERSION.get('live_validation',{}).get('deathlink'):
            raise ValueError(f'{name}: requires_verified_hook')
    return data


def inventory(item_ids):
    unknown = set(item_ids) - BY_ID.keys()
    if unknown:
        raise ValueError(f'unknown item IDs: {sorted(unknown)}')
    counts = Counter(BY_ID[item] for item in item_ids)
    return {'counts': counts, 'red_rings': sum(counts[n] * v for n, v in RING_VALUES.items()),
            'emeralds': [n for n in EMERALDS if counts[n]], 'wisps': [n for n in ALL_WISP_ITEMS if counts[n]],
            'super_sonic_allowed': all(counts[n] for n in EMERALDS)}


def detect_checks(slot_data, snapshot, owned_wisps=frozenset()):
    checks = set()
    for name, code in slot_data['locations'].items():
        data = LOCATION_TABLE[name]
        # This reconciler is for native progress. Physical pickup checks are
        # produced by observe_pickups(), never imported from a historical save.
        rings = snapshot.persisted_rings.get(data.mission, frozenset())
        if (data.kind == 'clear' and data.mission in snapshot.persisted_clears
                or data.kind == 'ring' and data.index in rings
                or data.kind == 'rings' and frozenset(range(1, 6)) <= rings
                or data.kind == 'rank' and data.mission in snapshot.awarded_ranks
                   and 0 <= snapshot.awarded_ranks[data.mission] <= data.index
                or data.kind == 'emerald' and data.index in snapshot.emerald_rewards
                   and snapshot.evidence.get('native_data',{}).get('progression_events',{}).get('game_land_clears',0)
                       & (7 << ((data.index-1)*3))
                   and all(s['mission_id'] in snapshot.persisted_clears for s in STAGES
                           if s['zone_index'] == data.index + 6)
                or data.kind == 'capsule' and capsule_check_allowed(slot_data, data, snapshot, owned_wisps)
                or data.kind == 'wisp' and data.index in snapshot.discovered_wisps):
            checks.add(code)
    return checks


def capsule_check_allowed(slot_data, data, snapshot, owned_wisps):
    from ..capsules import CAPSULES
    capsule = CAPSULES[data.instance_key]
    if not capsule.eligible or capsule.key not in snapshot.opened_capsules:
        return False
    from ..wisps import wisp_level
    colour = capsule.wisp_item.removeprefix('Progressive ').removesuffix(' Wisp')
    # The selected YAML may provide a single normal Wisp, two progressive
    # tiers, or vanilla White Boost. Keep the actual opening as the witness.
    counts = Counter({name: 1 for name in owned_wisps})
    return wisp_level(counts, colour, slot_data.get('options', {})) >= 1


def victory(slot_data, snapshot, ever_collected_mask=None, owned=None, observed_clears=frozenset()):
    goal = slot_data['options']['goal']
    clears = snapshot.persisted_clears | observed_clears
    if goal == 0:
        return {'stg790', 'stg720'} <= clears
    if goal == 1:
        return all(s['mission_id'] in clears for s in STAGES if s['kind'] == 'Boss')
    if goal == 2:
        return all((ever_collected_mask or {}).get(s['mission_id'], 0) == 31
                   for s in STAGES if s['normal'])
    if goal == 3:
        return all(s['mission_id'] in clears for s in STAGES if s['zone_index'] >= 7)
    if goal == 4:
        return bool(owned and owned['super_sonic_allowed'])
    raise ValueError('unsupported goal')


class Runtime:
    def __init__(self, slot_data, journal, guard, hooks):
        self.slot_data = validate_slot(slot_data)
        self.journal, self.guard, self.hooks = journal, guard, hooks
        # Read-only/replay adapters need not implement native control status.
        # Their pickup checkpoint must not fail on optional diagnostics.
        if self.hooks is not None and not hasattr(self.hooks,'gameplay_controls_status'):
            self.hooks.gameplay_controls_status={}
        self.snapshot = None
        from .test_inventory import LocalInventoryOverrides
        self.test_inventory = LocalInventoryOverrides(self.slot_data['options'])
        from .ap_hud_ticker import Ticker
        self.hud_ticker=Ticker(journal)
        self.last_error = None
        self.pickup_masks = {}
        self.pickup_started = False
        self.initial_pickup_exclusions = {}
        self.capsule_states = {}
        self.capsule_started = False
        self.inflight = {}
        self.deferred = {}
        self.retry_after = {}
        self.clock = time.monotonic
        self.resource_music = None
        self.music_status = {'status':'off' if not self.slot_data['options']['music_randomization'] else 'waiting for verified in-memory CSB bank',
                             'audible_verified':False}
        self.next_music_poll = 0.0
        self.experimental_direct_hooks = False
        self.boost_gain_status = {'status': 'waiting for verified living Sonic'}
        self.intro_box_status = {'status':'not observed','applied':False}
        self.movement_status = {'status': 'Movement Unlocks off or waiting for Dolphin',
                                'native_gate_verified': False, 'swim_gate_verified': False,
                                'breath_gate_verified': False}

    def observe_capsules(self, owned_wisps):
        from ..capsules import CAPSULES
        snapshot = self.snapshot
        from .capsule_capture import read_events,control_context
        memory=getattr(self,'_capsule_memory',None)
        native=bool(memory and getattr(memory,'native_patch',None))
        if native:
            # The guest event is the pickup witness. A bound map/result can
            # consume it after the actor/stage has disappeared from host scans.
            try:context=control_context(memory,snapshot,self.guard)
            except MemoryUnavailable:return
        elif not self.guard.can_record_pickups(snapshot):return
        captured=read_events(memory,getattr(self,'_capsule_event_cursor',0)) if native else None
        if captured is not None:
            from ..capsules import CAPSULES_BY_NATIVE_ID
            head,entries,overflow=captured
            locations={LOCATION_TABLE[n].instance_key:code for n,code in self.slot_data['locations'].items()
                       if LOCATION_TABLE[n].kind=='capsule'}
            events=[];checks=set()
            if context!=control_context(memory,snapshot,self.guard):
                raise MemoryUnavailable('capsule capture context changed during consume')
            from .progression_hook import identity_tag
            tag=identity_tag(self.journal.identity)
            for entry in entries:
                if entry['session_tag']!=tag:continue
                if (entry['container'],entry['save_index'])!=(context[1],context[2]):continue
                capsule=CAPSULES_BY_NATIVE_ID.get((entry['mission'],entry['object_id'],entry['instance']))
                if not capsule or not capsule.eligible or capsule.raw_wisp!=entry['raw_wisp']:continue
                code=locations.get(capsule.key)
                if code is None or code in self.journal.data['pickup_checks'] or code in checks:continue
                checks.add(code);events.append({'kind':'capsule','mission':capsule.mission,
                    'instance_key':capsule.key,'object_id':entry['object_id'],'native_session_tag':tag,
                    'provenance':'PAL_800D4CF0_committed_opening','native_sequence':entry['sequence']})
            if events:self.journal.record_pickups(events,{},checks)
            self._capsule_event_cursor=head
            self.capsule_capture_status={'installed':True,'native_head':head,'overflow':overflow,
                                        'status':'native successful-opening events consumed'}
            return
        stage = next(iter(snapshot.evidence.get('native_data', {}).get('stage_objects', [])), {})
        if 'capsules' not in stage:
            return
        baseline = not self.capsule_started
        self.capsule_started = True
        seen = {event.get('instance_key') for event in self.journal.data['pickup_events'] if event['kind'] == 'capsule'}
        locations = {LOCATION_TABLE[name].instance_key: code for name, code in self.slot_data['locations'].items()
                     if LOCATION_TABLE[name].kind == 'capsule'}
        events, checks = [], set()
        for native in stage['capsules']:
            key = native['key']
            token = snapshot.stage_epoch, key
            previous = self.capsule_states.get(token, False)
            self.capsule_states[token] = native['opened']
            capsule = CAPSULES.get(key)
            # Native opening is the check witness. Permission enforcement is
            # separate; reporting must not wait for ReceivedItems (White Boost
            # capsules are usable without its item when Boost Lock is off).
            if (baseline or previous or not native['opened'] or key in seen or key not in locations
                    or not capsule or capsule.mission != snapshot.actual_mission or not capsule.eligible):
                continue
            checks.add(locations[key])
            events.append({'kind': 'capsule', 'mission': capsule.mission, 'instance_key': key,
                           'stage_epoch': snapshot.stage_epoch, 'actor_id': native['actor_id'],
                           'sequence': len(self.journal.data['pickup_events']) + len(events)})
        if events:
            self.journal.record_pickups(events, {}, checks)
            quiet_logging.record('pickup', 'Pickup detected: opened capsules %s; Location queued: %s',
                        [event['instance_key'] for event in events], sorted(checks))

    def observe_results(self):
        snapshot = self.snapshot
        result = snapshot.current_result
        if (not self.guard.can_record_pickups(snapshot) or snapshot.scene != 'results'
                or not result.get('final') or result.get('mission') != snapshot.actual_mission
                or type(result.get('grade')) is not int or not 0 <= result['grade'] <= 4):
            return
        checks = {code for name, code in self.slot_data['locations'].items()
                  if LOCATION_TABLE[name].mission == snapshot.actual_mission
                  and (LOCATION_TABLE[name].kind == 'clear'
                       or LOCATION_TABLE[name].kind == 'rank' and result['grade'] <= LOCATION_TABLE[name].index)}
        checks -= set(self.journal.data['checks'])
        epoch = self.journal.data.get('bootstrap', {}).get('epoch')
        new_intro_witness = (self.journal.data.get('save_identity') is None
            and snapshot.actual_mission in ('stg110','stg130') and epoch is not None
            and not any(e.get('kind') == 'result' and e.get('mission') == snapshot.actual_mission
                        and e.get('playthrough_epoch') == epoch
                        and e.get('session') == snapshot.session
                        for e in self.journal.data.get('pickup_events', ())))
        if checks or new_intro_witness:
            self.journal.record_pickups([{'kind': 'result', 'mission': snapshot.actual_mission,
                'grade': result['grade'], 'score': result.get('score'),
                'session': snapshot.session, 'playthrough_epoch': epoch,
                'stage_epoch': snapshot.stage_epoch,
                'provenance': result['provenance']}], {}, checks)
            quiet_logging.record('result', 'Result detected: %s grade %s; Location queued: %s',
                        snapshot.actual_mission, result['grade'], sorted(checks))

    def observe_pickups(self):
        snapshot = self.snapshot
        if not self.guard.can_record_pickups(snapshot):
            return
        mission = snapshot.actual_mission
        if not BY_MISSION.get(mission, {}).get('normal'):
            return
        rings = snapshot.active_rings.get(mission, frozenset())
        if any(type(ring) is not int or not 1 <= ring <= 5 for ring in rings):
            raise MemoryUnavailable('pickup mask contains invalid physical ring identity')
        mask = sum(1 << (ring - 1) for ring in rings)
        epoch = snapshot.stage_epoch
        if not self.pickup_started:
            # Baseline on first attribution: never credit state predating this
            # client's observation. Later stage loads belong to this playthrough.
            self.pickup_masks[epoch] = mask
            self.initial_pickup_exclusions[mission] = mask
            self.pickup_started = True
            return
        previous = self.pickup_masks.get(epoch, 0)
        self.pickup_masks[epoch] = mask
        excluded = self.initial_pickup_exclusions.get(mission, 0) & mask
        self.initial_pickup_exclusions[mission] = excluded
        mode = self.slot_data['options']['red_ring_checks']
        ever = self.journal.data['ever_collected_mask'].get(mission, 0)
        from .physical_rings import witnessed
        physical_ever = witnessed(self.journal).get(mission, 0)
        added = mask & ~previous & ~physical_ever & ~excluded
        if not added:
            return
        updated = ever | added
        events = [{'kind': 'red_ring', 'mission': mission, 'ring': ring,
                   'stage_epoch': epoch, 'playthrough_epoch': (self.journal.data.get('bootstrap', {}).get('epoch')
                       or (self.journal.data.get('native_binding') or {}).get('bootstrap_epoch')),
                   'sequence': len(self.journal.data['pickup_events']) + index}
                  for index, ring in enumerate(ring for ring in range(1, 6) if added & (1 << (ring - 1)))]
        checks = {code for name, code in self.slot_data['locations'].items()
                  if (LOCATION_TABLE[name].mission == mission and
                      (mode == 1 and LOCATION_TABLE[name].kind == 'ring' and
                       added & (1 << (LOCATION_TABLE[name].index - 1)) or
                       mode == 2 and LOCATION_TABLE[name].kind == 'rings' and updated == 31))}
        self.journal.record_pickups(events, {mission: updated}, checks)
        quiet_logging.record('pickup', 'Pickup detected: %s rings %s; Location queued: %s',
                    mission, [event['ring'] for event in events], sorted(checks))

    def poll(self, memory, item_ids, history_ready):
        steps=self.poll_steps(memory,item_ids,history_ready)
        while True:
            try:next(steps)
            except StopIteration as done:return done.value

    def poll_steps(self, memory, item_ids, history_ready):
        self._capsule_memory=memory
        self.snapshot = self.hooks.snapshot(memory)
        self.guard.observe(self.snapshot)
        # Capture irreversible pickup/result evidence before slow permission
        # writes. Network clients can transmit this checkpoint and receive
        # acknowledgements before continuing the same synchronous poll.
        self.observe_pickups()
        self.observe_results()
        if getattr(memory,'native_patch',None):
            try:
                from .capsule_capture import configure as arm_capture
                arm_capture(memory,self.snapshot,self.guard,self.journal)
                self.observe_capsules(frozenset())
            except MemoryUnavailable as error:
                self.capsule_capture_status={'installed':True,'status':'deferred: '+str(error)}
        can_send=self.guard.can_send(self.snapshot)
        if can_send and self.journal.data.get('save_identity') is not None:
            saved_checks=detect_checks(self.slot_data,self.snapshot)
            saved_checks-={code for name,code in self.slot_data['locations'].items()
                           if LOCATION_TABLE[name].kind in ('ring','rings','capsule')}
            self.journal.add_checks(saved_checks)
        yield (set(self.journal.data['checks']) if can_send else set(),
               bool(can_send and self.journal.data.get('goal_observed')))
        # Arm time-critical controls before the 90-cast HUD publication.
        early_items=list(item_ids if history_ready else self.journal.data['receipts'])
        early_items+=[item for item in self.journal.data.get('permission_receipts',()) if item not in early_items]
        early_owned=self.effective_inventory(inventory(early_items))
        from .capsule_refresh import configure as configure_early_capsules
        from .gameplay_controls import configure as configure_early_controls
        for name,action in (
                ('white_capsules',lambda:configure_early_capsules(memory,self.snapshot,early_owned,self.slot_data)),
                ('boost_controls',lambda:configure_early_controls(memory,self.snapshot,early_owned,self.slot_data,
                    temporary_boost=self.temporary_boost_allowed(memory),kinds=('boost_use','boost_query','boost_add')))):
            try:self.hooks.gameplay_controls_status[name]=action()
            except MemoryUnavailable as error:self.hooks.gameplay_controls_status[name]={'status':str(error)}
        self.enforce_white_boost_gain_lock(memory,early_owned)
        # Water entry and controller replacement must be handled before slow
        # journal, resource-bank and progression operations in this poll.
        if self.slot_data['options'].get('movement_unlocks'):
            early_items=list(item_ids if history_ready else self.journal.data['receipts'])
            early_items+=[item for item in self.journal.data.get('permission_receipts',()) if item not in early_items]
            early_owned=self.effective_inventory(inventory(early_items))
            from .movement_gate import configure as configure_movement
            from .water_native import configure as configure_breath
            for name,action in (('movement_status',configure_movement),('breath_status',configure_breath)):
                try:
                    result=(action(memory,self.snapshot,early_owned,transport=('direct' if self.experimental_direct_hooks else 'gecko')) if name=='movement_status'
                            else action(memory,self.snapshot,self.guard,early_owned,self.journal))
                    setattr(self,name,result)
                except MemoryUnavailable as error:
                    setattr(self,name,{'status':str(error),'write_verified':False})
        # Publish the HUD before owner configuration performs its guarded
        # writes. A new scene's music must not wait behind those transactions.
        try:
            from .native_events import status as event_status
            self.native_event_status=event_status(memory)
        except MemoryUnavailable as error:
            self.native_event_status={'installed':False,'status':str(error)}
        try:
            from .ap_hud_connected import render as render_ap_hud
            self.hud_status=render_ap_hud(self,memory)
        except MemoryUnavailable as error:
            self.hud_status={'hud_ready':False,'status':str(error)}
            self.hud_ticker.elapsed_visible(False)
        try:
            from .event_controls import configure as configure_events
            self.native_event_status=configure_events(self,memory)
            self.temporary_trap_status={'name':'Dead Weight Trap','remaining':self.native_event_status['remaining'],
                                        'active':self.native_event_status['remaining']>0,'time_source':'native gameplay delta'}
            self._death_allowed_stages=getattr(self,'_death_allowed_stages',set())
            if (getattr(self,'_event_owner',None) and self.snapshot.scene=='gameplay'
                    and self.guard.can_record_pickups(self.snapshot)):
                self._death_allowed_stages.add(self._event_owner[2])
        except MemoryUnavailable as error:
            self.native_event_status={'installed':False,'status':str(error)}
        try:
            from .physical_rings import apply as restore_physical_rings
            self.physical_ring_status = restore_physical_rings(memory, self.snapshot, self.guard)
        except MemoryUnavailable as error:
            self.physical_ring_status = {'status':str(error), 'nand_flush_verified':False}
        if self.slot_data['options']['eggman_heart_sanity'] and self.guard.can_record(self.snapshot):
            try:
                self.guard.check(self.snapshot)
                from .medal_hook import observe, configure
                observe(memory, self.snapshot, self.journal, self.slot_data)
                self.hooks.medal_status = configure(memory, self.snapshot, self.journal)
            except MemoryUnavailable as error:
                self.hooks.medal_status = {'available': False, 'reason': str(error)}
        try:
            from .intro_box import apply as apply_intro_box
            self.intro_box_status = apply_intro_box(memory,self.snapshot,self.guard,self.slot_data)
        except MemoryUnavailable as error:
            self.intro_box_status = {'status':str(error),'applied':False}
        self.settle_effects(memory)
        durable = list(item_ids if history_ready else self.journal.data['receipts'])
        durable += [item for item in self.journal.data.get('permission_receipts',()) if item not in durable]
        known = self.effective_inventory(inventory(durable))
        if self.snapshot.scene in ('global_map','world_map','game_land_select'):
            try:
                self.guard.check(self.snapshot)
                self.project_permissions(memory,known)
            except MemoryUnavailable as error:
                self.hooks.progression_status={'available':False,'reason':str(error)}
        if not getattr(memory,'native_patch',None):self.observe_capsules(frozenset(known['wisps']))
        # Catch native enemy/script grants even if they bypass boost_add.
        # Do this BEFORE new AP refill receipts are applied, so the refill
        # is calculated from the genuinely AP-owned remaining balance.
        self.enforce_white_boost_gain_lock(memory, known)
        # Install native interception even before ReceivedItems finishes. Zero
        # or durable authenticated permissions do not authorize unknown items.
        if not history_ready and self.guard.can_record(self.snapshot):
            try:
                self.project_permissions(memory, known)
            except MemoryUnavailable as error:
                self.hooks.progression_status = {'available':False,'reason':str(error)}
        self.last_error = self.snapshot.status
        # The original CSB resource lives in MEM2 and is independently
        # identified by its full PAL digest. Unlike the old 36-Act mission
        # alias patch, this covers world maps, Game Land, menus and bosses.
        # Attempt immediately, including title / mandatory prologue, then
        # check periodically in case Sonic reloads the bank after a scene change.
        if self.clock() >= self.next_music_poll:
            self.next_music_poll = self.clock() + (10.0 if self.music_status.get('bank_address') else 2.0)
            try:
                from .live_music import apply
                self.music_status = apply(memory, self.slot_data, getattr(self,'music_test_pair',None))
            except MemoryUnavailable as error:
                self.music_status = {'status':str(error), 'audible_verified':False}
        owned = known if history_ready else None
        if history_ready:
            self.journal.record_history(item_ids)
        if self.guard.can_record(self.snapshot):
            # Before a selected native save is bound, only witnessed pickups
            # and final result events from the mandatory intro may grant AP
            # checks. Never import persisted bits from an unidentified slot.
            checks = (detect_checks(self.slot_data, self.snapshot,
                                   frozenset(owned['wisps']) if owned else frozenset())
                      if self.journal.data['save_identity'] is not None else set())
            checks -= {code for name, code in self.slot_data['locations'].items()
                       if LOCATION_TABLE[name].kind in ('ring', 'rings', 'capsule')}
            observed = frozenset(e['mission'] for e in self.journal.data['pickup_events'] if e['kind'] == 'result')
            goal = victory(self.slot_data, self.snapshot, self.journal.data['ever_collected_mask'],
                           inventory(durable) if self.slot_data['options']['goal'] == 4 else owned, observed)
            if self.guard.can_send(self.snapshot):
                self.journal.add_checks(checks)
                if goal and not self.journal.data.get('goal_observed'):
                    self.journal.data['goal_observed'] = True
                    self.journal.save()
            else:
                bootstrap = self.journal.data['bootstrap']
                updated_checks = sorted(set(bootstrap['checks']) | checks)
                updated_missions = sorted(set(bootstrap['observed_missions']) | set(self.snapshot.persisted_clears))
                updated_goal = bootstrap.get('goal', False) or goal
                if (updated_checks != bootstrap['checks'] or updated_missions != bootstrap['observed_missions']
                        or updated_goal != bootstrap.get('goal', False)):
                    bootstrap.update(checks=updated_checks, observed_missions=updated_missions, goal=updated_goal)
                    self.journal.save()
        if owned and self.slot_data['options']['goal'] == 4 and inventory(durable)['super_sonic_allowed']:
            if not self.journal.data.get('goal_observed'):
                self.journal.data['goal_observed'] = True
                self.journal.save()
        # An opt-in, signature-verified Movement Gecko profile writes ONLY its
        # transient controller/mask words. It may be tested on a freshly verified
        # living player even while the vanilla new-game save is still being
        # attributed. It never bypasses persistent AP world/save write guards.
        if (owned and self.slot_data['options'].get('movement_unlocks')
                and not self.experimental_direct_hooks):
            try:
                from .movement_gate import configure
                self.movement_status = configure(memory, self.snapshot, owned, transport='gecko')
            except MemoryUnavailable as error:
                self.movement_status = {'status':str(error), 'native_gate_verified':False,
                                        'swim_gate_verified':False, 'breath_gate_verified':False}
        if owned:
            # Native permissions and non-idempotent filler are independent. A
            # blocked query hook must not prevent separately verified stats writes.
            errors = []
            for operation in (lambda: self.project_permissions(memory, owned),
                              lambda: self.apply_effects(memory, item_ids)):
                try:
                    operation()
                except MemoryUnavailable as error:
                    errors.append(str(error))
            if errors:
                self.last_error = self.guard.reason + '; ' + '; '.join(dict.fromkeys(errors))
        elif not history_ready:
            self.last_error = 'Received history incomplete; independently verified reads remain active.'
        can_send = self.guard.can_send(self.snapshot)
        # Never leak a saved journal event to another Dolphin session without
        # fresh native attribution. Bootstrap checks travel before save select.
        checks_out = set(self.journal.data['checks']) if can_send else set()
        return (checks_out, bool(can_send and self.journal.data.get('goal_observed')))

    def select_resource_music(self, path):
        from .music_bank import load_manifest
        try:
            self.resource_music = load_manifest(path, self.slot_data)
        except (ValueError, OSError, KeyError, StopIteration) as error:
            self.resource_music = {'status': f'Music resource rejected: {error}',
                                   'resource_verified': False, 'audible_verified': False}
        self.music_status = self.resource_music
        quiet_logging.record('music', '%s', self.music_status['status'])

    def effective_inventory(self,owned):
        from ..wisps import project_inventory
        return project_inventory(self.test_inventory.apply(owned),self.slot_data['options'])

    def movement_policy(self, owned):
        from ..wisps import project_inventory
        owned=project_inventory(owned,self.slot_data['options'])
        if self.slot_data['options'].get('movement_unlocks'):return owned
        from ..Items import MOVEMENT_ITEMS
        from .test_inventory import MAXIMUM
        counts=owned['counts'].copy()
        for item in MOVEMENT_ITEMS:counts[item]=MAXIMUM.get(item,1)
        return {**owned,'counts':counts}  # Wisp tiers retain genuine ownership

    def refresh_movement_permissions(self,memory,owned):
        """Apply idempotent ability permissions on receipt/override events.

        Uses existing per-operation write guards. No resource scans, filler
        replay or persistent progression writes; unavailable scenes defer.
        """
        if self.snapshot is None:return
        owned=self.movement_policy(owned)
        from .stunts import configure as stunts
        from .player_switch import configure as assist
        from .drill_turbo import configure as drill
        from .hover_ring_dash import configure as hover_dash
        if self.slot_data['options'].get('movement_unlocks'):
            from .movement_gate import configure as movement
            from .water_native import configure as breath
            for attribute,action in (
                ('movement_status',lambda:movement(memory,self.snapshot,owned,transport='direct' if self.experimental_direct_hooks else 'gecko')),
                ('breath_status',lambda:breath(memory,self.snapshot,self.guard,owned,self.journal))):
                try:setattr(self,attribute,action())
                except MemoryUnavailable as error:setattr(self,attribute,{'status':str(error)})
        if not self.slot_data['options'].get('movement_unlocks'):
            from .movement_gate import configure as movement
            try:self.movement_status=movement(memory,self.snapshot,self.movement_policy(owned),transport='direct' if self.experimental_direct_hooks else 'gecko')
            except MemoryUnavailable as error:self.movement_status={'status':str(error)}
        from .quick_step import configure as quick_step
        for name,action in (('quick_step',lambda:quick_step(memory,self.snapshot,owned,self.slot_data['options'].get('movement_unlocks',False))),('stunts',lambda:stunts(memory,self.snapshot,owned,self.slot_data)),
                            ('assist_change',lambda:assist(memory,self.snapshot,owned)),
                            ('drill_turbo',lambda:drill(memory,self.snapshot,owned)),
                            ('hover_ring_dash',lambda:hover_dash(memory,self.snapshot,owned))):
            try:result=action()
            except MemoryUnavailable as error:result={'status':str(error)}
            self.hooks.gameplay_controls_status[name]=result

    def configure_native_hooks(self, memory, owned):
        """Project authenticated ownership into independent native controls.

        Configure White first, including before ReceivedItems completes. A
        missing optional speed/query control cannot strand its capsule data.
        Each writer retains its own executable/profile/scene checks.
        """
        owned=self.movement_policy(owned)
        from .game_land_ui import apply as apply_game_land_ui
        try:
            game_land_display=apply_game_land_ui(memory,self.snapshot,self.guard,owned)
        except MemoryUnavailable as error:
            game_land_display={'status':str(error)}
        from .capsule_refresh import configure as configure_capsules
        from .progression_hook import configure as configure_progression
        from .gameplay_controls import configure as configure_controls
        try:
            capsules = configure_capsules(memory, self.snapshot, owned, self.slot_data)
        except MemoryUnavailable as error:
            capsules = {'available': False, 'reason': str(error)}
        try:
            self.hooks.progression_status = configure_progression(
                memory, self.snapshot, owned, self.slot_data, self.journal)
        except MemoryUnavailable as error:
            self.hooks.progression_status = {'available': False, 'reason': str(error)}
        try:
            controls = configure_controls(memory, self.snapshot, owned, self.slot_data, temporary_boost=self.temporary_boost_allowed(memory))
        except MemoryUnavailable as error:
            controls = {'error': str(error), 'installed': {}}
        self.hooks.gameplay_controls_status = {**controls, 'white_capsules': capsules,'game_land_ui':game_land_display}
        from .emerald_ui import apply as apply_emerald_ui
        try:
            self.hooks.gameplay_controls_status['emerald_ui']=apply_emerald_ui(memory,self.snapshot,self.guard,owned)
        except MemoryUnavailable as error:
            self.hooks.gameplay_controls_status['emerald_ui']={'status':str(error)}
        from .stunts import configure as configure_stunts
        try:
            self.hooks.gameplay_controls_status['stunts']=configure_stunts(memory,self.snapshot,owned,self.slot_data)
        except MemoryUnavailable as error:
            self.hooks.gameplay_controls_status['stunts']={'status':str(error)}
        from .player_switch import configure as configure_assist
        try:
            self.hooks.gameplay_controls_status['assist_change']=configure_assist(memory,self.snapshot,owned)
        except MemoryUnavailable as error:
            self.hooks.gameplay_controls_status['assist_change']={'status':str(error)}
        from .oneup_hook import configure as configure_oneup
        try:
            self.hooks.gameplay_controls_status['one_up_sanity']=configure_oneup(memory,self.snapshot,self.guard,self.slot_data)
        except MemoryUnavailable as error:
            self.hooks.gameplay_controls_status['one_up_sanity']={'status':str(error)}
        from .quick_step import configure as configure_quick
        try:
            self.hooks.gameplay_controls_status['quick_step']=configure_quick(memory,self.snapshot,owned,self.slot_data['options'].get('movement_unlocks',False))
        except MemoryUnavailable as error:
            self.hooks.gameplay_controls_status['quick_step']={'status':str(error)}
        from .drill_turbo import configure as configure_drill
        try:
            self.hooks.gameplay_controls_status['drill_turbo']=configure_drill(memory,self.snapshot,owned)
        except MemoryUnavailable as error:
            self.hooks.gameplay_controls_status['drill_turbo']={'status':str(error)}
        from .hover_ring_dash import configure as configure_hover_dash
        try:
            self.hooks.gameplay_controls_status['hover_ring_dash']=configure_hover_dash(memory,self.snapshot,owned)
        except MemoryUnavailable as error:
            self.hooks.gameplay_controls_status['hover_ring_dash']={'status':str(error)}
        if self.slot_data['options']['movement_unlocks']:
            from .water_native import configure as configure_breath
            try:
                self.breath_status=configure_breath(memory,self.snapshot,self.guard,owned,self.journal)
            except MemoryUnavailable as error:
                self.breath_status={'status':str(error),'write_verified':False}
            from .movement_gate import configure
            try:
                self.movement_status = configure(memory, self.snapshot, owned,
                                                 transport=('direct' if self.experimental_direct_hooks else 'gecko'))
            except MemoryUnavailable as error:
                self.movement_status = {'status': str(error), 'native_gate_verified': False,
                                        'swim_gate_verified': False, 'breath_gate_verified': False}
        else:
            from .movement_gate import configure
            try:self.movement_status=configure(memory,self.snapshot,self.movement_policy(owned),transport='direct' if self.experimental_direct_hooks else 'gecko')
            except MemoryUnavailable as error:self.movement_status={'status':str(error)}

    def project_permissions(self, memory, owned):
        try:
            self.guard.check(self.snapshot)
        except MemoryUnavailable:
            self.guard.check_stats(self.snapshot)
            self.configure_native_hooks(memory, owned)
            self.hooks.project_live_permissions(memory, self.snapshot, owned, self.slot_data)
            return
        on_map=self.snapshot.scene in ('global_map','world_map','game_land_select')
        if not on_map:self.configure_native_hooks(memory, owned)
        from .game_land_notice import prepare as prepare_notice, apply as apply_notice
        prepare_notice(memory,self.snapshot,owned,self.slot_data,self.journal)
        self.hooks.project_permissions(memory, self.snapshot, owned, self.slot_data)
        if on_map:self.configure_native_hooks(memory, owned)
        try:
            self.game_land_notice_status=apply_notice(memory,self.snapshot,self.guard,self.journal)
        except MemoryUnavailable as error:
            self.game_land_notice_status={'status':str(error),'visual_verified':False}

    def boost_grant_context(self, memory):
        context = self.effect_context(memory, 'boost')
        backend = getattr(memory, 'backend', None)
        if not hasattr(backend, 'instance_info'):
            return context  # offline adapters cannot assert a live process
        info = backend.instance_info()
        candidates = info.get('process_candidates', [])
        if len(candidates) != 1:
            raise MemoryUnavailable('WRITE_BLOCKED: temporary Boost process attribution unavailable')
        stage = next(iter(self.snapshot.evidence.get('native_data', {}).get('stage_objects', [])), {})
        # Exclude only host-generated session/epoch UUIDs. Require the same
        # live Dolphin PID, attributed native stage/player/provider and mission.
        return [candidates[0]['pid'], self.snapshot.save_identity,
                stage.get('stage'), stage.get('player_actor_id'), *context[2:]]

    def temporary_boost_allowed(self, memory):
        grant = self.journal.data.get('temporary_boost')
        if not grant or grant.get('consumed'):
            return False
        try:
            context = self.boost_grant_context(memory)
            gauge = memory.read_f32(self.snapshot.boost_address)
        except MemoryUnavailable:
            return False
        if (context != grant['context'] or gauge <= 0 or
                not isinstance(grant.get('ceiling'), (int,float)) or grant['ceiling'] <= 0):
            grant['consumed'] = True
            self.journal.save()
            return False
        return math.isfinite(gauge) and gauge > 0

    def enforce_white_boost_gain_lock(self, memory, owned):
        """Correct native Boost grants that bypass the single boost_add C2 hook.

        Native Boost state and the C2 hook stay authoritative for normal Boost
        consumption. This guarded reconciliation is *only* a backup: with White
        Boost missing, the meter cannot exceed the last AP-receipt-backed
        balance. The balance is monotonically nonincreasing between AP refills.
        Unlike a naive per-frame zeroing hook, a legitimate AP refill remains
        usable and ordinary consumption still works. No persistent save writes.
        """
        if not self.slot_data['options'].get('boost_lock'):
            self.boost_gain_status = {'status': 'off: Boost Lock option disabled'}
            return
        if owned['counts']['White Boost Wisp']:
            self.boost_gain_status = {'status': 'white owned: vanilla Boost gains allowed'}
            return
        try:
            self.guard.check_stats(self.snapshot)
            address = self.snapshot.boost_address
            maximum_addr = self.snapshot.boost_max_address
            if address is None or maximum_addr != address + 12:
                raise MemoryUnavailable('boost provider pointer unavailable')
            if memory.read_u32(address - 8) != 0x80763A18:
                raise MemoryUnavailable('boost provider vtable changed')
            current = memory.read_f32(address)
            maximum = memory.read_f32(maximum_addr)
            if not (math.isfinite(current) and math.isfinite(maximum)
                    and 0. < maximum <= 10000. and 0. <= current <= maximum):
                raise MemoryUnavailable('native Boost meter out of range')
            grant = self.journal.data.get('temporary_boost')
            ceiling = 0.
            receipt = None
            if grant and not grant.get('consumed'):
                # Never inherit an unverified old grant or accept vanilla
                # enemy gains as its new baseline. New grants record ceiling
                # at the instant the AP refill write passes readback.
                if (self.boost_grant_context(memory) == grant.get('context')
                        and type(grant.get('ceiling')) in (int, float)
                        and math.isfinite(grant['ceiling'])
                        and 0. <= grant['ceiling'] <= maximum):
                    ceiling = float(grant['ceiling'])
                    receipt = grant.get('receipt')
                else:
                    grant['consumed'] = True
                    self.journal.save()
            if current > ceiling + 0.0001:
                # Restores only the exact current, attributed native gauge.
                # compare/readback, scene/actor revalidation are performed by
                # SonicMemory's existing boost_stats write policy.
                memory.write_f32(address, ceiling, expected=current,
                                 operation='boost_stats')
                self.boost_gain_status = {
                    'status':'vanilla gain clamped', 'before':current,
                    'after':ceiling, 'ap_refill_receipt':receipt,
                    'native_boost_add_hook_alone_sufficient':False}
                current = ceiling
            else:
                self.boost_gain_status = {'status':'native gauge within AP-authorized ceiling',
                                          'current':current, 'ceiling':ceiling,
                                          'ap_refill_receipt':receipt}
            if grant and receipt is not None:
                # Reduce budget following ordinary Boost use. Persist the
                # downward change, so client restarts cannot reauthorize an
                # already consumed amount via enemy kills.
                new_ceiling = min(ceiling, current)
                if new_ceiling < ceiling:
                    grant['ceiling'] = new_ceiling
                    if new_ceiling <= 0:
                        grant['consumed'] = True
                    self.journal.save()
        except MemoryUnavailable as error:
            self.boost_gain_status = {'status': 'deferred: '+str(error)}

    def effect_context(self, memory, family):
        context = list(self.guard.check_stats(self.snapshot))
        if family == 'boost':
            if self.snapshot.boost_address is None or self.snapshot.boost_max_address is None:
                raise MemoryUnavailable('WRITE_BLOCKED: boost model unavailable')
            context.extend((self.snapshot.boost_address, self.snapshot.boost_max_address,
                            memory.read_u32(self.snapshot.boost_max_address)))
        return context

    @staticmethod
    def delivery_readback_verified(effect):
        addresses=effect.get('addresses',())
        return (bool(addresses) and effect.get('completed_writes')==len(addresses)
                and effect.get('state') in ('verifying','uncertain')
                and effect.get('family') in ('rings','lives','boost'))

    def settle_effects(self, memory):
        for index, pending in list(self.inflight.items()):
            effect = self.journal.data['effects'][str(index)]
            if self.snapshot.scene not in ('gameplay', 'paused'):
                if self.delivery_readback_verified(effect):
                    effect['confirmation_source']='all native writes/readbacks verified before scene exit'
                    self.journal.confirm(index)
                    del self.inflight[index]
                    continue
                effect.update(state='uncertain', reason='left living gameplay before verification completed')
                self.journal.save()
                del self.inflight[index]
                logger.warning('Item uncertain: receipt %s left gameplay; no replay, later receipts continue', index)
                continue
            try:
                context = self.effect_context(memory, pending['family'])
            except MemoryUnavailable:
                continue
            elapsed = self.clock() - pending['started']
            if context != effect['context']:
                if self.delivery_readback_verified(effect):
                    effect['confirmation_source']='all native writes/readbacks verified before actor change'
                    self.journal.confirm(index)
                    del self.inflight[index]
                    continue
                effect.update(state='uncertain', reason='actor/context changed before verification')
                self.journal.save()
                del self.inflight[index]
                logger.warning('Item uncertain: receipt %s actor/context changed; no replay', index)
                continue
            try:
                values = [memory.read_u32(address) for address in pending['addresses']]
            except MemoryUnavailable as error:
                effect.update(state='uncertain', reason=str(error))
                self.journal.save()
                del self.inflight[index]
                logger.warning('Item uncertain: receipt %s verification read failed: %s', index, error)
                continue
            correct = all(value == effect['after'] for value in values)
            if pending['family'] == 'boost':
                decoded = [struct.unpack('>f', v.to_bytes(4, 'big'))[0] for v in values]
                coherent = all(math.isfinite(v) and 0 <= v <= effect['maximum'] for v in decoded)
            else:
                coherent = len(set(values)) == 1 and all(0 <= value <= (99 if pending['family'] == 'lives' else 9999) for value in values)
            effect['last_observed'] = values
            effect['elapsed'] = elapsed
            if elapsed >= .02 and coherent and (correct or self.delivery_readback_verified(effect)):
                pending['later_frame'] = True
            if elapsed >= .5:
                pending['half_second'] = pending.get('half_second', False) or (coherent and pending.get('later_frame'))
            if elapsed >= 2:
                if coherent and pending.get('later_frame') and pending.get('half_second'):
                    self.journal.confirm(index)
                    if effect.get('rolled_amount'):
                        quiet_logging.record('item_effect', 'Rings applied: receipt %s, rolled +%s, counter gain +%s', index,
                                    effect['rolled_amount'], effect['after'] - effect['before'])
                    if pending['family'] == 'boost':
                        before_float, after_float = (struct.unpack('>f', effect[k].to_bytes(4, 'big'))[0]
                                                     for k in ('before','after'))
                        quiet_logging.record('item_effect', '%s applied: receipt %s, %.2f -> %.2f (maximum %.2f)',
                                    BY_ID[effect['item']], index, before_float, after_float, effect['maximum'])
                    quiet_logging.record('item_effect', 'Counter delivery observed: receipt %s, counters %s after %.2fs; HUD verification separate', index, values, elapsed)
                else:
                    effect.update(state='uncertain', reason='no later-frame effect witness or counter sources disagree')
                    self.journal.save()
                    logger.warning('Item uncertain: receipt %s stable counters %s differ; no replay', index, values)
                del self.inflight[index]

    def apply_effects(self, memory, item_ids):
        try:
            from .intro_box import apply as apply_intro_box
            self.intro_box_status = apply_intro_box(memory,self.snapshot,self.guard,self.slot_data)
        except MemoryUnavailable as error:
            self.intro_box_status = {'status':str(error),'applied':False}
        self.settle_effects(memory)
        occupied = {pending['family'] for pending in self.inflight.values()}
        for index, item in enumerate(item_ids):
            name = BY_ID[item]
            if name not in DELIVERY_ITEMS:
                continue
            recorded = self.journal.data['effects'].get(str(index))
            if name=='Dead Weight Trap':
                from .dead_weight import deliver
                try:deliver(self,memory,index,item)
                except MemoryUnavailable as error:self.journal.defer(index,item,str(error))
                continue
            if (recorded and recorded.get('state')=='uncertain' and self.delivery_readback_verified(recorded)
                    and recorded.get('reason') in ('left living gameplay before verification completed',
                        'actor/context changed before verification',
                        'no later-frame effect witness or counter sources disagree')
                    and (recorded.get('reason')!='no later-frame effect witness or counter sources disagree'
                        or recorded.get('last_observed')==[recorded.get('after')]*len(recorded['addresses']))):
                recorded['confirmation_source']='historical complete native write/readback; no replay'
                self.journal.confirm(index,verified_delivery=True)
                continue
            if name=='Score Reset Trap':
                effect=self.journal.data['effects'].get(str(index),{})
                if effect.get('state') in ('confirmed','uncertain','prepared','verifying','skipped_by_operator'):continue
                from .score_reset import deliver
                try:deliver(memory,self.snapshot,self.guard,self.journal,index,item)
                except MemoryUnavailable as error:self.journal.defer(index,item,str(error))
                continue
            family = 'lives' if name == '1-Up' else 'boost' if name in ('Half Boost Refill', 'Full Boost Refill') else 'rings'
            amount = rings_amount(self.journal, index) if name == 'Rings' else None
            recorded = self.journal.data['effects'].get(str(index))
            if recorded and recorded['state'] not in ('queued', 'deferred'):
                # Persisted but unowned verification is uncertain after a restart.
                # Do not block independent receipts and never automatically replay.
                if recorded['state'] in ('prepared', 'verifying', 'uncertain') and index not in self.inflight:
                    if recorded['state'] != 'uncertain':
                        recorded.update(state='uncertain', reason='client restarted after a native attempt')
                        self.journal.save()
                    if index not in self.deferred:
                        self.deferred[index] = 'uncertain'
                        logger.warning('Item uncertain: receipt %s (%s); no replay. Later receipts continue; /sonicitems and /sonicrecover skip %s', index, name, index)
                continue
            if self.clock() < self.retry_after.get(index, 0):
                continue
            snapshot = self.snapshot
            try:
                self.guard.check_stats(snapshot)
                self.hooks.require('stats')
            except MemoryUnavailable as error:
                self.journal.defer(index, item, str(error), snapshot.stage_epoch if snapshot.scene == 'results' else None)
                continue
            if recorded and recorded.get('wait_epoch') is not None and recorded['wait_epoch'] == snapshot.stage_epoch:
                continue
            if family in occupied:
                self.journal.defer(index, item, 'earlier receipt is actively verifying')
                continue
            address = snapshot.lives_address if family == 'lives' else snapshot.boost_address if family == 'boost' else snapshot.rings_address
            mirror = snapshot.world_lives_address if family == 'lives' else None if family == 'boost' else snapshot.ring_mirror_address
            addresses = list(dict.fromkeys(a for a in (address, mirror) if a is not None))
            if not addresses or address is None:
                self.journal.defer(index, item, 'runtime_stats_pointer_missing')
                continue
            try:
                before = memory.read_u32(address)
            except MemoryUnavailable as error:
                self.journal.defer(index, item, str(error))
                continue
            stage=BY_MISSION.get(snapshot.actual_mission,{})
            ring_trap_stage=stage.get('normal',False) or stage.get('zone_index',-1)>=7
            if name == 'Ring Loss Trap' and (before == 0 or not ring_trap_stage):
                if index not in self.deferred:
                    self.deferred[index] = 'trap context'
                    quiet_logging.record('item_effect', 'Item deferred: receipt %s Ring Loss awaits story or Game Land act with positive Rings', index)
                self.journal.defer(index, item, 'story or Game Land act with positive rings required')
                continue  # Keep receipt queued, allow later positive filler.
            limit = 99 if family == 'lives' else 9999
            if family != 'boost' and before > limit:
                self.journal.defer(index, item, 'stats_out_of_range')
                continue
            if family == 'boost':
                try:
                    maximum = memory.read_f32(snapshot.boost_max_address)
                    current = struct.unpack('>f', before.to_bytes(4, 'big'))[0]
                except (MemoryUnavailable, TypeError):
                    self.journal.defer(index, item, 'native boost maximum unavailable')
                    continue
                if not (math.isfinite(current) and math.isfinite(maximum) and 0 < maximum <= 10000 and 0 <= current <= maximum):
                    self.journal.defer(index, item, 'native boost values out of range')
                    continue
                after = int.from_bytes(struct.pack('>f', maximum if name == 'Full Boost Refill' else min(maximum, current + maximum / 2)), 'big')
            else:
                if amount is None:
                    amount = 1 if name == '1-Up' else int(name.split('+')[1].split(')')[0]) if name in LEGACY_FILLER else 0
                after = 0 if name == 'Ring Loss Trap' else min(limit, before + amount)
            self.deferred.pop(index, None)
            context = self.effect_context(memory, family)
            if family == 'boost' and context[-1] != int.from_bytes(struct.pack('>f', maximum), 'big'):
                self.journal.defer(index, item, 'native boost maximum changed before attempt')
                continue
            grant_context = self.boost_grant_context(memory) if family == 'boost' else None
            self.journal.prepare(index, item, context, before, after)
            quiet_logging.record('item_effect', 'Native write attempted: receipt %s, %s, %s -> %s', index, name, before, after)
            self.journal.data['effects'][str(index)].update(addresses=addresses, family=family, stage_epoch=snapshot.stage_epoch, reason=None, completed_writes=0)
            if family == 'boost':
                self.journal.data['effects'][str(index)]['maximum'] = maximum
            self.journal.save()
            completed_writes = 0
            try:
                for target in addresses:
                    if family == 'boost' and self.effect_context(memory, family) != context:
                        raise MemoryUnavailable('WRITE_BLOCKED: boost model or maximum changed before write')
                    current = memory.read_u32(target)
                    if family != 'boost' and current > limit:
                        raise MemoryUnavailable('WRITE_UNCERTAIN: stat mirror out of range')
                    memory.write_u32(target, after, expected=before if target == address else current,
                                     operation='boost_stats' if family == 'boost' else 'stats')
                    completed_writes += 1
                    self.journal.data['effects'][str(index)]['completed_writes']=completed_writes
                    self.journal.save()
            except MemoryUnavailable as error:
                if completed_writes == 0 and str(error).startswith('WRITE_BLOCKED:'):
                    # SonicMemory emits WRITE_BLOCKED only before backend mutation.
                    # This is evidence of no attempt, unlike any WRITE_UNCERTAIN.
                    self.journal.data['effects'][str(index)].update(state='deferred', reason=str(error))
                    self.journal.save()
                    self.retry_after[index] = self.clock() + .25
                    quiet_logging.record('item_effect', 'Item deferred before any native write: receipt %s (%s): %s', index, name, error)
                    continue
                self.journal.data['effects'][str(index)].update(state='uncertain', reason=str(error))
                self.journal.save()
                logger.warning('Item uncertain: receipt %s (%s): %s; later receipts remain eligible', index, name, error)
                continue
            if family == 'boost':
                self.journal.data['temporary_boost'] = {'context': grant_context, 'receipt': index,
                                                        'consumed': False, 'ceiling': struct.unpack('>f', after.to_bytes(4, 'big'))[0]}
            self.journal.data['effects'][str(index)]['state'] = 'verifying'
            self.journal.save()
            self.inflight[index] = {'started': self.clock(), 'addresses': addresses,
                                    'family': family, 'positive': name != 'Ring Loss Trap'}
            occupied.add(family)
            quiet_logging.record('item_effect', 'Immediate readback verified: receipt %s; settlement follows on a later observation', index)

    def pending_effects(self):
        return [i for i, item in enumerate(self.journal.data['receipts'])
                if BY_ID[item] in DELIVERY_ITEMS and self.journal.data['effects'].get(str(i), {}).get('state')
                not in ('confirmed', 'skipped_by_operator')]

    def item_details(self):
        rows = []
        for index, item in enumerate(self.journal.data['receipts']):
            name = BY_ID[item]
            if name in DELIVERY_ITEMS:
                effect = self.journal.data['effects'].get(str(index), {})
                rows.append({**effect, 'index': index, 'name': name,
                             'family': 'score' if name=='Score Reset Trap' else 'lives' if name == '1-Up' else 'boost' if name in ('Half Boost Refill', 'Full Boost Refill') else 'rings',
                             'state': 'applying' if effect.get('state') == 'prepared' else effect.get('state', 'queued'),
                             'journal_state': effect.get('state', 'queued'),
                             'hud_verified': False})
        return rows
