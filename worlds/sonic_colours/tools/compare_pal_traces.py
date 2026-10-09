"""Compare bounded PAL captures; differences alone never grant capabilities."""
import argparse
import json
from pathlib import Path


def compare(before, after):
    if before.get('revision_sha') != after.get('revision_sha') or not before.get('revision_sha'):
        raise ValueError('trace revision mismatch or absent revision')
    def bank(report):
        trace = report['snapshot']['evidence']['save_chain_trace']
        if trace['status'] != 'candidate_only':
            raise ValueError('trace has no stable candidate bank')
        return bytes.fromhex(next(s['hex'] for s in trace['steps'] if s['step'] == 'c_bank'))
    old, new = bank(before), bank(after)
    if len(old) != 40 or len(new) != 40:
        raise ValueError('unexpected flag bank length')
    changes = []
    for offset in range(0, 40, 4):
        a, b = int.from_bytes(old[offset:offset+4], 'big'), int.from_bytes(new[offset:offset+4], 'big')
        for bit in range(32):
            if (a ^ b) & (1 << bit):
                changes.append({'bit': offset * 8 + bit, 'before': bool(a & (1 << bit)),
                                'after': bool(b & (1 << bit))})
    return {'before_operator_phase': before.get('operator_phase'),
            'after_operator_phase': after.get('operator_phase'), 'changed_bits': changes,
            'warning': 'Phase labels are operator reports. No native scene, mission, identity, AP acknowledgement or write proof follows from a bank diff.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('before', type=Path)
    parser.add_argument('after', type=Path)
    args = parser.parse_args()
    print(json.dumps(compare(json.loads(args.before.read_text()), json.loads(args.after.read_text())), indent=2))
