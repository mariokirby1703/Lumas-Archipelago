"""Locate x64 RIP-relative references to exact local executable strings, without executing them."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import struct

from capstone import Cs, CS_ARCH_X86, CS_MODE_64
from inspect_game import inspect_pe


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("names", nargs="+")
    args = parser.parse_args()
    world = Path(__file__).resolve().parents[1]
    data = (world / "notes/gamefiles/LEGOLCUR_DX11.exe").read_bytes()
    pe = inspect_pe(data)
    base = int(pe["image_base"], 16)
    text = next(s for s in pe["sections"] if s["name"] == ".text")
    targets = {}
    for match in re.finditer(rb"[\x20-\x7e]{2,}", data):
        name = match.group().decode("ascii")
        if name in args.names:
            section = next(s for s in pe["sections"]
                           if s["raw_offset"] <= match.start() < s["raw_offset"] + s["raw_size"])
            targets[base + section["rva"] + match.start() - section["raw_offset"]] = name
    raw = data[text["raw_offset"]:text["raw_offset"] + text["raw_size"]]
    decoder = Cs(CS_ARCH_X86, CS_MODE_64)
    rows = []
    for offset in range(len(raw) - 7):
        if raw[offset] not in (0x48, 0x4C) or raw[offset + 1] not in (0x8B, 0x8D) or raw[offset + 2] & 0xC7 != 5:
            continue
        va = base + text["rva"] + offset
        target = va + 7 + struct.unpack_from("<i", raw, offset + 3)[0]
        if target in targets:
            rows.append(dict(name=targets[target], rva=hex(va-base),
                             instructions=[f"{i.address-base:x}: {i.mnemonic} {i.op_str}"
                                           for i in decoder.disasm(raw[offset:offset + 128], va)]))
    output = world / "notes/analysis/string_xrefs_latest.json"
    output.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(json.dumps(rows, indent=2))


if __name__ == "__main__":
    main()
