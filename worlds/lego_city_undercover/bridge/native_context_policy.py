"""Pinned native command eligibility; vehicle grants never revoke actors."""
NATIVE_OPCODES=frozenset((*range(1,11),12,13))
PASSIVE_CONTEXTS=frozenset((27,46,157)) # DropPoint, Default, RideObject
PASSIVE_OPCODES=frozenset((1,2,3,6,7,10))
READ_OR_SAVE_OPCODES=frozenset((4,5,9))

def allows_native_command(context,opcode,alive=True):
    return bool(alive and opcode in NATIVE_OPCODES and (opcode in READ_OR_SAVE_OPCODES or context==46 or
                          (context in PASSIVE_CONTEXTS and opcode in PASSIVE_OPCODES)))

def header():
    contexts=' || '.join(f'context=={n}' for n in sorted(PASSIVE_CONTEXTS-{46}))
    opcodes=' || '.join(f'opcode=={n}' for n in sorted(PASSIVE_OPCODES))
    exempt=' || '.join(f'opcode=={n}' for n in sorted(READ_OR_SAVE_OPCODES))
    known=' || '.join(f'opcode=={n}' for n in sorted(NATIVE_OPCODES))
    return ('// Generated from native_context_policy.py.\n'
            f'static bool IsKnownNativeOpcode(unsigned opcode) {{ return {known}; }}\n'
            'static bool AllowsNativeCommand(int context,unsigned opcode,bool alive) {\n'
            f'    return alive && IsKnownNativeOpcode(opcode) && (({exempt}) || context==46 ||\n'
            f'        (({contexts}) && ({opcodes})));\n'+'}\n')
