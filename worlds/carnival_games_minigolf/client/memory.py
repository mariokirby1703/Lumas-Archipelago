"""Big-endian, bounds-checked memory access independent of Dolphin's Python module."""
import hashlib
from dataclasses import dataclass

from .constants import CODE_SIGNATURES, MANAGER_PTR, SUPPORTED_GAME_ID


class MemoryUnavailable(RuntimeError):
    pass


def valid_pointer(address, size=4):
    return (isinstance(address, int) and address % 4 == 0 and
            (0x80004000 <= address <= 0x81800000 - size or
             0x90000000 <= address <= 0x94000000 - size))


class Memory:
    def __init__(self, backend):
        self.backend = backend

    def read(self, address, size):
        if not (0x80000000 <= address <= 0x81800000 - size or
                0x90000000 <= address <= 0x94000000 - size):
            raise MemoryUnavailable(f"Address outside Wii RAM: {address:#x}")
        data = bytes(self.backend.read_bytes(address, size))
        if len(data) != size:
            raise MemoryUnavailable("Short Dolphin read")
        return data

    def integer(self, address, size=4):
        return int.from_bytes(self.read(address, size), 'big')

    def pointer(self, address, size=4):
        value = self.integer(address)
        if not valid_pointer(value, size):
            raise MemoryUnavailable(f"Uninitialized or invalid pointer at {address:#x}")
        return value

    def write(self, address, data):
        if self.read(address, len(data)) != data:
            self.backend.write_bytes(address, data)
            if self.read(address, len(data)) != data:
                raise MemoryUnavailable("Dolphin write could not be verified")

    def put(self, address, value, size=1):
        self.write(address, value.to_bytes(size, 'big'))

    def verify_game(self):
        return (self.read(0x80000000, 6) == SUPPORTED_GAME_ID and
                all(hashlib.sha256(self.read(address, 64)).hexdigest() == digest
                    for address, digest in CODE_SIGNATURES))

    def resolve(self, local_player=0):
        manager = self.pointer(MANAGER_PTR, 0x1A0)
        count = self.integer(manager + 0x12C)
        if not 1 <= count <= 4 or not 0 <= local_player < count:
            raise MemoryUnavailable("Waiting for selected local player")
        roots = tuple(self.pointer(manager + 0x190 + i*4, 0x2E0) for i in range(count))
        if len(set(roots)) != count:
            raise MemoryUnavailable("Player roots are not initialized")
        session = self.integer(manager + 0x114)
        if not valid_pointer(session, 0x2F4):
            session = None
        return Snapshot(manager, roots, roots[local_player], session, local_player)

    def confirm(self, snapshot):
        if self.resolve(snapshot.local_player) != snapshot:
            raise MemoryUnavailable("Player context changed during poll")


@dataclass(frozen=True)
class Snapshot:
    manager: int
    roots: tuple[int, ...]
    root: int
    session: int | None
    local_player: int
