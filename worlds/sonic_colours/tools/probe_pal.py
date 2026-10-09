"""Read-only PAL probe; never arms a save or sends AP checks. No RAM dumps."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys
import time
from datetime import datetime, timezone


class RecordingBackend:
    """Record only small data reads, never executable sections or RAM pools."""
    def __init__(self, backend):
        self.backend = backend
        self.reads = []

    def read_bytes(self, address, size):
        data = self.backend.read_bytes(address, size)
        if size <= 64 and address >= 0x80800000:
            self.reads.append({'address': address, 'size': size, 'hex': data.hex()})
        return data

    def write_bytes(self, address, data):
        raise RuntimeError('read-only probe')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, help='Optional small JSON report')
    parser.add_argument('--phase', default='unspecified', help='Operator scene label; never native scene proof')
    parser.add_argument('--samples', type=int, default=3)
    parser.add_argument('--interval', type=float, default=0.1)
    parser.add_argument('--pool', action='store_true', help='Also read 28 header bytes and 40 flag bytes for each of the three code-derived saves')
    args = parser.parse_args()
    if not 1 <= args.samples <= 600 or not 0.1 <= args.interval <= 10:
        parser.error('samples must be 1..600; interval must be 0.1..10 seconds')
    # Restrict unrelated world loading through the repository's existing filter.
    import os
    import unittest  # noqa: F401 - activates AP_TEST_WORLDS filter in this fork
    os.environ['AP_TEST_WORLDS'] = 'sonic_colours'
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    import dolphin_memory_engine as dolphin
    from worlds.sonic_colours.client.memory import DMEBackend, SonicMemory, MemoryUnavailable
    from worlds.sonic_colours.client.hooks import NativeHooks
    report = {'read_only': True, 'live_writes': 0, 'live_checks_sent': 0,
              'operator_phase': args.phase, 'phase_is_native_proof': False, 'samples': []}
    backend = DMEBackend(dolphin)
    try:
        dolphin.hook()
        report['dme_status'] = getattr(dolphin.get_status(), 'name', str(dolphin.get_status()))
        recording = RecordingBackend(backend)
        memory = SonicMemory(recording)
        report['revision_sha'] = memory.verify_revision()
        hooks = NativeHooks()
        for index in range(args.samples):
            recording.reads = []
            state = hooks.snapshot(memory)
            sample = {'timestamp_utc': datetime.now(timezone.utc).isoformat(),
                      'snapshot': asdict(state), 'reads': recording.reads}
            if args.pool and hooks.chain:
                container = hooks.chain[1]
                pool = []
                for slot_index in range(3):
                    selected = container + 8 + slot_index * 0x19608
                    pool.append({'internal_index': slot_index, 'address': f'0x{selected:08X}',
                                 'header_hex': memory.read_bytes(selected, 28).hex(),
                                 'flag_words_hex': memory.read_bytes(selected + 0x2c, 40).hex(),
                                 'grade': 'candidate-only; header semantics unresolved'})
                if memory.resolve_flags_ptr() != hooks.chain:
                    raise MemoryUnavailable('pool_context_changed')
                sample['save_pool_candidates'] = pool
            report['samples'].append(sample)
            if args.output:
                args.output.write_text(json.dumps(report, indent=2, default=lambda v: sorted(v) if isinstance(v, frozenset) else str(v)) + '\n', encoding='utf-8')
            if index + 1 < args.samples:
                time.sleep(args.interval)
        report['snapshot'] = asdict(state)
    except (MemoryUnavailable, RuntimeError, OSError) as error:
        report['error'] = str(error)
    finally:
        backend.close()
        if dolphin.is_hooked():
            dolphin.un_hook()
    content = json.dumps(report, indent=2, default=lambda value: sorted(value) if isinstance(value, frozenset) else str(value))
    if args.output:
        print(json.dumps({'output': str(args.output), 'dme_status': report.get('dme_status'),
                          'samples': len(report['samples']), 'error': report.get('error'),
                          'candidate_clears': sorted(state.candidate_clears) if 'snapshot' in report else [],
                          'native_status': state.status if 'snapshot' in report else None}, indent=2))
    else:
        print(content)
    if args.output:
        args.output.write_text(content + '\n', encoding='utf-8')
    return 0 if 'snapshot' in report else 1


if __name__ == '__main__':
    raise SystemExit(main())
