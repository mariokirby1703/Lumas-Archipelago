"""Experimental, executable-specific CREATE Wii Object popup patch.

Addresses/ABI are verified against the supported executable and its UI scripts.
Memory access is injected by the client; this module never owns a Dolphin hook.
The cave is retained on uninstall because a live vanilla UI may still call back.
"""
from __future__ import annotations

from dataclasses import dataclass
import logging
import struct
import time

logger = logging.getLogger("Client")
MAGIC = 0x41504F50
VERSION = 3
IDLE, PENDING, ACTIVE, ERROR = range(4)
MODAL_LAYER = 0x80948040
OBJECT_REGISTRY_COUNT = 0x80904C84
VTABLE_SLOT = 0x805E2C70
ORIGINAL_UPDATE = 0x8000D880
GAME_SINGLETON = 0x806798C0
GAME_VTABLE = 0x805E2C4C
HEARTBEAT_TIMEOUT_SECONDS = 5.0
CODE_ORIGINALS = {0x80091D0C: 0x3BAD8AD0, 0x800921E0: 0x4BF93381}
ORIGINALS = {VTABLE_SLOT: ORIGINAL_UPDATE, **CODE_ORIGINALS}
# Refuse old runtime revisions rather than mixing instruction-cache state.
LEGACY_ORIGINALS = {0x8000DB5C: 0x4808A365, 0x80092184: 0x3A600000,
                    0x8009240C: 0x3A730001, 0x80092424: 0x7C1EE800,
                    0x80091DBC: 0x481FC175}


def ppc_branch(source: int, target: int, *, link: bool = False) -> int:
    delta = target - source
    if source % 4 or target % 4:
        raise ValueError("PPC branch target/source is not 4-byte aligned")
    if not -0x02000000 <= delta < 0x02000000:
        raise ValueError("PPC relative branch target is out of range")
    return 0x48000000 | (delta & 0x03FFFFFC) | int(link)


def word(value: int) -> bytes:
    return struct.pack(">I", value)


@dataclass(frozen=True)
class PopupPatchLayout:
    code_base: int = 0x80006048
    dispatcher: int = 0x80006048
    maintain_hooks: int = 0x80006220
    object_available_hook: int = 0x80006360
    object_display_hook: int = 0x800063B0
    closed_callback: int = 0x800063E4
    mailbox: int = 0x80006400
    end: int = 0x80006470


def hook_words(layout):
    return {VTABLE_SLOT: layout.dispatcher,
            0x80091D0C: ppc_branch(0x80091D0C, layout.object_display_hook),
            0x800921E0: ppc_branch(0x800921E0, layout.object_available_hook, link=True)}


class _Routine:
    """Small label/fixup builder; conditional branches use CR0 only."""
    def __init__(self, base):
        self.base, self.words, self.labels, self.fixups = base, [], {}, []

    def emit(self, *words):
        self.words.extend(words)

    def label(self, name):
        self.labels[name] = len(self.words) * 4 + self.base

    def branch(self, target, condition=None, *, link=False):
        self.fixups.append((len(self.words), target, condition, link))
        self.emit(0)

    def build(self):
        for index, target, condition, link in self.fixups:
            target = self.labels[target] if isinstance(target, str) else target
            source = self.base + index * 4
            if condition is None:
                self.words[index] = ppc_branch(source, target, link=link)
            else:
                delta = target - source
                if delta % 4 or not -0x8000 <= delta < 0x8000:
                    raise ValueError("PPC conditional branch out of range/alignment")
                self.words[index] = condition | (delta & 0xFFFC)
        return b"".join(map(word, self.words))


def build_image(layout: PopupPatchLayout) -> bytes:
    if layout != PopupPatchLayout():
        raise ValueError("Only the verified CREATE executable layout is supported")
    load_mailbox = (0x3D808000, 0x618C6400)
    hooks = hook_words(layout)

    def load(r, register, value):
        r.emit(0x3C000000 | register << 21 | value >> 16,
               0x60000000 | register << 21 | register << 16 | value & 0xFFFF)

    d = _Routine(layout.dispatcher)
    d.emit(0x9421FFC0, 0x7C0802A6, 0x90010044)
    # SimUpdate(this, const cTime&) receives the untouched incoming r3/r4.
    d.branch(ORIGINAL_UPDATE, link=True)
    d.emit(0x9061003C)
    d.branch(layout.maintain_hooks, link=True)
    d.emit(*load_mailbox, 0x816C001C, 0x396B0001, 0x916C001C)
    d.emit(0x800C0000, 0x3D604150, 0x616B4F50, 0x7C005800)
    d.branch("return", 0x40820000)
    d.emit(0x800C0004, 0x28000000 | VERSION)
    d.branch("return", 0x40820000)
    d.emit(0x800C0048, 0x28000001)  # guest hooks installed/cache synchronized
    d.branch("return", 0x40820000)
    d.emit(0x800C0044, 0x28000001)  # Python still enables dispatch
    d.branch("return", 0x40820000)
    d.emit(0x800C0008, 0x28000001)
    d.branch("return", 0x40820000)
    d.emit(0x800C000C, 0x28000106)
    d.branch("invalid", 0x40800000)
    d.emit(0x3D6080B2, 0x880BABD3, 0x28000002)
    d.branch("guard_ok", 0x41820000)
    d.emit(0x280000FF)
    d.branch("return", 0x40820000)
    d.label("guard_ok")
    d.emit(0x3D608095, 0x800B8040, 0x28000000)
    d.branch("return", 0x40820000)
    d.emit(0x880C0034, 0x28000000)
    d.branch("return", 0x40820000)
    d.emit(0x800C0020, 0x28000000)
    d.branch("return", 0x40820000)
    # Native registry/preflight works independently of Python MEM2 traversal.
    load(d, 11, OBJECT_REGISTRY_COUNT)
    d.emit(0x800B0000, 0x808C000C, 0x7C040040)  # cmplw target,count
    d.branch("return", 0x40800000)
    load(d, 3, 0x808D3440)
    d.branch(0x80490BF0, link=True)
    d.emit(0x28030000)
    d.branch("return", 0x41820000)
    d.emit(0x80030000, 0x28000000)  # descriptor must exist
    d.branch("return", 0x41820000)
    d.emit(0x7C0B0378, 0x800B0340, 0x28000000)  # descriptor unlockable flag
    d.branch("return", 0x41820000)
    d.emit(*load_mailbox, 0x800C0008, 0x28000001)  # cancellation during preflight
    d.branch("return", 0x40820000)
    d.emit(0x800C0044, 0x28000001)
    d.branch("return", 0x40820000)
    d.emit(0x38000000, 0x900C0018, 0x38000002, 0x900C0008)
    d.emit(0x386C0020, 0x388C0040, 0x38A00000, 0x38CC0038,
           0x38E00004, 0x39000140, 0x392000B4)
    d.branch(0x80074930, link=True)
    d.emit(*load_mailbox, 0x800C0020, 0x28000000)
    d.branch("return", 0x40820000)
    d.emit(0x38000003)
    d.branch("error")
    d.label("invalid")
    d.emit(0x38000001)
    d.label("error")
    d.emit(0x900C0018, 0x38000003, 0x900C0008)
    d.label("return")
    d.emit(0x8061003C, 0x80010044, 0x7C0803A6, 0x38210040, 0x4E800020)

    # Only guest PPC writes executable hooks. Python publishes code once and
    # redirects the data pointer. Guest removal flushes before detaching itself;
    # a paused game completes removal on its next SimUpdate, without Gecko.
    m = _Routine(layout.maintain_hooks)
    m.emit(*load_mailbox, 0x814C0044)  # enabled
    for index, (address, original) in enumerate(CODE_ORIGINALS.items()):
        load(m, 11, address)
        load(m, 5, original)
        load(m, 6, hooks[address])
        m.emit(0x800B0000, 0x7C002800)
        m.branch(f"known{index}", 0x41820000)
        m.emit(0x7C003000)
        m.branch(f"known{index}", 0x41820000)
        # Never overwrite somebody else's hook. Disable, then restore any
        # other known hook on the following frame before removing the vtable.
        m.emit(0x280A0000)
        m.branch(f"next{index}", 0x41820000)
        m.emit(0x38000005, 0x900C0018, 0x38000003, 0x900C0008,
               0x38000000, 0x900C0044, 0x900C0048, 0x4E800020)
        m.label(f"known{index}")
        m.emit(0x280A0001)
        m.branch(f"write{index}", 0x40820000)
        m.emit(0x7CC53378)  # mr r5,r6 (patched instruction)
        m.label(f"write{index}")
        m.emit(0x90AB0000, 0x7C00586C, 0x7C0004AC, 0x7C005FAC)
        # stw; dcbst 0,r11; sync; icbi 0,r11
        m.label(f"next{index}")
    m.emit(0x7C0004AC, 0x4C00012C, 0x914C0048, 0x280A0000)
    m.branch("return", 0x40820000)
    load(m, 11, VTABLE_SLOT)
    load(m, 5, layout.dispatcher)
    m.emit(0x800B0000, 0x7C002800)
    m.branch("return", 0x40820000)
    load(m, 5, ORIGINAL_UPDATE)
    m.emit(0x90AB0000, 0x7C0004AC)
    m.label("return")
    m.emit(0x4E800020)

    def ap_owner_guard(r, owner_load):
        r.emit(*load_mailbox, 0x800C0008, 0x28000002)
        r.branch("vanilla", 0x40820000)
        r.emit(0x396C0020, owner_load, 0x7C005800)
        r.branch("vanilla", 0x40820000)

    a = _Routine(layout.object_available_hook)
    ap_owner_guard(a, 0x801C0020)
    a.emit(0x800C000C, 0x7C009800, 0x38600000)
    a.branch("return", 0x40820000)
    a.emit(0x38600001)  # exact target, no threshold write needed
    a.label("return")
    a.emit(0x4E800020)
    a.label("vanilla")
    a.branch(0x80025560)

    s = _Routine(layout.object_display_hook)
    ap_owner_guard(s, 0x80190004)
    s.emit(0x3BAD8AD8)  # r29 = "unlock"; type 4 still builds the object array
    s.branch(0x80091D10)
    s.label("vanilla")
    s.emit(CODE_ORIGINALS[0x80091D0C])  # r29 = "award"
    s.branch(0x80091D10)

    c = _Routine(layout.closed_callback)
    c.emit(0x80030010, 0x90030014, 0x38000000, 0x90030008, 0x4E800020)
    image = bytearray(layout.end - layout.code_base)
    for routine, limit in ((d, layout.maintain_hooks), (m, layout.object_available_hook),
                           (a, layout.object_display_hook), (s, layout.closed_callback),
                           (c, layout.mailbox)):
        code = routine.build()
        if routine.base + len(code) > limit:
            raise ValueError(f"Popup routine {routine.base:08X} exceeds cave space ({len(code)} bytes)")
        start = routine.base - layout.code_base
        image[start:start + len(code)] = code
    offset = layout.mailbox - layout.code_base
    image[offset:offset + 8] = word(MAGIC) + word(VERSION)
    image[offset + 0x38:offset + 0x44] = (
        word(layout.closed_callback) + word(layout.mailbox) + word(layout.mailbox + 0x4C))
    image[offset + 0x44:offset + 0x48] = word(1)
    message = b"$GUI_PR_UNLOCK_GAME_OBJECT\0"
    image[offset + 0x4C:offset + 0x4C + len(message)] = message
    return bytes(image)


class PopupRuntime:
    def __init__(self, *, probe_timeout: float = HEARTBEAT_TIMEOUT_SECONDS):
        self.layout = PopupPatchLayout()
        self.image = build_image(self.layout)
        self.hooks = hook_words(self.layout)
        self.installed = False
        self.ready = False
        self.failure = None
        self._heartbeat = None
        self.probe_timeout = probe_timeout
        self._last_heartbeat_at = 0.0

    def diagnostics(self, read_memory):
        return {
            "installed": self.installed,
            "ready": self.ready,
            "failure": self.failure,
            "heartbeat_unchanged_seconds": round(time.monotonic() - self._last_heartbeat_at, 1)
            if self.installed else None,
            "cave_matches": self._known_image(read_memory(self.layout.code_base, len(self.image))),
            "hooks": {f"0x{address:08X}": {
                "ram": read_memory(address, 4).hex().upper(),
                "expected": f"{value:08X}",
            } for address, value in self.hooks.items()},
        }

    def snapshot(self, read_memory):
        raw = read_memory(self.layout.mailbox, 0x4C)
        fields = struct.unpack(">8I", raw[:0x20])
        result = dict(zip(("magic", "version", "status", "object_id", "request_seq",
                           "ack_seq", "error", "heartbeat"), fields))
        result.update(popup_pointer=int.from_bytes(raw[0x20:0x24], "big"),
                      active=raw[0x34], enabled=int.from_bytes(raw[0x44:0x48], "big"),
                      hooks_applied=int.from_bytes(raw[0x48:0x4C], "big"))
        return result

    def status(self, read_memory):
        return self.snapshot(read_memory)["status"]

    def heartbeat(self, read_memory):
        return self.snapshot(read_memory)["heartbeat"]

    def _known_image(self, data):
        # Mutable mailbox and owner fields are excluded; signature alone is
        # insufficient to accept somebody else's code or a partial installation.
        offset = self.layout.mailbox - self.layout.code_base
        return (len(data) == len(self.image) and data[:offset + 8] == self.image[:offset + 8]
                and data[offset + 0x38:offset + 0x44] == self.image[offset + 0x38:offset + 0x44]
                and data[offset + 0x4C:] == self.image[offset + 0x4C:])

    def ensure_installed(self, read_memory, write_memory):
        if self.failure:
            return False
        try:
            if read_memory(GAME_SINGLETON, 4) != word(GAME_VTABLE):
                raise RuntimeError("CREATE singleton/vtable is not ready or has changed")
            for address, original in LEGACY_ORIGINALS.items():
                if read_memory(address, 4) != word(original):
                    raise RuntimeError("old/conflicting popup patch detected; stop and freshly boot CREATE")
            for address, original in ORIGINALS.items():
                actual = int.from_bytes(read_memory(address, 4), "big")
                if actual not in (original, self.hooks[address]):
                    raise RuntimeError(f"unexpected instruction at 0x{address:08X}: 0x{actual:08X}")
            cave = read_memory(self.layout.code_base, len(self.image))
            if cave == bytes(len(self.image)):
                if any(read_memory(a, 4) != word(o) for a, o in ORIGINALS.items()):
                    raise RuntimeError("hook points into an empty code cave")
                write_memory(self.layout.code_base, self.image)
                if read_memory(self.layout.code_base, len(self.image)) != self.image:
                    raise RuntimeError("code/data readback failed")
            elif not self._known_image(cave):
                raise RuntimeError("unknown nonzero code-cave contents")
            if not self.installed:
                self.reset_request(read_memory, write_memory)
                write_memory(self.layout.mailbox + 0x44, word(1))
                write_memory(VTABLE_SLOT, word(self.layout.dispatcher))
                if read_memory(VTABLE_SLOT, 4) != word(self.layout.dispatcher):
                    raise RuntimeError("vtable data-pointer readback failed")
                self.installed = True
                self._heartbeat = self.heartbeat(read_memory)
                self._last_heartbeat_at = time.monotonic()
                logger.info("Create AP popup vtable bootstrap installed (no Gecko); waiting up to %.0fs for heartbeat.",
                            self.probe_timeout)
                return False
            state = self.snapshot(read_memory)
            if not state["enabled"] or state["error"] == 5:
                raise RuntimeError("guest popup hooks disabled or conflicting instruction detected")
            if read_memory(VTABLE_SLOT, 4) != word(self.layout.dispatcher):
                raise RuntimeError("runtime vtable pointer changed after installation")
            beat = self.heartbeat(read_memory)
            applied = state["hooks_applied"] == 1
            if applied and any(read_memory(a, 4) != word(self.hooks[a]) for a in CODE_ORIGINALS):
                raise RuntimeError("runtime hooks changed after guest installation")
            if beat != self._heartbeat and applied:
                if not self.ready:
                    logger.info("Create AP Object popup runtime hook heartbeat confirmed.")
                self.ready = True
                self._last_heartbeat_at = time.monotonic()
            else:
                timeout = HEARTBEAT_TIMEOUT_SECONDS if self.ready else self.probe_timeout
                if time.monotonic() - self._last_heartbeat_at >= timeout:
                    logger.warning("Popup hook diagnostics before rollback: %s; mailbox=%s",
                                   self.diagnostics(read_memory), self.snapshot(read_memory))
                    raise RuntimeError(
                        "runtime hook heartbeat missing (error 4); RAM readback alone does not prove "
                        "instruction execution. Resume Dolphin if paused. This build uses the vtable "
                        "bootstrap without Gecko; freshly boot CREATE without a save state, then use "
                        "/createpopupretry and /createpopupstatus to diagnose the virtual call.")
            self._heartbeat = beat
            return self.ready
        except Exception as error:
            self.failure = str(error)
            self.ready = False
            logger.warning("Create AP Object popup runtime patch refused: %s", error)
            self.uninstall(read_memory, write_memory)
            return False

    def reset_request(self, read_memory, write_memory):
        if self._known_image(read_memory(self.layout.code_base, len(self.image))):
            if self.status(read_memory) == PENDING:
                write_memory(self.layout.mailbox + 8, word(IDLE))

    def uninstall(self, read_memory, write_memory):
        # Guest restores and invalidates its instructions before detaching the
        # vtable. Keep the entry installed until that cleanup can actually run.
        # In particular, a paused Dolphin must flush on resume, not be detached
        # by Python while stale JIT code still points into the cave.
        try:
            self.reset_request(read_memory, write_memory)
            if self._known_image(read_memory(self.layout.code_base, len(self.image))):
                write_memory(self.layout.mailbox + 0x44, word(0))
        except Exception:
            logger.debug("Could not request guest popup hook removal", exc_info=True)
        self.installed = self.ready = False

    def request_object(self, object_id, read_memory, write_memory):
        if not isinstance(object_id, int) or not 0 <= object_id < 262 or not self.ready:
            return False
        state = self.snapshot(read_memory)
        if (state["magic"] != MAGIC or state["version"] != VERSION
                or state["status"] != IDLE or state["active"] or state["popup_pointer"]):
            return False
        write_memory(self.layout.mailbox + 0x0C, word(object_id))
        write_memory(self.layout.mailbox + 0x10, word((state["request_seq"] + 1) & 0xFFFFFFFF))
        write_memory(self.layout.mailbox + 0x18, word(0))
        write_memory(self.layout.mailbox + 0x08, word(PENDING))  # publish last
        return True
