"""Read the pinned immediate-mode pause list; never attach a debugger or write game memory."""
import json
from pathlib import Path
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bridge'))
from live_monitor import Session


def snapshot():
    session = Session()
    try:
        read = lambda rva, size: session.read(session.base + rva, size)
        records = []
        for index in range(5, 11):
            data = read(0x115d7c0 + index * 0x30, 0x30)
            records.append(dict(index=index, id=struct.unpack_from('<i', data)[0],
                init=hex(struct.unpack_from('<Q', data, 8)[0]),
                draw=hex(struct.unpack_from('<Q', data, 16)[0]),
                input=hex(struct.unpack_from('<Q', data, 24)[0])))
        contexts = []
        for index in range(10):
            data = read(0x1c4c9f0 + index * 0xf0, 0xf0)
            contexts.append(dict(index=index, record=struct.unpack_from('<h', data, 0x14)[0],
                selected=struct.unpack_from('<h', data, 0xa)[0],
                first=struct.unpack_from('<h', data, 0xe)[0],
                last=struct.unpack_from('<h', data, 0x12)[0],
                rows=struct.unpack_from('<i', data, 0x98)[0],
                selected_input=struct.unpack_from('<i', data, 0x40)[0],
                confirm=struct.unpack_from('<i', data, 0x70)[0],
                back=struct.unpack_from('<i', data, 0x74)[0]))
        return dict(pid=session.pid, base=hex(session.base),
            stack_index=struct.unpack('<i', read(0x115efc4, 4))[0],
            record_count=struct.unpack('<i', read(0x115efe0, 4))[0],
            profile=hex(struct.unpack('<Q', read(0x1c7f160, 8))[0]),
            detective_prefix=read(0x649a0, 15).hex(),
            default_font=struct.unpack('<f', read(0x115d7b8, 4))[0],
            default_spacing=struct.unpack('<f', read(0x115d7bc, 4))[0],
            records=records, contexts=contexts, writes_enabled=False)
    finally:
        session.close()


if __name__ == '__main__':
    report = snapshot()
    output = Path('build/lego_city_undercover/debugger/pause_list_snapshot.json')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))
