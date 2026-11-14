import unittest
from native_context_policy import allows_native_command,PASSIVE_OPCODES

class NativeContextPolicyTests(unittest.TestCase):
    def test_vehicle_passive_grants_allowed_but_revocation_remains_blocked(self):
        for context in (27,157):
            for opcode in PASSIVE_OPCODES:
                self.assertTrue(allows_native_command(context,opcode))
                self.assertFalse(allows_native_command(context,opcode,alive=False))
            self.assertFalse(allows_native_command(context,8))
            self.assertTrue(allows_native_command(context,5))
    def test_interaction_and_death_do_not_gain_passive_grant_permissions(self):
        for context in (25,28,59,62,63,250):
            for opcode in PASSIVE_OPCODES:
                self.assertFalse(allows_native_command(context,opcode))
        self.assertTrue(allows_native_command(46,8))
