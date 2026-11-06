import hashlib
import unittest
from unittest.mock import patch

from ..client import memory as memory_module
from ..client.constants import MANAGER_PTR, USA_MANAGER_PTR
from ..client.memory import Memory
from .test_runtime import FakeDolphin


class TestRevision(unittest.TestCase):
    def test_region_selection_requires_matching_code_and_clears_stale_profile(self):
        backend = FakeDolphin()
        memory = Memory(backend)
        payloads = {b'RG9P54': b'P'*64, b'RG9E54': b'E'*64}
        pal = [(0x80010000, hashlib.sha256(payloads[b'RG9P54']).hexdigest())]
        usa = [(0x80010000, hashlib.sha256(payloads[b'RG9E54']).hexdigest())]
        with (patch.object(memory_module, 'CODE_SIGNATURES', pal),
              patch.object(memory_module, 'USA_CODE_SIGNATURES', usa)):
            for game_id, manager in ((b'RG9P54', MANAGER_PTR), (b'RG9E54', USA_MANAGER_PTR)):
                backend.write_bytes(0x80000000, game_id)
                backend.write_bytes(0x80010000, payloads[game_id])
                self.assertTrue(memory.verify_game())
                self.assertEqual(memory.game_id, game_id)
                self.assertEqual(memory.manager_ptr, manager)
                backend.write_bytes(0x80010000, b'X'*64)
                self.assertFalse(memory.verify_game())
                self.assertIsNone(memory.game_id)
            backend.write_bytes(0x80000000, b'RG9J54')
            self.assertFalse(memory.verify_game())
