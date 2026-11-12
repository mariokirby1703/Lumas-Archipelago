"""Bounded read-only player context sampling for manual death/respawn experiments."""
import ctypes
import argparse
import json
from pathlib import Path
import sys
import time

WORLD = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD / "bridge"))
import diagnose
from actor_reader import read_context, PLAYER_RVA
from inventory_reader import pointer


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=float, default=180)
    args = parser.parse_args()
    if not 0 < args.seconds <= 180:
        raise ValueError("Watch duration must be between 0 and 180 seconds")
    process = next(p for p in diagnose.diagnose()["processes"] if p["status"] == "module_header_read")
    if process["sha256"] != diagnose.RESEARCH_HASH:
        raise ValueError("Unsupported executable")
    kernel = diagnose.bind_kernel()
    handle = kernel.OpenProcess(0x1010, False, process["pid"])
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    target = WORLD / "notes/analysis" / f"death_context_watch_{time.time_ns()}.jsonl"
    try:
        read = lambda address, size: diagnose.read_memory(kernel, handle, address, size)
        base = int(process["module_base"], 16)
        start = time.monotonic()
        previous = None
        print(f"Read-only context watch started: {target.name}", flush=True)
        with target.open("x", encoding="utf-8") as stream:
            while time.monotonic() - start < args.seconds:
                try:
                    actor = pointer(read, base + PLAYER_RVA)
                    state = dict(actor=hex(actor), context=read_context(read, base, actor)) if actor else dict(actor=None)
                    if actor:
                        health = read(actor + 0x942, 2)
                        if len(health) != 2:
                            raise ValueError("Incomplete health bytes")
                        state["health_limit_byte"] = health[0]
                        state["health_current_byte"] = health[1]
                except (OSError, ValueError, RuntimeError) as error:
                    state = dict(error=str(error))
                if state != previous:
                    row = dict(seconds=round(time.monotonic()-start, 3), **state)
                    line = json.dumps(row)
                    stream.write(line + "\n")
                    stream.flush()
                    print(line, flush=True)
                    previous = state
                time.sleep(0.1)
    finally:
        kernel.CloseHandle(handle)


if __name__ == "__main__":
    main()
