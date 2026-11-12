"""Disassemble a bounded RVA range of the local research executable; never execute it."""
from __future__ import annotations

import argparse
from pathlib import Path
import struct

from capstone import Cs, CS_ARCH_X86, CS_MODE_64
from inspect_game import inspect_pe


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rva", type=lambda value: int(value, 0))
    parser.add_argument("--size", type=int, default=256)
    args = parser.parse_args()
    world = Path(__file__).resolve().parents[1]
    data = (world / "notes/gamefiles/LEGOLCUR_DX11.exe").read_bytes()
    pe = inspect_pe(data)
    size = args.size
    pdata = next(s for s in pe["sections"] if s["name"] == ".pdata")
    for offset in range(pdata["raw_offset"], pdata["raw_offset"] + pdata["virtual_size"], 12):
        start, end, unwind = struct.unpack_from("<III", data, offset)
        if start == args.rva:
            size = max(size, min(end - start, 16384))
            break
    section = next(s for s in pe["sections"] if s["rva"] <= args.rva < s["rva"] + s["raw_size"])
    offset = section["raw_offset"] + args.rva - section["rva"]
    base = int(pe["image_base"], 16)
    decoder = Cs(CS_ARCH_X86, CS_MODE_64)
    lines = [f"{i.address-base:x}: {i.mnemonic} {i.op_str}"
             for i in decoder.disasm(data[offset:offset + size], base + args.rva)]
    output = world / "notes/analysis/disassembly"
    output.mkdir(exist_ok=True)
    (output / f"{args.rva:x}.txt").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
