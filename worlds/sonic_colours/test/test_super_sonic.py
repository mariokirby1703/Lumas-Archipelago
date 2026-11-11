from collections import Counter

import pytest

from ..Items import EMERALDS
from ..wisps import project_inventory
from ..client import super_sonic
from ..client.native_dol import Dol, patch_dol, plan, plan_for_digest, PAL_DOL_SHA256
from ..client.memory import SonicMemory, MemoryUnavailable
from .dol_memory import read_dol_memory


@pytest.mark.parametrize('enabled', [False, True])
@pytest.mark.parametrize('count', [0, 6, 7])
def test_super_permission_requires_option_and_every_distinct_ap_emerald(enabled, count):
    owned = {'counts': Counter(EMERALDS[:count])}
    projected = project_inventory(owned, {'super_sonic': enabled})
    assert projected['super_sonic_allowed'] == (enabled and count == 7)
    assert owned['counts'] == Counter(EMERALDS[:count])


def test_repeated_emeralds_do_not_replace_a_missing_colour():
    assert not project_inventory({'counts': Counter(EMERALDS[:-1] * 2)},
                                 {'super_sonic': True})['super_sonic_allowed']


def test_old_native_plan_remains_exactly_identifiable():
    old = plan(include_super_guard=False)
    assert plan_for_digest(old[2].hex()) == old
    assert not any(address == super_sonic.AUTO_UNLOCK for address, _, _ in old[0])
    current = plan()
    assert current[2] != old[2]
    assert plan_for_digest(current[2].hex()) == current


def test_auto_unlock_branch_skips_both_native_grant_and_notification():
    from capstone import Cs, CS_ARCH_PPC, CS_MODE_32, CS_MODE_BIG_ENDIAN
    address, original, replacement = super_sonic.patches()[0]
    assert original == bytes.fromhex('38610008')
    decoder = Cs(CS_ARCH_PPC, CS_MODE_32 | CS_MODE_BIG_ENDIAN)
    instruction, = decoder.disasm(replacement, address)
    assert instruction.mnemonic == 'b'
    assert int(instruction.op_str, 16) == super_sonic.AUTO_UNLOCK_END
    assert address < 0x8016C340 < 0x8016C34C < super_sonic.AUTO_UNLOCK_END


@pytest.mark.parametrize('disc', [b'SNCP8P', b'SNCE8P'])
def test_native_super_guard_validates_and_rejects_tampering(pal_dol_bytes, disc):
    import hashlib
    assert hashlib.sha256(pal_dol_bytes).hexdigest() == PAL_DOL_SHA256
    # The complete-game-land loop covers all 21 clear bits, followed by the
    # unconditional notification even when the AP setter refuses the grant.
    original = Dol(pal_dol_bytes)
    assert original.read(0x8016C300, 4).hex() == '3ba000fc'
    assert original.read(0x8016C324, 4).hex() == '281d0110'
    image = Dol(patch_dol(pal_dol_bytes, 'SuperGuard')[0])
    class Backend:
        def read_bytes(self, address, size):
            if address == 0x80000000:
                return (disc + bytes(26))[:size]
            if address == 0x80000007:
                return bytes(size)
            return read_dol_memory(image, address, size)
    memory = SonicMemory(Backend())
    memory.verify_revision()
    assert memory.native_patch['super_sonic_guard']
    address, before, after = super_sonic.patches()[0]
    image.replace(address, after, before)
    with pytest.raises(MemoryUnavailable, match='native AP patch modified'):
        memory.verify_revision()
