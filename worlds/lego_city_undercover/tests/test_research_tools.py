"""Synthetic parser tests; no gameplay verification is implied."""
import importlib.util
import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "tools"


def load(name):
    spec = importlib.util.spec_from_file_location(name, TOOLS / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


archive = load("archive_index")
inspect = load("inspect_game")
mapping = load("map_candidates")
jobs = load("job_data")
scripts = load("script_catalogue")
resources = load("resource_catalogue")
builder = load("build_diagnostics")
collection = load("collection_data")
backups = load("backup_slot")
BRIDGE = TOOLS.parent / "bridge"
sys.path.insert(0, str(BRIDGE))
from research_profile import ABILITY_NAMES, symbol_hash, validate_table, decode_ability_query
from objective_reader import parse_records, parse_record_groups, decode_bits, read_objectives
from inventory_reader import (parse_stats, parse_character_control, cstring, read_stats, read_characters,
                              STATS_RVA, PROFILE_RVA, MODELS_RVA, CONTROLLER_RVA, CHARACTER_STATE_RVA)
from actor_reader import read_actor, read_context, parse_item_node, PLAYER_RVA, CONTEXT_MANAGER_RVA
from story_reader import parse_job_registry, decode_job_value, read_story, JOB_MANAGER_RVA


class MockMemory:
    def __init__(self, regions):
        self.regions = regions

    def read(self, address, size):
        for start, data in self.regions.items():
            if start <= address and address + size <= start + len(data):
                return bytes(data[address - start:address - start + size])
        raise ValueError(f"Mock read outside fixture: {address:#x}+{size}")


class ResearchToolsTests(unittest.TestCase):
    def test_save_backup_preserves_sources_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            source, target = Path(folder) / "slot1", Path(folder) / "backup"
            source.mkdir()
            path = source / "game1.save"
            path.write_bytes(b"synthetic save")
            manifest = backups.backup_slot(source, target)
            self.assertEqual(path.read_bytes(), b"synthetic save")
            self.assertEqual((target / "game1.save").read_bytes(), path.read_bytes())
            self.assertTrue(manifest["stable_double_read"])
            self.assertFalse(manifest["format_validated"])
            with self.assertRaises(ValueError):
                backups.backup_slot(source, target)

    def test_save_backup_rejects_changes_between_reads(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as folder:
            source, target = Path(folder) / "slot1", Path(folder) / "backup"
            source.mkdir()
            (source / "game1.save").write_bytes(b"first")
            with patch.object(Path, "read_bytes", side_effect=[b"first", b"other"]):
                with self.assertRaises(RuntimeError):
                    backups.backup_slot(source, target)
            self.assertFalse(target.exists())

    def test_job_registry_and_concrete_types(self):
        record = struct.pack("<I4xQH6x", 123, 0x20000, 2)
        self.assertEqual(parse_job_registry(record), {123: (0x20000, 2)})
        with self.assertRaises(ValueError):
            parse_job_registry(record + record)
        base = 0x140000000
        value = struct.pack("<QI Ii", base + 0xC46B38, 0, 123, -10)
        self.assertEqual(decode_job_value(value, base, 123, "Int"), -10)
        with self.assertRaises(ValueError):
            decode_job_value(value, base, 123, "Bool")
        with self.assertRaises(ValueError):
            decode_job_value(value, base, 124, "Int")
        boolean = struct.pack("<QII4s", base + 0xC46BB8, 0, 123, b"\x02\0\0\0")
        with self.assertRaises(ValueError):
            decode_job_value(boolean, base, 123, "Bool")

    def test_mock_named_story_value(self):
        base, manager, table, fields, obj = 0x140000000, 0x20000, 0x30000, 0x40000, 0x50000
        regions = {base + JOB_MANAGER_RVA: struct.pack("<Q", manager),
                   manager + 0xE0: struct.pack("<QII", table, 1, 1),
                   table: struct.pack("<I4xQH6x", symbol_hash("Flow_Setup"), fields, 1),
                   fields: struct.pack("<Q", obj),
                   obj: struct.pack("<QIIi", base + 0xC46B38, 1, symbol_hash("Flow_Act"), 1)}
        result = read_story(MockMemory(regions).read, base)
        self.assertEqual(result["jobs"], {"Flow_Setup": {"Flow_Act": 1}})

    def test_actor_context_matches_name_lookup(self):
        base, actor, action, manager, definition, name = 0x140000000, 0x20000, 0x30000, 0x40000, 0x50000, 0x60000
        state = struct.pack("<i4xi4xQ", 46, 10, action)
        regions = {actor + 0x6B0: state, base + CONTEXT_MANAGER_RVA: struct.pack("<Q", manager),
                   manager + 0x8F0: struct.pack("<I", 100),
                   manager + 0xF0 + 46 * 8: struct.pack("<Q", definition),
                   definition + 8: struct.pack("<Q", name), name: b"Default\0" + bytes(24)}
        self.assertEqual(read_context(MockMemory(regions).read, base, actor)["name"], "Default")
        regions[actor + 0x6B0] = struct.pack("<i4xi4xQ", 10, 10, action)
        regions[action + 0x11E] = struct.pack("<h", 46)
        self.assertEqual(read_context(MockMemory(regions).read, base, actor)["name"], "Default")

    def test_mock_actor_key_presence_is_not_hand_or_unlock_state(self):
        base, actor, models, model, table, text, items, node, definition = (
            0x140000000, 0x20000, 0x30000, 0x40000, 0x50000, 0x60000, 0x70000, 0x80000, 0x90000)
        metadata = bytearray(0x38)
        struct.pack_into("<h", metadata, 8, 227)
        struct.pack_into("<Q", metadata, 0x30, text)
        regions = {base + PLAYER_RVA: struct.pack("<Q", actor), actor + 0xD4: struct.pack("<I", 0x1000),
                   actor + 0x650: struct.pack("<Q", model), model: metadata,
                   base + MODELS_RVA: struct.pack("<Q", models), models + 0xE0: struct.pack("<I", 1002),
                   models + 0x118: struct.pack("<Q", table), table + 227 * 8: struct.pack("<Q", model),
                   text: b"COP\0" + bytes(28), actor + 0x8A0: struct.pack("<Q", items),
                   items + 0x90: struct.pack("<Q", node), node: struct.pack("<QQQ", 0, 0, definition),
                   definition + 0x58: b"M02_Dspot_key_item\0" + bytes(32), actor + 0x6B0: bytes(0x18)}
        result = read_actor(MockMemory(regions).read, base)
        self.assertEqual(result["equipped_internal_name"], "COP")
        self.assertTrue(result["chief_office_key_present"])
        self.assertFalse(result["held_in_hand_independently_verified"])
        regions[node] = struct.pack("<QQQ", 0, node, definition)
        with self.assertRaises(ValueError):
            read_actor(MockMemory(regions).read, base)
        regions[items + 0x90] = bytes(8)
        self.assertFalse(read_actor(MockMemory(regions).read, base)["chief_office_key_present"])
        with self.assertRaises(ValueError):
            parse_item_node(bytes(24))

    def test_mock_character_inventory_merges_owned_and_pending_without_locked_defaults(self):
        base, models, controller, table, state, extras = 0x140000000, 0x20000, 0x30000, 0x40000, 0x50000, 0x60000
        count = 703
        header = bytearray(0x120)
        struct.pack_into("<I", header, 0xE0, count)
        struct.pack_into("<Q", header, 0x118, table)
        control = bytearray(0x70)
        struct.pack_into("<16h", control, 8, *range(16))  # Defaults must not imply unlocks.
        struct.pack_into("<16h", control, 0x2A, 227, *([-1] * 15))
        struct.pack_into("<Q", control, 0x60, extras)
        struct.pack_into("<I", control, 0x6C, 1)
        flags = bytearray(0x80 + count)
        flags[244 // 8] |= 1 << (244 % 8)
        flags[0x80 + 244] = 1
        memory = {base + MODELS_RVA: struct.pack("<Q", models),
                  base + CONTROLLER_RVA: struct.pack("<Q", controller),
                  base + CHARACTER_STATE_RVA: struct.pack("<Q", state), models: bytes(header),
                  controller + 0x140: bytes(control), state: bytes(flags), extras: struct.pack("<h", 702)}
        for index, name in ((227, "COP"), (244, "Civilian_ChaseMcCain"), (702, "Cop_Female_P2")):
            record, text = 0x80000 + index * 256, 0x180000 + index * 256
            metadata = bytearray(0x38)
            struct.pack_into("<Q", metadata, 0x30, text)
            memory[table + index * 8] = struct.pack("<Q", record)
            memory[record] = bytes(metadata)
            memory[text] = name.encode("ascii") + bytes(32 - len(name))
        def read(address, size):
            for start, data in memory.items():
                if start <= address and address + size <= start + len(data):
                    return data[address - start:address - start + size]
            raise ValueError("Mock read outside fixture")
        result = read_characters(read, base)
        self.assertEqual([row["model_id"] for row in result["characters"]], [227, 244, 702])
        self.assertTrue(result["characters"][0]["pending_grant"])
        self.assertTrue(result["characters"][1]["owned_byte"])
        self.assertFalse(result["characters"][2]["found_bit"])

    def test_stud_profile_count_is_64_bit_and_not_checkpoint(self):
        data = bytearray(0x3A0)
        struct.pack_into("<Q", data, 0x48, 10580)
        struct.pack_into("<I", data, 0x14, 2171)
        data[0x40] = 1
        struct.pack_into("<II", data, 0x360, 450, 0)
        values = parse_stats(data, struct.pack("<Q", 2**32 + 17580))
        self.assertEqual(values["studs"], 2**32 + 17580)
        self.assertEqual(values["stats_stud_checkpoint"], 10580)
        self.assertEqual(values["super_bricks"], 2171)
        self.assertEqual(values["gold_brick_total"], 450)
        with self.assertRaises(ValueError):
            parse_stats(data[:-1], bytes(8))

    def test_super_brick_mode_branches(self):
        data = bytearray(0x3A0)
        struct.pack_into("<II", data, 0x14, 2171, 4500)
        self.assertEqual(parse_stats(data, bytes(8))["super_bricks"], 4500)
        for offset in (0x40, 0x5D, 0x5E):
            data[offset] = 1
            self.assertEqual(parse_stats(data, bytes(8))["super_bricks"], 2171)
            data[offset] = 0

    def test_character_defaults_do_not_become_pending_unlocks(self):
        data = bytearray(0x70)
        struct.pack_into("<16h", data, 8, *range(16))
        struct.pack_into("<16h", data, 0x2A, 227, *([-1] * 15))
        control = parse_character_control(data, [702])
        self.assertEqual(control["pending_class_model_ids"][0], 227)
        self.assertEqual(control["pending_class_model_ids"][1], -1)
        self.assertEqual(control["pending_extra_model_ids"], [702])
        with self.assertRaises(ValueError):
            parse_character_control(data, [1024])

    def test_collection_aliases_and_progress_are_distinct(self):
        text = ('collect Example token cat 8\ncollect Example token cat 4 no_progress\n'
                'collect Custom token cat 0 no_progress\n;VEHICLE_LIST_START\ncollect Car token cat 12')
        roster = collection.parse_collection(text)["entries"]
        self.assertEqual(roster["EXAMPLE"]["categories"], [8, 4])
        self.assertTrue(roster["EXAMPLE"]["counts_for_progress"])
        self.assertFalse(roster["CUSTOM"]["counts_for_progress"])
        self.assertEqual(roster["CAR"]["kind"], "vehicle")

    def test_model_cstring_does_not_read_across_page(self):
        reads = []
        def read(address, size):
            reads.append((address, size))
            return b"AB" if address == 0x1FFE else b"C\0" + bytes(size - 2)
        self.assertEqual(cstring(read, 0x1FFE), "ABC")
        self.assertEqual(reads[0], (0x1FFE, 2))

    def test_stats_pointer_change_is_rejected(self):
        base, manager, profile = 0x140000000, 0x20000, 0x30000
        reads = 0
        def read(address, size):
            nonlocal reads
            if address == base + STATS_RVA:
                reads += 1
                return struct.pack("<Q", manager if reads == 1 else manager + 8)
            if address == base + PROFILE_RVA:
                return struct.pack("<Q", profile)
            return bytes(size)
        with self.assertRaises(RuntimeError):
            read_stats(read, base)

    def test_duplicate_objective_names_remain_ambiguous(self):
        data = struct.pack("<Ih6xIh6x", 329245068, 1058, 329245068, 1055)
        self.assertEqual(parse_record_groups(data), {329245068: [1058, 1055]})
        with self.assertRaises(ValueError):
            parse_records(data)
    def test_diagnostic_build_is_reproducible_and_allowlisted(self):
        import zipfile
        with tempfile.TemporaryDirectory() as folder:
            first, second = Path(folder) / "first.pyz", Path(folder) / "second.pyz"
            self.assertEqual(builder.build(TOOLS.parent, first), builder.build(TOOLS.parent, second))
            with zipfile.ZipFile(first) as package:
                self.assertEqual(set(package.namelist()), set(builder.SOURCES) | {"__main__.py", "manifest.json"})

    def test_gizmo_sections_respect_bounds(self):
        data = struct.pack("<III", 17, 0, 7) + b"GizItem" + struct.pack("<I", 3) + b"abc" + bytes(4) + b"opaque"
        blocks, tail = resources.sections(data)
        self.assertEqual(blocks, [dict(name="GizItem", offset=23, size=3)])
        self.assertEqual(data[tail:], b"opaque")
        with self.assertRaises(ValueError):
            resources.sections(data[:25])
        with self.assertRaises(ValueError):
            resources.sections(bytes(20))

    def test_mock_objective_snapshot_and_relocation(self):
        import objective_reader
        base, manager, table, owner, bits = 0x7FF700000000, 0x20000, 0x30000, 0x40000, 0x50000
        descriptor = struct.pack("<QHh", table, 2, 2)
        memory = {base + objective_reader.MANAGER_POINTER_RVA: struct.pack("<Q", manager),
                  manager + 0x950: descriptor, table: struct.pack("<Ih6xIh6x", 10, 0, 20, 35),
                  manager + 0x978: struct.pack("<Q", owner), owner: struct.pack("<Q", bits),
                  bits: b"\x01\0\0\0\x08\0\0\0"}
        def read(address, size):
            self.assertEqual(len(memory[address]), size)
            return memory[address]
        result = read_objectives(read, base)
        self.assertEqual([row["candidate_complete"] for row in result["records"]], [True, True])
        reads = 0
        def changing(address, size):
            nonlocal reads
            if address == base + objective_reader.MANAGER_POINTER_RVA:
                reads += 1
                if reads > 1:
                    return struct.pack("<Q", manager + 16)
            return read(address, size)
        with self.assertRaises(RuntimeError):
            read_objectives(changing, base)
        with self.assertRaises(ValueError):
            read_objectives(lambda address, size: b"", base)

    def test_job_defaults_round_trip(self):
        sample = (jobs.Job("Flow.Act1", (jobs.Field("Stage", "Int", 1, -3),
                                          jobs.Field("Done", "Bool", 0, False))),)
        encoded = jobs.encode(sample)
        decoded = jobs.parse(encoded)
        self.assertEqual(decoded[0].fields[0].default, -3)
        self.assertEqual(jobs.encode(decoded), encoded)
        self.assertFalse(decoded[0].fields[1].default)

    def test_job_invalid_headers_sizes_and_types(self):
        data = jobs.encode((jobs.Job("Test", (jobs.Field("Done", "Bool", 1, True),)),))
        for invalid in (data[:-1], data + b"extra", data.replace(b"Bool", b"Text"),
                        data.replace(b"JobE", b"JobX"), data[:-6] + b"\x02" + data[-5:]):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                jobs.parse(invalid)

    def test_job_duplicate_fields_rejected(self):
        with self.assertRaises(ValueError):
            jobs.encode((jobs.Job("Test", (jobs.Field("Same", "Bool", 1, True),
                                           jobs.Field("Same", "Int", 0, 2))),))

    def test_script_comments_and_strings_are_not_calls(self):
        text = '// UnlockAbility("fake");\nText t("LockAbility(fake)");\nUnlockAbility(#Jetpack);'
        calls = scripts.catalogue(text)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["line"], 3)
        self.assertEqual(calls[0]["arguments"][0]["symbol"], "Jetpack")
        self.assertEqual(scripts.catalogue('UnlockAbility(#2x_Brick_Multi);')[0]["arguments"][0]["symbol"],
                         "2x_Brick_Multi")

    def test_script_variable_evidence_is_not_direct_literal(self):
        text = 'Text t; t="First"; t="Second"; CityObjective_SetComplete(t);'
        argument = scripts.catalogue(text)[0]["arguments"][0]
        self.assertIsNone(argument["literal"])
        self.assertEqual(argument["possible_literals"], ["First", "Second"])

    def test_script_nested_call_and_receiver(self):
        text = 'Job j("Flow.Act1"); j.SetValue("Stage", GetValue("Other", 1));'
        calls = scripts.catalogue(text)
        self.assertEqual(calls[0]["possible_receiver_paths"], ["Flow.Act1"])
        self.assertEqual(len(calls[0]["arguments"]), 2)
        with self.assertRaises(ValueError):
            scripts.catalogue('UnlockAbility("missing close";')

    def test_ability_query_matches_static_or_semantics(self):
        existing, pending = [0] * 51, [0] * 51
        existing[0], pending[18] = 1, 1
        values = decode_ability_query(existing, pending)
        self.assertTrue(values["GrappleGun"])
        self.assertTrue(values["Jetpack"])
        self.assertFalse(values["SuperStrength"])
        with self.assertRaises(ValueError):
            decode_ability_query([], pending)

    def test_runtime_symbol_hash_profile(self):
        self.assertEqual(symbol_hash("GrappleGun"), 897586088)
        self.assertEqual(symbol_hash("Jetpack"), 2086321629)
        validate_table([symbol_hash(name) for name in ABILITY_NAMES])
        with self.assertRaises(ValueError):
            validate_table([0] * 51)

    def test_objective_records_and_bits(self):
        records = parse_records(struct.pack("<Ih6xIh6x", 123, 0, 456, 33))
        self.assertEqual(decode_bits(records, bytes([1, 0, 0, 0, 2, 0, 0, 0])), {123: True, 456: True})
        with self.assertRaises(ValueError):
            decode_bits(records, b"\0")
        with self.assertRaises(ValueError):
            parse_records(struct.pack("<Ih6x", 1, -1))

    def test_mock_uninitialized_objective_manager(self):
        self.assertEqual(read_objectives(lambda address, size: bytes(size), 0x140000000)["status"],
                         "not_initialized")

    def test_rc4_known_vector(self):
        self.assertEqual(archive.rc4(b"Plaintext", b"Key").hex(), "bbf316e8d940af0ad3")

    def test_crc_normalization(self):
        self.assertEqual(archive.name_crc("Stuff/test.txt"), archive.name_crc("STUFF\\TEST.TXT"))

    def test_traversal_rejected(self):
        for name in ("..\\secret", "C:\\secret", "\\root", "a:stream"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                archive.safe_target(Path(tempfile.gettempdir()), name)

    def test_invalid_pe_rejected(self):
        for data in (b"", b"MZ" + bytes(100)):
            with self.assertRaises(ValueError):
                inspect.inspect_pe(data)

    def test_synthetic_index_crc_matching(self):
        name = b"test.txt\0"
        data = struct.pack(">I8siIIII", 0, b".CC40TAD", -11, 2, 1, 1, len(name))
        data += name + bytes(4) + struct.pack(">IHHhH", 0, 0, 0, 0, 1)
        data += struct.pack(">iIQII", -11, 1, 32, 3, 3)
        data += struct.pack(">I", archive.name_crc("test.txt"))
        entries = archive.parse_index(data, 100)
        self.assertEqual(entries[0]["path"], "test.txt")
        with self.assertRaises(ValueError):
            archive.parse_index(data[:-1], 100)
        with self.assertRaises(ValueError):
            archive.parse_index(data, 34)

    def test_raw_zipx_and_deflate_extraction(self):
        original = b"test payload\n" * 20
        encoder = zlib.compressobj(wbits=-15)
        compressed = encoder.compress(original) + encoder.flush()
        for signature, chunk, size in ((b"ZIPX", original, len(original)),
                                        (b"ZIPX", compressed, len(original)),
                                        (b"DFLT", compressed, len(original))):
            if signature == b"ZIPX":
                chunk = archive.rc4(chunk, struct.pack("<I", len(chunk)))
            data = signature + struct.pack("<II", len(chunk), size) + chunk
            with tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / "synthetic.dat"
                path.write_bytes(data)
                entry = dict(offset=0, packed_size=len(data), size=size, packed=True)
                self.assertEqual(archive.extract(path, entry), original)
                with self.assertRaises(ValueError):
                    archive.extract(path, entry, limit=1)

    def test_duplicate_missions_rejected(self):
        text = 'START_SIDE_MISSION\nName "test"\nEND_SIDE_MISSION\n'
        self.assertEqual(mapping.parse_missions(text)[0]["Name"], "test")
        with self.assertRaises(ValueError):
            mapping.parse_missions(text * 2)


if __name__ == "__main__":
    unittest.main()
