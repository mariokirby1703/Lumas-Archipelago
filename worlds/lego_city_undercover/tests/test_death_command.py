import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("death_command", Path(__file__).resolve().parents[1] / "bridge/death_command.py")
command = importlib.util.module_from_spec(spec)
spec.loader.exec_module(command)


class DeathCommandTests(unittest.TestCase):
    def test_wire_layout_and_idle_default(self):
        data = command.make_command(123, 456)
        self.assertEqual(len(data), 32)
        decoded = command.decode_command(data)
        self.assertEqual((decoded["pid"], decoded["thread_id"], decoded["state"]), (123, 456, "idle"))
        self.assertFalse(decoded["death_confirmed"])

    def test_invalid_identity_and_protocol(self):
        for pid, thread in ((0, 1), (1, 0), (-1, 2), (2**32, 3)):
            with self.assertRaises(ValueError):
                command.make_command(pid, thread)
        for data in (b"", bytes(32), command.make_command(1, 2)[:-1]):
            with self.assertRaises(ValueError):
                command.decode_command(data)
