from collections import Counter
import logging
import time
from ..Items import BY_ID, RING_VALUES, EMERALDS, WISP_ITEMS, FILLER, TRAPS
from ..Locations import LOCATION_TABLE, enabled
from ..Options import SonicColoursOptions, OPTION_NAMES
from ..world_constants import GAME, SCHEMA_VERSION, STAGES, STARTING_STAGES, BY_MISSION, game_land_gates
from .memory import MemoryUnavailable

logger = logging.getLogger('Client')


def validate_slot(data):
    if not isinstance(data, dict) or data.get('game') != GAME or data.get('schema_version') != SCHEMA_VERSION:
        raise ValueError('Sonic Colours schema migration required: this client uses schema 3 (always-on Wisp/World Access, coloured Emeralds and five Goals). Regenerate the seed and .apsonic file with the new world; old seed journals cannot be migrated into another seed.')
    if not isinstance(data.get('seed_name'), str) or not data['seed_name']:
        raise ValueError('slot seed identity missing')
    options = data.get('options')
    if not isinstance(options, dict) or set(options) != set(OPTION_NAMES):
        raise ValueError('slot options missing or unexpected')
    resolved = {}
    for name in OPTION_NAMES:
        value = options[name]
        if type(value) is not int:
            raise ValueError(f'slot option {name} must be resolved integer')
        cls = SonicColoursOptions.type_hints[name]
        option = cls.from_any(value)
        if getattr(option, 'options', None) and value not in option.options.values():
            raise ValueError(f'invalid choice {name}')
        if hasattr(option, 'range_start') and not option.range_start <= value <= option.range_end:
            raise ValueError(f'invalid range {name}')
        resolved[name] = option
    if data.get('game_land_gates') != game_land_gates(options['game_land_requirement_reduction']):
        raise ValueError('slot Game Land gates mismatch')
    expected_mapping = {s['stage_slot_id']: s['mission_id'] for s in STAGES}
    if data.get('stage_mapping') != expected_mapping:
        raise ValueError('unsupported native stage permutation')
    from types import SimpleNamespace
    expected_locations = {n: d.code for n, d in LOCATION_TABLE.items() if enabled(d, SimpleNamespace(**resolved))}
    if data.get('locations') != expected_locations:
        raise ValueError('slot locations do not match option-selected stable IDs')
    if options['wisp_capsules'] and not any(LOCATION_TABLE[n].kind == 'capsule' for n in expected_locations):
        raise ValueError('wisp_capsules: no validated accessible capsule instances')
    if data.get('logic_policy') != 'provisional_clears_conservative_pickups':
        raise ValueError('slot logic policy mismatch; regenerate with matching world/client')
    if data.get('mandatory_prologue') != ['stg110', 'stg130']:
        raise ValueError('unsupported native prologue contract')
    start = STARTING_STAGES[options['starting_act']]
    if data.get('starting_slot') != start['stage_slot_id'] or data.get('starting_world') != start['zone_index']:
        raise ValueError('starting slot/world mismatch')
    for name in ('level_randomization', 'death_link', 'swim_trap_weight'):
        if options[name]:
            raise ValueError(f'{name}: requires_verified_hook')
    return data


def inventory(item_ids):
    unknown = set(item_ids) - BY_ID.keys()
    if unknown:
        raise ValueError(f'unknown item IDs: {sorted(unknown)}')
    counts = Counter(BY_ID[item] for item in item_ids)
    return {'counts': counts, 'red_rings': sum(counts[n] * v for n, v in RING_VALUES.items()),
            'emeralds': [n for n in EMERALDS if counts[n]], 'wisps': [n for n in WISP_ITEMS if counts[n]],
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
    return (capsule.eligible and capsule.key in snapshot.opened_capsules
            and capsule.wisp_item in owned_wisps)


def victory(slot_data, snapshot, ever_collected_mask=None, owned=None, observed_clears=frozenset()):
    goal = slot_data['options']['goal']
    clears = snapshot.persisted_clears | observed_clears
    if goal == 0:
        return 'stg790' in clears
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
        self.snapshot = None
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
        self.music_status = {'status':'off' if not self.slot_data['options']['music_randomization'] else 'waiting for attributed stage selection',
                             'audible_verified':False}

    def observe_capsules(self, owned_wisps):
        from ..capsules import CAPSULES
        snapshot = self.snapshot
        if not self.guard.can_record_pickups(snapshot):
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
            if (baseline or previous or not native['opened'] or key in seen or key not in locations
                    or not capsule or capsule.mission != snapshot.actual_mission or not capsule.eligible
                    or capsule.wisp_item not in owned_wisps):
                continue
            checks.add(locations[key])
            events.append({'kind': 'capsule', 'mission': capsule.mission, 'instance_key': key,
                           'stage_epoch': snapshot.stage_epoch, 'actor_id': native['actor_id'],
                           'sequence': len(self.journal.data['pickup_events']) + len(events)})
        if events:
            self.journal.record_pickups(events, {}, checks)
            logger.info('Pickup detected: opened capsules %s; Location queued: %s',
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
        if checks:
            self.journal.record_pickups([{'kind': 'result', 'mission': snapshot.actual_mission,
                'grade': result['grade'], 'stage_epoch': snapshot.stage_epoch,
                'provenance': result['provenance']}], {}, checks)
            logger.info('Result detected: %s grade %s; Location queued: %s',
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
        added = mask & ~previous & ~ever & ~excluded
        if not added:
            return
        updated = ever | added
        events = [{'kind': 'red_ring', 'mission': mission, 'ring': ring,
                   'stage_epoch': epoch, 'playthrough_epoch': self.journal.data.get('bootstrap', {}).get('epoch'),
                   'sequence': len(self.journal.data['pickup_events']) + index}
                  for index, ring in enumerate(ring for ring in range(1, 6) if added & (1 << (ring - 1)))]
        checks = {code for name, code in self.slot_data['locations'].items()
                  if (LOCATION_TABLE[name].mission == mission and
                      (mode == 1 and LOCATION_TABLE[name].kind == 'ring' and
                       added & (1 << (LOCATION_TABLE[name].index - 1)) or
                       mode == 2 and LOCATION_TABLE[name].kind == 'rings' and updated == 31))}
        self.journal.record_pickups(events, {mission: updated}, checks)
        logger.info('Pickup detected: %s rings %s; Location queued: %s',
                    mission, [event['ring'] for event in events], sorted(checks))

    def poll(self, memory, item_ids, history_ready):
        self.snapshot = self.hooks.snapshot(memory)
        self.guard.observe(self.snapshot)
        self.observe_pickups()
        self.observe_results()
        self.settle_effects(memory)
        known = inventory(item_ids) if history_ready else inventory(self.journal.data['receipts'])
        self.observe_capsules(frozenset(known['wisps']))
        # Install native interception even before ReceivedItems finishes. Zero
        # or durable authenticated permissions do not authorize unknown items.
        if not history_ready and self.guard.can_record(self.snapshot):
            try:
                try:
                    self.guard.check(self.snapshot)
                except MemoryUnavailable:
                    self.guard.check_stats(self.snapshot)
                from .progression_hook import configure
                self.hooks.progression_status = configure(memory,self.snapshot,known,self.slot_data,self.journal)
            except MemoryUnavailable as error:
                self.hooks.progression_status = {'available':False,'reason':str(error)}
        self.last_error = self.snapshot.status
        if self.snapshot.scene in ('world_map','global_map','game_land_select'):
            try:
                self.guard.check(self.snapshot)
                from .music import apply_music
                self.music_status = apply_music(memory,self.slot_data)
            except MemoryUnavailable as error:
                self.music_status = {'status':str(error),'audible_verified':False}
        owned = inventory(item_ids) if history_ready else None
        if history_ready:
            self.journal.record_history(item_ids)
        if self.guard.can_record(self.snapshot):
            checks = detect_checks(self.slot_data, self.snapshot,
                                   frozenset(owned['wisps']) if owned else frozenset())
            checks -= {code for name, code in self.slot_data['locations'].items()
                       if LOCATION_TABLE[name].kind in ('ring', 'rings', 'capsule')}
            observed = frozenset(e['mission'] for e in self.journal.data['pickup_events'] if e['kind'] == 'result')
            goal = victory(self.slot_data, self.snapshot, self.journal.data['ever_collected_mask'], owned, observed)
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
        if owned and self.slot_data['options']['goal'] == 4 and owned['super_sonic_allowed']:
            if not self.journal.data.get('goal_observed'):
                self.journal.data['goal_observed'] = True
                self.journal.save()
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
        return (set(self.journal.data['pickup_checks']) | (set(self.journal.data['checks']) if can_send else set()),
                bool((can_send or self.slot_data['options']['goal'] == 4) and self.journal.data.get('goal_observed')))

    def project_permissions(self, memory, owned):
        from .progression_hook import configure
        def configure_hook():
            try:
                self.hooks.progression_status = configure(memory,self.snapshot,owned,self.slot_data,self.journal)
            except MemoryUnavailable as error:
                self.hooks.progression_status = {'available':False,'reason':str(error)}
        try:
            self.guard.check(self.snapshot)
        except MemoryUnavailable:
            self.guard.check_stats(self.snapshot)
            configure_hook()
            self.hooks.project_live_permissions(memory, self.snapshot, owned, self.slot_data)
            return
        configure_hook()
        self.hooks.project_permissions(memory, self.snapshot, owned, self.slot_data)

    def settle_effects(self, memory):
        for index, pending in list(self.inflight.items()):
            effect = self.journal.data['effects'][str(index)]
            if self.snapshot.scene not in ('gameplay', 'paused'):
                effect.update(state='uncertain', reason='left living gameplay before verification completed')
                self.journal.save()
                del self.inflight[index]
                logger.warning('Item uncertain: receipt %s left gameplay; no replay, later receipts continue', index)
                continue
            try:
                context = list(self.guard.check_stats(self.snapshot))
            except MemoryUnavailable:
                continue
            elapsed = self.clock() - pending['started']
            if context != effect['context']:
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
            coherent = len(set(values)) == 1 and all(0 <= value <= (99 if pending['family'] == 'lives' else 9999) for value in values)
            effect['last_observed'] = values
            effect['elapsed'] = elapsed
            if elapsed >= .02 and correct:
                pending['later_frame'] = True
            if .5 <= elapsed < 2:
                pending['half_second'] = pending.get('half_second', False) or (coherent and pending.get('later_frame'))
            if elapsed >= 2:
                if coherent and pending.get('later_frame') and pending.get('half_second'):
                    self.journal.confirm(index)
                    logger.info('Counter delivery observed: receipt %s, counters %s after %.2fs; HUD verification separate', index, values, elapsed)
                else:
                    effect.update(state='uncertain', reason='no later-frame effect witness or counter sources disagree')
                    self.journal.save()
                    logger.warning('Item uncertain: receipt %s stable counters %s differ; no replay', index, values)
                del self.inflight[index]

    def apply_effects(self, memory, item_ids):
        self.settle_effects(memory)
        occupied = {pending['family'] for pending in self.inflight.values()}
        for index, item in enumerate(item_ids):
            name = BY_ID[item]
            if name not in FILLER + TRAPS:
                continue
            recorded = self.journal.data['effects'].get(str(index))
            family = 'lives' if name == '1-Up' else 'rings'
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
            if name == 'Swim Everywhere Trap':
                self.journal.defer(index, item, 'unsupported native swimming operation')
                continue  # Unsupported trap cannot starve independently safe filler.
            address = snapshot.lives_address if family == 'lives' else snapshot.rings_address
            mirror = snapshot.world_lives_address if family == 'lives' else snapshot.ring_mirror_address
            addresses = list(dict.fromkeys(a for a in (address, mirror) if a is not None))
            if not addresses or address is None:
                self.journal.defer(index, item, 'runtime_stats_pointer_missing')
                continue
            try:
                before = memory.read_u32(address)
            except MemoryUnavailable as error:
                self.journal.defer(index, item, str(error))
                continue
            if name == 'Ring Loss Trap' and (before == 0 or not BY_MISSION.get(snapshot.actual_mission, {}).get('normal', False)):
                if index not in self.deferred:
                    self.deferred[index] = 'trap context'
                    logger.info('Item deferred: receipt %s Ring Loss awaits normal act with positive Rings', index)
                self.journal.defer(index, item, 'normal act with positive rings required')
                continue  # Keep receipt queued, allow later positive filler.
            limit = 99 if family == 'lives' else 9999
            if before > limit:
                self.journal.defer(index, item, 'stats_out_of_range')
                continue
            amount = 1 if name == '1-Up' else int(name.split('+')[1].split(')')[0]) if name in FILLER else 0
            after = 0 if name == 'Ring Loss Trap' else min(limit, before + amount)
            self.deferred.pop(index, None)
            self.journal.prepare(index, item, list(self.guard.check_stats(snapshot)), before, after)
            logger.info('Native write attempted: receipt %s, %s, %s -> %s', index, name, before, after)
            self.journal.data['effects'][str(index)].update(addresses=addresses, family=family, stage_epoch=snapshot.stage_epoch, reason=None)
            self.journal.save()
            completed_writes = 0
            try:
                for target in addresses:
                    current = memory.read_u32(target)
                    if current > limit:
                        raise MemoryUnavailable('WRITE_UNCERTAIN: stat mirror out of range')
                    memory.write_u32(target, after, expected=before if target == address else current, operation='stats')
                    completed_writes += 1
            except MemoryUnavailable as error:
                if completed_writes == 0 and str(error).startswith('WRITE_BLOCKED:'):
                    # SonicMemory emits WRITE_BLOCKED only before backend mutation.
                    # This is evidence of no attempt, unlike any WRITE_UNCERTAIN.
                    self.journal.data['effects'][str(index)].update(state='deferred', reason=str(error))
                    self.journal.save()
                    self.retry_after[index] = self.clock() + .25
                    logger.info('Item deferred before any native write: receipt %s (%s): %s', index, name, error)
                    continue
                self.journal.data['effects'][str(index)].update(state='uncertain', reason=str(error))
                self.journal.save()
                logger.warning('Item uncertain: receipt %s (%s): %s; later receipts remain eligible', index, name, error)
                continue
            self.journal.data['effects'][str(index)]['state'] = 'verifying'
            self.journal.save()
            self.inflight[index] = {'started': self.clock(), 'addresses': addresses,
                                    'family': family, 'positive': name != 'Ring Loss Trap'}
            occupied.add(family)
            logger.info('Immediate readback verified: receipt %s; queued for 0.5s/2s settlement', index)

    def pending_effects(self):
        return [i for i, item in enumerate(self.journal.data['receipts'])
                if BY_ID[item] in FILLER + TRAPS and self.journal.data['effects'].get(str(i), {}).get('state')
                not in ('confirmed', 'skipped_by_operator')]

    def item_details(self):
        rows = []
        for index, item in enumerate(self.journal.data['receipts']):
            name = BY_ID[item]
            if name in FILLER + TRAPS:
                effect = self.journal.data['effects'].get(str(index), {})
                rows.append({**effect, 'index': index, 'name': name,
                             'family': 'lives' if name == '1-Up' else 'rings',
                             'state': 'applying' if effect.get('state') == 'prepared' else effect.get('state', 'queued'),
                             'journal_state': effect.get('state', 'queued'),
                             'hud_verified': False})
        return rows
