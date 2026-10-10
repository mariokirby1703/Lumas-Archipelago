"""Normal runtime regression coverage; overlays are not live Dolphin evidence."""
from dataclasses import replace
import pytest
from ..Items import ITEM_TABLE
from ..client import gameplay_controls, progression_hook
from ..client.hooks import NativeHooks
from ..client.journal import Journal
from ..client.memory import SonicMemory, MemoryUnavailable
from ..client.runtime import Runtime
from ..client.state import WritePolicy
from . import generate
from .test_runtime import IDENTITY
from .test_native_originals import PAIRS
from .test_pickup_integration import Overlay
from .test_white_capsule_controls import install


class BoundFixture:
    reason = 'explicit offline bound-profile fixture'
    def observe(self, snapshot): pass
    def check(self, snapshot): return ('fixture', snapshot.stage_epoch)
    def check_stats(self, snapshot): return self.check(snapshot)
    def can_record(self, snapshot): return True
    def can_record_pickups(self, snapshot): return False
    def can_send(self, snapshot): return True


@pytest.mark.skipif(not PAIRS, reason='original PAL captures absent')
@pytest.mark.parametrize('failed_hook', ('none', 'progression', 'gameplay'))
def test_normal_poll_configures_white_before_optional_failures_and_after_receipt_restart(tmp_path, monkeypatch, failed_hook):
    backend = Overlay(PAIRS[0])
    address = install(backend)
    memory = SonicMemory(backend)
    reader = NativeHooks()
    guard = BoundFixture()
    memory.write_guard = WritePolicy(memory, guard, reader.snapshot)
    hooks = NativeHooks()
    native = replace(reader.snapshot(memory), save_identity='fixture')
    hooks.snapshot = lambda memory: native
    hooks.project_permissions = lambda *args: None
    def unavailable(*args): raise MemoryUnavailable('optional fixture hook unavailable')
    if failed_hook == 'progression': monkeypatch.setattr(progression_hook, 'configure', unavailable)
    if failed_hook == 'gameplay': monkeypatch.setattr(gameplay_controls, 'configure', unavailable)
    slot = generate({'boost_lock': True}).worlds[1].fill_slot_data()
    white = [ITEM_TABLE['White Boost Wisp']]
    with Journal(tmp_path, IDENTITY) as journal:
        runtime = Runtime(slot, journal, guard, hooks)
        runtime.poll(memory, [], False)
        assert memory.read_u32(address+8) == 0
        assert hooks.gameplay_controls_status['white_capsules'] == {'available': True, 'white_allowed': False}
        runtime.poll(memory, white, True)
        assert memory.read_u32(address+8) == 1
        assert hooks.gameplay_controls_status['white_capsules']['white_allowed']
        assert journal.data['receipts'] == white
    with Journal(tmp_path, IDENTITY) as journal:
        runtime = Runtime(slot, journal, guard, hooks)
        # No ReceivedItems yet: the authenticated seed's durable history owns White.
        runtime.poll(memory, [], False)
        assert memory.read_u32(address+8) == 1
        # A different stage rebuilds the hook attribution without re-opening actors.
        native = replace(native, stage_epoch='next-stage')
        runtime.poll(memory, white, True)
        assert memory.read_u32(address+8) == 1
        assert not any(a == 0x90b59840+0x110 for a, _ in backend.writes)
