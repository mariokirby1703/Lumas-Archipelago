"""Find action-name getter references in the supplied x64 image; never call them.

Requires capstone (available in the repository virtual environment).
Pointer-table associations are candidates, not verified calling interfaces.
"""
from __future__ import annotations

import json
import struct
from pathlib import Path

from capstone import Cs, CS_ARCH_X86, CS_MODE_64

from inspect_game import inspect_pe

NAMES = {"UnlockAbility", "LockAbility", "IsAbilityUnlocked", "CityObjective_IsComplete", "CityObjective_SetComplete",
         "PlayerGiveStuds", "UI_SetMissionMessage", "CommitCollectables", "Job_GetValue", "Job_SetValue",
         "GetPlayerBricks", "GetClassUnlocked", "CharacterAvailable", "UnlockCharacterDebug", "AwardCharacter",
         "GetGoldBricksCollected", "GetGoldBrickTotal", "UI_SetStatsStuds", "Character_GetModelName",
         "Character_GetClass", "Character_GetItemOut", "Character_InContext", "InContext"}


def main() -> None:
    world = Path(__file__).resolve().parents[1]
    output = world / "notes/analysis"
    data = (world / "notes/gamefiles/LEGOLCUR_DX11.exe").read_bytes()
    pe = inspect_pe(data)
    base = int(pe["image_base"], 16)
    text = next(section for section in pe["sections"] if section["name"] == ".text")

    def file_va(offset: int) -> int:
        section = next(section for section in pe["sections"]
                       if section["raw_offset"] <= offset < section["raw_offset"] + section["raw_size"])
        return base + section["rva"] + offset - section["raw_offset"]

    strings = json.loads((output / "LEGOLCUR_DX11.exe.strings.json").read_text())
    targets = {file_va(row["offset"]): row["text"] for row in strings if row["text"] in NAMES}
    raw = data[text["raw_offset"]:text["raw_offset"] + text["raw_size"]]
    decoder = Cs(CS_ARCH_X86, CS_MODE_64)
    rows = []
    for offset in range(len(raw) - 8):
        # REX.W LEA reg,[RIP+disp32], followed by RET. Check exact semantics by disassembly below.
        if raw[offset] not in (0x48, 0x4C) or raw[offset + 1] != 0x8D or raw[offset + 2] & 0xC7 != 5:
            continue
        va = base + text["rva"] + offset
        target = va + 7 + struct.unpack_from("<i", raw, offset + 3)[0]
        if target not in targets or raw[offset + 7] != 0xC3:
            continue
        row = dict(name=targets[target], getter_rva=hex(va - base),
                   instructions=[f"{i.address - base:x}: {i.mnemonic} {i.op_str}"
                                 for i in decoder.disasm(raw[offset:offset + 8], va)],
                   pointer_tables=[])
        needle = struct.pack("<Q", va)
        start = 0
        while (hit := data.find(needle, start)) >= 0:
            start = hit + 1
            if hit + 32 > len(data):
                continue
            pointers = struct.unpack_from("<QQQQ", data, hit)
            candidate = pointers[3]
            if base + text["rva"] <= candidate < base + text["rva"] + text["virtual_size"]:
                candidate_offset = candidate - base - text["rva"] + text["raw_offset"]
                row["pointer_tables"].append(dict(table_file_offset=hex(hit),
                    candidate_method_rva=hex(candidate - base),
                    disassembly=[f"{i.address - base:x}: {i.mnemonic} {i.op_str}"
                                 for i in decoder.disasm(data[candidate_offset:candidate_offset + 192], candidate)]))
        rows.append(row)
    (output / "action_xrefs.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(json.dumps([dict(name=row["name"], getter_rva=row["getter_rva"],
                           candidate_method_rvas=[p["candidate_method_rva"] for p in row["pointer_tables"]])
                      for row in rows], indent=2))


if __name__ == "__main__":
    main()
