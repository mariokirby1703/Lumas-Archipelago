"""Experimental, executable-specific CREATE Wii Object popup patch.

All addresses and the wrapper ABI come from the runtime implementation briefing.
Memory access is injected by the client; this module never owns a Dolphin hook.
The cave is retained on uninstall because a live vanilla UI may still call back.
"""
from __future__ import annotations

from dataclasses import dataclass
import logging
import struct

logger = logging.getLogger("Client")
MAGIC = 0x41504F50
VERSION = 1
IDLE, PENDING, ACTIVE, ERROR = range(4)
MODAL_LAYER = 0x80948040
ORIGINALS = {0x8000DB5C: 0x4808A365, 0x80092184: 0x3A600000, 0x8009240C: 0x3A730001}


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
    closed_callback: int = 0x80006200
    object_scan_start_hook: int = 0x80006240
    object_scan_step_hook: int = 0x80006280
    mailbox: int = 0x80006400
    end: int = 0x80006448


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
    # r12 is a volatile mailbox pointer, reloaded after calls. 64-byte EABI
    # frame with linkage area; preserve LR and original update's return in r3.
    load_mailbox = (0x3D808000, 0x618C6400)  # lis r12,0x8000; ori r12,r12,0x6400
    if layout != PopupPatchLayout():
        raise ValueError("Only the verified CREATE executable layout is supported")
    d = _Routine(layout.dispatcher)
    d.emit(0x9421FFC0, 0x7C0802A6, 0x90010044)  # stwu; mflr; stw LR
    d.branch(0x80097EC0, link=True)  # unconditionally preserve original update
    d.emit(0x9061003C, *load_mailbox, 0x816C001C, 0x396B0001, 0x916C001C)
    d.emit(0x800C0000, 0x3D604150, 0x616B4F50, 0x7C005800)  # magic vs r11
    d.branch("return", 0x40820000)  # bne
    d.emit(0x800C0004, 0x28000001)
    d.branch("return", 0x40820000)
    d.emit(0x800C0008, 0x28000001)
    d.branch("return", 0x40820000)
    d.emit(0x800C000C, 0x28000106)  # cmplwi r0,262 (also rejects negative IDs)
    d.branch("invalid", 0x40800000)  # bge
    # Recheck transition-sensitive RAM on the game thread, including requests
    # that waited behind a modal UI. Python supplies the positive Slot 3 session.
    d.emit(0x3D608069, 0x880BCFC3, 0x2800000A)  # challenge byte
    d.branch("return", 0x40810000)  # ble: challenge 0..10
    d.emit(0x3D6080B2, 0x880BABD3, 0x28000002)  # save guard byte
    d.branch("guard_ok", 0x41820000)
    d.emit(0x280000FF)
    d.branch("return", 0x40820000)
    d.label("guard_ok")
    d.emit(0x3D608095, 0x800B8040, 0x28000000)  # modal layer (signed displacement)
    d.branch("return", 0x40820000)
    d.emit(0x880C0034, 0x28000000)  # lbz handle.active
    d.branch("return", 0x40820000)
    d.emit(0x800C0020, 0x28000000)  # also require no existing popup pointer
    d.branch("return", 0x40820000)
    d.emit(0x38000000, 0x900C0018, 0x38000002, 0x900C0008)
    d.emit(0x386C0020, 0x388C0040, 0x38A00000, 0x38CC0038,
           0x38E00004, 0x39000140, 0x392000B4)
    d.branch(0x80074930, link=True)
    d.emit(*load_mailbox, 0x800C0020, 0x28000000)
    d.branch("return", 0x40820000)
    d.emit(0x38000003)  # popup creation returned NULL
    d.branch("error")
    d.label("invalid")
    d.emit(0x38000001)
    d.label("error")
    d.emit(0x900C0018, 0x38000003, 0x900C0008)
    d.label("return")
    d.emit(0x8061003C, 0x80010044, 0x7C0803A6, 0x38210040, 0x4E800020)

    c = _Routine(layout.closed_callback)
    c.emit(0x80030010, 0x90030014, 0x38000000, 0x90030008, 0x4E800020)
    routines = [(d, layout.closed_callback), (c, layout.object_scan_start_hook)]
    for base, original, ap_instruction, back, limit in (
        (layout.object_scan_start_hook, 0x3A600000, 0x826C000C, 0x80092188,
         layout.object_scan_step_hook),
        (layout.object_scan_step_hook, 0x3A730001, 0x3A607FFF, 0x80092410, layout.mailbox),
    ):
        r = _Routine(base)
        r.emit(*load_mailbox, 0x800C0008, 0x28000002)
        r.branch("vanilla", 0x40820000)
        r.emit(ap_instruction)
        r.branch(back)
        r.label("vanilla")
        r.emit(original)
        r.branch(back)
        routines.append((r, limit))
    image = bytearray(layout.end - layout.code_base)
    for routine, limit in routines:
        code = routine.build()
        if routine.base + len(code) > limit:
            raise ValueError("Popup routine exceeds reserved cave space")
        start = routine.base - layout.code_base
        image[start:start + len(code)] = code
    offset = layout.mailbox - layout.code_base
    image[offset:offset + 8] = word(MAGIC) + word(VERSION)
    image[offset + 0x38:offset + 0x44] = (
        word(layout.closed_callback) + word(layout.mailbox) + word(layout.mailbox + 0x44))
    image[offset + 0x44:offset + 0x48] = b" \0\0\0"
    return bytes(image)


class PopupRuntime:
    def __init__(self):
        self.layout = PopupPatchLayout()
        self.image = build_image(self.layout)
        self.hooks = {
            0x8000DB5C: ppc_branch(0x8000DB5C, self.layout.dispatcher, link=True),
            0x80092184: ppc_branch(0x80092184, self.layout.object_scan_start_hook),
            0x8009240C: ppc_branch(0x8009240C, self.layout.object_scan_step_hook),
        }
        self.installed = False
        self.ready = False
        self.failure = None
        self._heartbeat = None
        self._heartbeat_polls = 0

    def snapshot(self, read_memory):
        raw = read_memory(self.layout.mailbox, 0x38)
        fields = struct.unpack(">8I", raw[:0x20])
        result = dict(zip(("magic", "version", "status", "object_id", "request_seq",
                           "ack_seq", "error", "heartbeat"), fields))
        result.update(popup_pointer=int.from_bytes(raw[0x20:0x24], "big"),
                      active=raw[0x34])
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
                and data[offset + 0x38:] == self.image[offset + 0x38:])

    def ensure_installed(self, read_memory, write_memory):
        if self.failure:
            return False
        try:
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
                for address in (0x80092184, 0x8009240C, 0x8000DB5C):
                    write_memory(address, word(self.hooks[address]))
                    if read_memory(address, 4) != word(self.hooks[address]):
                        raise RuntimeError(f"hook readback failed at 0x{address:08X}")
                self.installed = True
                self._heartbeat = self.heartbeat(read_memory)
                logger.info("Create AP Object popup runtime patch installed.")
                return False
            if any(read_memory(a, 4) != word(h) for a, h in self.hooks.items()):
                raise RuntimeError("runtime hooks changed after installation")
            beat = self.heartbeat(read_memory)
            if beat != self._heartbeat:
                if not self.ready:
                    logger.info("Create AP Object popup runtime hook heartbeat confirmed.")
                self.ready = True
                self._heartbeat_polls = 0
            else:
                self._heartbeat_polls += 1
                if self._heartbeat_polls >= 50:
                    raise RuntimeError("runtime hook heartbeat missing (error 4); check Dolphin JIT")
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
        # Do not destroy a live owner or callback. Vanilla cleanup retains control.
        try:
            self.reset_request(read_memory, write_memory)
        except Exception:
            pass
        for address, original in ORIGINALS.items():  # main call first
            try:
                if read_memory(address, 4) == word(self.hooks[address]):
                    write_memory(address, word(original))
                    if read_memory(address, 4) != word(original):
                        logger.warning("Popup hook restoration readback failed at 0x%08X", address)
            except Exception:
                logger.debug("Could not restore popup hook at 0x%08X", address, exc_info=True)
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
