from collections import Counter
from ..Items import BY_ID, RING_VALUES, EMERALDS, WISP_ITEMS, FILLER, TRAPS
from ..Locations import LOCATION_TABLE, enabled
from ..Options import SonicColoursOptions, OPTION_NAMES
from ..world_constants import GAME, SCHEMA_VERSION, STAGES, NORMAL, BY_MISSION, game_land_gates
from .memory import MemoryUnavailable


def validate_slot(data):
    if not isinstance(data, dict) or data.get('game') != GAME or data.get('schema_version') != SCHEMA_VERSION:
        raise ValueError('Unsupported Sonic Colours slot schema/game: v2 uses Sonic Colours (Wii); regenerate old .apsonic files.')
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
    if options['wisp_capsule_sanity'] and not any(LOCATION_TABLE[n].kind == 'capsule' for n in expected_locations):
        raise ValueError('wisp_capsule_sanity: no validated accessible capsule instances')
    if data.get('logic_policy') != 'provisional_clears_conservative_pickups':
        raise ValueError('slot logic policy mismatch; regenerate with matching world/client')
    if data.get('mandatory_prologue') != ['stg110', 'stg130']:
        raise ValueError('unsupported native prologue contract')
    if data.get('research_only') is not True:
        raise ValueError('only research-only slot files supported by this client build')
    start = NORMAL[options['starting_act']]
    if data.get('starting_slot') != start['stage_slot_id'] or data.get('starting_world') != start['zone_index']:
        raise ValueError('starting slot/world mismatch')
    if options['goal'] == 2 and not options['red_ring_checks']:
        raise ValueError('all_red_rings requires enabled Red Ring checks')
    if options['goal'] == 3 and not options['game_land_checks']:
        raise ValueError('all_game_land requires enabled Game Land checks')
    for name in ('level_randomization', 'music_randomization', 'rank_checks', 'death_link',
                 'swim_trap_weight', 'wisp_discovery_checks'):
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
        rings = snapshot.persisted_rings.get(data.mission, frozenset())
        if (data.kind == 'clear' and data.mission in snapshot.persisted_clears
                or data.kind == 'ring' and data.index in rings
                or data.kind == 'rings' and frozenset(range(1, 6)) <= rings
                or data.kind == 'rank' and data.mission in snapshot.awarded_ranks
                   and 0 <= snapshot.awarded_ranks[data.mission] <= data.index
                or data.kind == 'emerald' and data.index in snapshot.emerald_rewards
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
            and (not slot_data['options']['wisp_unlocks'] or capsule.wisp_item in owned_wisps))


def victory(slot_data, snapshot):
    goal = slot_data['options']['goal']
    if goal == 0:
        return 'stg790' in snapshot.persisted_clears
    if goal == 1:
        return all(s['mission_id'] in snapshot.persisted_clears for s in STAGES if s['zone_index'] < 7)
    if goal == 2:
        return all(frozenset(range(1, 6)) <= snapshot.persisted_rings.get(s['mission_id'], frozenset())
                   for s in STAGES if s['normal'])
    if goal == 3:
        return all(s['mission_id'] in snapshot.persisted_clears for s in STAGES if s['zone_index'] >= 7)
    raise ValueError('unsupported goal')


class Runtime:
    def __init__(self, slot_data, journal, guard, hooks):
        self.slot_data = validate_slot(slot_data)
        self.journal, self.guard, self.hooks = journal, guard, hooks
        self.snapshot = None
        self.last_error = None

    def poll(self, memory, item_ids, history_ready):
        self.snapshot = self.hooks.snapshot(memory)
        self.guard.observe(self.snapshot)
        self.last_error = self.snapshot.status
        owned = inventory(item_ids) if history_ready else None
        if history_ready:
            self.journal.record_history(item_ids)
        if self.guard.can_record(self.snapshot):
            checks = detect_checks(self.slot_data, self.snapshot,
                                   frozenset(owned['wisps']) if owned else frozenset())
            goal = victory(self.slot_data, self.snapshot)
            if self.guard.can_send(self.snapshot):
                self.journal.add_checks(checks)
                if goal and not self.journal.data.get('goal_observed'):
                    self.journal.data['goal_observed'] = True
                    self.journal.save()
            else:
                bootstrap = self.journal.data['bootstrap']
                bootstrap['checks'] = sorted(set(bootstrap['checks']) | checks)
                bootstrap['observed_missions'] = sorted(set(bootstrap['observed_missions']) |
                                                        set(self.snapshot.persisted_clears))
                bootstrap['goal'] = bootstrap.get('goal', False) or goal
                self.journal.save()
        if owned:
            # Native permissions and non-idempotent filler are independent. A
            # blocked query hook must not prevent separately verified stats writes.
            errors = []
            for operation in (lambda: self.hooks.project_permissions(memory, self.snapshot, owned, self.slot_data),
                              lambda: self.apply_effects(memory, item_ids)):
                try:
                    self.guard.check(self.snapshot)
                    operation()
                except MemoryUnavailable as error:
                    errors.append(str(error))
            if errors:
                self.last_error = self.guard.reason + '; ' + '; '.join(dict.fromkeys(errors))
        elif not history_ready:
            self.last_error = 'Received history incomplete; independently verified reads remain active.'
        can_send = self.guard.can_send(self.snapshot)
        return (set(self.journal.data['checks']) if can_send else set(),
                bool(can_send and self.journal.data.get('goal_observed')))

    def apply_effects(self, memory, item_ids):
        for index, item in enumerate(item_ids):
            name = BY_ID[item]
            if name not in FILLER + TRAPS:
                continue
            recorded = self.journal.data['effects'].get(str(index))
            if recorded:
                if recorded['state'] == 'prepared':
                    raise MemoryUnavailable(f'WRITE_UNCERTAIN: receipt {index}; /sonicrecover skip {index}')
                continue
            snapshot = self.snapshot
            self.guard.check(snapshot)
            self.hooks.require('stats')
            if snapshot.scene != 'gameplay' or snapshot.death_state != 'alive':
                raise MemoryUnavailable('WRITE_BLOCKED: effect awaits stable living gameplay')
            if name == 'Swim Everywhere Trap':
                self.hooks.require('swimming')
                raise MemoryUnavailable('WRITE_BLOCKED: swimming lifecycle not live validated')
            address = snapshot.lives_address if name == '1-Up' else snapshot.rings_address
            if address is None or address % 4:
                raise MemoryUnavailable('WRITE_BLOCKED: runtime_stats_pointer_missing')
            before = memory.read_u32(address)
            if name == 'Ring Loss Trap' and (before == 0 or not BY_MISSION.get(
                    snapshot.actual_mission, {}).get('normal', False)):
                raise MemoryUnavailable('WRITE_BLOCKED: ring trap awaits normal act with positive Rings')
            limit = 99 if name == '1-Up' else 999
            if before > limit:
                raise MemoryUnavailable('WRITE_BLOCKED: stats_out_of_range')
            amount = 1 if name == '1-Up' else int(name.split('+')[1].split(')')[0]) if name in FILLER else 0
            after = 0 if name == 'Ring Loss Trap' else min(limit, before + amount)
            self.journal.prepare(index, item, list(self.guard.check(snapshot)), before, after)
            memory.write_u32(address, after, expected=before, operation='stats')
            self.journal.confirm(index)

    def pending_effects(self):
        return [i for i, item in enumerate(self.journal.data['receipts'])
                if BY_ID[item] in FILLER + TRAPS and self.journal.data['effects'].get(str(i), {}).get('state')
                not in ('confirmed', 'skipped_by_operator')]
