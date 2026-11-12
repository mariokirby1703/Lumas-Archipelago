"""Shared native command protocol. No injection, hook installation or game writes."""
import struct

MAGIC = 0x4C435544
VERSION = 1
FORMAT = struct.Struct("<8I")
STATES = {0: "idle", 1: "pending", 2: "executing", 3: "returned", 4: "rejected"}


def make_command(pid: int, thread_id: int) -> bytes:
    if not 0 < pid <= 0xFFFFFFFF or not 0 < thread_id <= 0xFFFFFFFF:
        raise ValueError("A specific target PID and thread are required")
    # Initially idle: serializing a command does not authorize its execution.
    return FORMAT.pack(MAGIC, VERSION, 0, 1, pid, thread_id, 0, 0)


def decode_command(data: bytes) -> dict:
    if len(data) != FORMAT.size:
        raise ValueError("Incomplete native command")
    magic, version, state, opcode, pid, thread_id, error, context = FORMAT.unpack(data)
    if magic != MAGIC or version != VERSION or state not in STATES or opcode != 1:
        raise ValueError("Unsupported native command")
    if not pid or not thread_id:
        raise ValueError("Missing target identity")
    return dict(state=STATES[state], pid=pid, thread_id=thread_id, error=error,
                context_before=context, death_confirmed=False)
