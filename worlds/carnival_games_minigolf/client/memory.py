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
        try:
            data = bytes(self.backend.read_bytes(address, size))
        except (RuntimeError, OSError) as error:
            raise MemoryUnavailable(f"Temporary Dolphin memory read failure at {address:#x}") from error
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
        session = self.integer(manager + 0x114)
        if not valid_pointer(session, 0x2F4):
            session = None
        # manager+0x12C is not a reliable player count in every game state.
        root_values = tuple(self.integer(manager + 0x190 + i*4) for i in range(2))
        valid_roots = tuple((i, root) for i, root in enumerate(root_values) if valid_pointer(root, 0x2E0))
        if not valid_roots:
            raise MemoryUnavailable("Waiting for game player state.")
        selected = next(((i, root) for i, root in valid_roots if i == local_player), None)
        if selected is None:
            raise MemoryUnavailable("Waiting for configured game player state.")
        selected_player, selected_root = selected
        roots = tuple(dict.fromkeys(root for _, root in valid_roots))
        return Snapshot(manager, roots, selected_root, session, selected_player, local_player)

    def confirm(self, snapshot):
        if self.resolve(snapshot.requested_player) != snapshot:
            raise MemoryUnavailable("Player context changed during poll")


@dataclass(frozen=True)
class Snapshot:
    manager: int
    roots: tuple[int, ...]
    root: int
    session: int | None
    local_player: int
    requested_player: int
