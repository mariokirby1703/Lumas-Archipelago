"""Read-only PAL probe; never arms a save or sends AP checks. No RAM dumps."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, help='Optional small JSON report')
    args = parser.parse_args()
    # Restrict unrelated world loading through the repository's existing filter.
    import os
    import unittest  # noqa: F401 - activates AP_TEST_WORLDS filter in this fork
    os.environ['AP_TEST_WORLDS'] = 'sonic_colours'
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    import dolphin_memory_engine as dolphin
    from worlds.sonic_colours.client.memory import DMEBackend, SonicMemory, MemoryUnavailable
    from worlds.sonic_colours.client.hooks import NativeHooks
    report = {'read_only': True, 'live_writes': 0, 'live_checks_sent': 0}
    backend = DMEBackend(dolphin)
    try:
        dolphin.hook()
        report['dme_status'] = getattr(dolphin.get_status(), 'name', str(dolphin.get_status()))
        memory = SonicMemory(backend)
        report['revision_sha'] = memory.verify_revision()
        hooks = NativeHooks()
        for _ in range(3):
            state = hooks.snapshot(memory)
            time.sleep(0.1)
        report['snapshot'] = asdict(state)
    except (MemoryUnavailable, RuntimeError, OSError) as error:
        report['error'] = str(error)
    finally:
        backend.close()
        if dolphin.is_hooked():
            dolphin.un_hook()
    content = json.dumps(report, indent=2, default=lambda value: sorted(value) if isinstance(value, frozenset) else str(value))
    print(content)
    if args.output:
        args.output.write_text(content + '\n', encoding='utf-8')
    return 0 if 'snapshot' in report else 1


if __name__ == '__main__':
    raise SystemExit(main())
