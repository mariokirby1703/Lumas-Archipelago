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
VERSION = 5
IDLE, PENDING, ACTIVE, ERROR = range(4)
MODAL_LAYER = 0x80948040
OBJECT_REGISTRY_COUNT = 0x80904C84
VTABLE_SLOT = 0x805E2C70
ORIGINAL_UPDATE = 0x8000D880
GAME_SINGLETON = 0x806798C0
GAME_VTABLE = 0x805E2C4C
HEARTBEAT_TIMEOUT_SECONDS = 5.0
CODE_ORIGINALS = {0x800325E4: 0x4BFF2F7D}
ORIGINALS = {VTABLE_SLOT: ORIGINAL_UPDATE, **CODE_ORIGINALS}
# Refuse old runtime revisions rather than mixing instruction-cache state.
LEGACY_ORIGINALS = {0x8000DB5C: 0x4808A365, 0x80092184: 0x3A600000,
                    0x8009240C: 0x3A730001, 0x80092424: 0x7C1EE800,
                    0x80091DBC: 0x481FC175, 0x80091D0C: 0x3BAD8AD0,
                    0x800921E0: 0x4BF93381}


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
    construct_results: int = 0x80006270
    maintain_hooks: int = 0x80006380
    object_available_hook: int = 0x80006440
    closed_callback: int = 0x80006240
    mailbox: int = 0x80006480
    result_context: int = 0x800064D0
    end: int = 0x80006514


def hook_words(layout):
    return {VTABLE_SLOT: layout.dispatcher,
            0x800325E4: ppc_branch(0x800325E4, layout.object_available_hook, link=True)}


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
    load_mailbox = (0x3D808000, 0x618C6480)
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
    d.emit(0x800C0008, 0x28000002)
    d.branch("outro_fallback", 0x41820000)
    d.emit(0x28000001)
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
    d.emit(0x38000001, 0x980C0034)  # owner active until native End completes
    d.branch(layout.construct_results, link=True)
    d.emit(*load_mailbox, 0x800C0020, 0x28000000)
    d.branch("return", 0x40820000)
    d.emit(0x38000003)
    d.branch("error")
    d.label("invalid")
    d.emit(0x38000001)
    d.label("error")
    d.emit(0x900C0018, 0x38000003, 0x900C0008)
    d.branch("return")
    d.label("outro_fallback")
    # PO's final root frame is 375 (zero-based 374), with Event_OnOutroEnd
    # followed by Stop. Never use elapsed time or mere invisibility as proof.
    d.emit(0x800C0090, 0x816C0010, 0x7C005800)
    d.branch("return", 0x41820000)
    d.emit(0x806C0020, 0x28030000)
    d.branch("return", 0x41820000)
    d.emit(0x80830014, 0x28040000)
    d.branch("return", 0x41820000)
    d.emit(0x80840004, 0x28040000)  # movie reference, not slot asset pointer
    d.branch("return", 0x41820000)
    d.emit(0x800C0040, 0x7C002000)  # still the movie created for this request
    d.branch("return", 0x40820000)
    d.emit(0x80840064, 0x28040000)  # GFxMovieRoot root sprite
    d.branch("return", 0x41820000)
    d.emit(0x800400BC, 0x28000176)  # final frame 374 only
    d.branch("return", 0x40820000)
    d.emit(0x916C0090)  # mark before native cleanup, once per request
    d.branch(0x800336E0, link=True)
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
    ap_owner_guard(a, 0x801D0020)  # FePuzzleResults this = r29, callback owner +0x20
    a.emit(0x800C000C, 0x7C008800, 0x38600000)  # current Object ID = r17
    a.branch("return", 0x40820000)
    a.emit(0x38600001)
    a.label("return")
    a.emit(0x4E800020)
    a.label("vanilla")
    a.branch(0x80025560)

    f = _Routine(layout.construct_results)
    f.emit(0x9421FFE0, 0x7C0802A6, 0x90010024, *load_mailbox)
    f.emit(0x386C0038, 0x388C0050)
    f.branch(0x80031DB0, link=True)  # builds the one-object array in the same frame
    f.emit(*load_mailbox, 0x906C0020, 0x28030000)
    f.branch("return", 0x41820000)
    f.emit(0x80830014, 0x28040000)
    f.branch("return", 0x41820000)
    f.emit(0x80040000, 0x28000000)
    f.branch("return", 0x41820000)
    # Native UI registration: index = (movie_slot - manager.slots) / 24.
    load(f, 11, 0x80947F50)
    f.emit(0x7C8B2050, 0x38000018, 0x7C840396)  # subf r4,r11,r4; divwu r4,r4,r0
    load(f, 3, 0x80947A30)
    f.emit(0x38A00000, 0x38C00001)
    f.branch(0x804EA4D0, link=True)
    # Stop the PO root timeline at its initial frame before Congratulations
    # animates in, then run the actual PO object-only method. Unlock has already
    # initialized mItemData/m_numUnlocks inside the native factory.
    f.emit(*load_mailbox, 0x808C0020, 0x80840014, 0x38610008)
    f.branch(0x8000ED20, link=True)  # acquire movie ref into stack +8
    f.emit(0x80010008, *load_mailbox, 0x900C0040)
    for string_offset in (0x68, 0x73):
        f.emit(0x80610008, *load_mailbox, 0x388C0000 | string_offset,
               0x38AC008F, 0x4CC63182)  # empty Invoke format, no args
        f.branch(0x8028DF30, link=True)
    f.emit(0x80610008)
    f.branch(0x8035A96C, link=True)  # release movie ref
    f.label("return")
    f.emit(0x80010024, 0x7C0803A6, 0x38210020, 0x4E800020)

    c = _Routine(layout.closed_callback)
    c.emit(0x80030010, 0x90030014, 0x38000000, 0x90030008, 0x4E800020)
    image = bytearray(layout.end - layout.code_base)
    for routine, limit in ((d, layout.closed_callback), (c, layout.construct_results),
                           (f, layout.maintain_hooks), (m, layout.object_available_hook),
                           (a, layout.mailbox)):
        code = routine.build()
        if routine.base + len(code) > limit:
            raise ValueError(f"Popup routine {routine.base:08X} exceeds cave space ({len(code)} bytes)")
        start = routine.base - layout.code_base
        image[start:start + len(code)] = code
    offset = layout.mailbox - layout.code_base
    image[offset:offset + 8] = word(MAGIC) + word(VERSION)
    # Native FeMessageFlow::End releases the result object and UI slot, clears
    # owner.pointer, invokes our acknowledgement, then clears owner.active.
    image[offset + 0x2C:offset + 0x34] = word(layout.closed_callback) + word(layout.mailbox)
    image[offset + 0x38:offset + 0x40] = word(0x80074D90) + word(layout.mailbox + 0x20)
    image[offset + 0x44:offset + 0x48] = word(1)
    # Synthetic sPuzzleResults: no Puzzle pointer, one Object reward, no Sparks.
    image[offset + 0x60:offset + 0x64] = word(1)
    image[offset + 0x68:offset + 0x73] = b"_root.stop\0"
    image[offset + 0x73:offset + 0x8F] = b"_root.DeterminePlaySequence\0"
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
            "lifecycle": self.lifecycle(read_memory),
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

    def lifecycle(self, read_memory):
        state = self.snapshot(read_memory)
        def u32(address):
            return int.from_bytes(read_memory(address, 4), "big")
        result = {
            "popup_pointer": f"0x{state['popup_pointer']:08X}",
            "callback_invoked": bool(state["request_seq"] and state["ack_seq"] == state["request_seq"]),
            "status": state["status"], "request_seq": state["request_seq"],
            "ack_seq": state["ack_seq"], "modal": u32(MODAL_LAYER),
            "owner_active": bool(state["active"]),
            "fallback_seq": u32(self.layout.mailbox + 0x90),
            "movie_slot": None, "movie_slot_active": False, "root_frame_zero_based": None,
        }
        if state["popup_pointer"]:
            try:
                pointer = state["popup_pointer"]
                result["popup_vtable"] = f"0x{u32(pointer + 0x10):08X}"
                result["close_callback"] = f"0x{u32(pointer + 0x1C):08X}"
                result["callback_context"] = f"0x{u32(pointer + 0x20):08X}"
                slot = u32(pointer + 0x14)
                result["movie_slot"] = f"0x{slot:08X}"
                if slot:
                    movie = u32(slot + 4)
                    result["movie_slot_active"] = bool(u32(slot) and movie)
                    result["movie_slot_flags"] = f"0x{u32(slot + 0x0C):08X}"
                    sprite = u32(movie + 0x64) if movie else 0
                    if sprite:
                        result["root_frame_zero_based"] = u32(sprite + 0xBC)
            except Exception as error:
                result["read_error"] = str(error)
        return result

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
                and data[offset + 0x38:offset + 0x40] == self.image[offset + 0x38:offset + 0x40]
                and data[offset + 0x4C:offset + 0x90] == self.image[offset + 0x4C:offset + 0x90])

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
