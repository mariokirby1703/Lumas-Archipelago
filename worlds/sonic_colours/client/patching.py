"""Code patches require an explicit verified cache-coherency executor.

This module intentionally offers no raw PPC injection API or default executor.
"""
from .memory import MemoryUnavailable


class PatchManager:
    def __init__(self, executor=None):
        self.executor = executor
        self.installed = {}

    def install(self, memory, address, original, replacement):
        if self.executor is None:
            raise MemoryUnavailable('WRITE_BLOCKED: PPC I-cache/Dolphin JIT invalidation unverified')
        if address % 4 or len(original) % 4 or len(original) != len(replacement):
            raise ValueError('invalid PPC patch alignment/length')
        if address in self.installed:
            raise ValueError('patch already installed')
        if memory.read_bytes(address, len(original)) != original:
            raise MemoryUnavailable('WRITE_BLOCKED: original instruction mismatch')
        self.installed[address] = (original, replacement)
        self.executor(memory, address, original, replacement)

    def restore(self, memory, address):
        original, replacement = self.installed[address]
        self.executor(memory, address, replacement, original)
        del self.installed[address]

    def restore_all(self, memory):
        for address in list(self.installed):
            self.restore(memory, address)
