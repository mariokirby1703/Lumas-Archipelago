"""BE guest access. Typed writes always compare, gate, write, and verify.

An external process cannot perform atomic Wii RMW. A racing update blocks the
operation; multi-write transactions cannot guarantee rollback across scene exits.
"""
import os
import struct
from datetime import datetime, timezone
from typing import Protocol


class MemoryUnavailable(RuntimeError):
    pass


class MemoryBackend(Protocol):
    def read_bytes(self, address: int, size: int) -> bytes: ...
    def write_bytes(self, address: int, data: bytes) -> None: ...


def valid_range(address, size=4):
    return (type(address) is int and type(size) is int and size > 0 and any(
        start <= address < address + size <= end for start, end in
        ((0x80000000, 0x81800000), (0x90000000, 0x94000000))))


class DMEBackend:
    def __init__(self, engine):
        self.engine = engine
        self.fallback = None

    def active(self):
        return self.engine.is_hooked() and getattr(self.engine.get_status(), 'name', None) == 'hooked'

    def instance_info(self):
        status = self.engine.get_status()
        result = {'dme_status': getattr(status, 'name', str(status)), 'emulation_active': self.active(),
                  'selected_pid': self.fallback.pid if self.fallback else None,
                  'pid_attribution': 'verified MEM2 alias' if self.fallback else 'DME does not expose selected PID'}
        if os.name == 'nt':
            from .mem2_windows import dolphin_processes
            try:
                result['process_candidates'] = dolphin_processes()
            except OSError as error:
                result['process_enumeration_error'] = str(error)
        return result

    def _check(self):
        if not self.active():
            self.close()
            raise MemoryUnavailable('emulation_not_running')

    def assert_instance(self, info=None):
        info = self.instance_info() if info is None else info
        if info.get('process_enumeration_error'):
            raise MemoryUnavailable('dolphin_instance_unverified: process enumeration failed')
        if 'process_candidates' in info and len(info['process_candidates']) != 1:
            raise MemoryUnavailable('dolphin_instance_unverified: exactly one Dolphin process is required; DME cannot select an explicit PID')

    def _fallback(self):
        if os.name != 'nt':
            raise MemoryUnavailable('MEM2 unavailable in DME')
        if self.fallback is None:
            from .mem2_windows import WindowsMEM2
            self.fallback = WindowsMEM2(self.engine)
        return self.fallback

    def read_bytes(self, address, size):
        self._check()
        try:
            return bytes(self.engine.read_bytes(address, size))
        except (RuntimeError, OSError):
            if address < 0x90000000:
                raise
            return self._fallback().read(address, size)

    def write_bytes(self, address, data):
        self._check()
        # Repeat process attribution at the mutation boundary, not just when
        # attaching. No automatic selection between concurrently running games.
        self.assert_instance()
        # Choose one backend BEFORE mutation. A failed write may have partially
        # applied; retrying through another alias would conceal uncertainty.
        if address >= 0x90000000 and self.fallback:
            self.fallback.write(address, data)
        else:
            self.engine.write_bytes(address, data)

    def close(self):
        if self.fallback:
            self.fallback.close()
            self.fallback = None


class SonicMemory:
    error = MemoryUnavailable

    def __init__(self, backend, write_guard=None):
        self.backend = backend
        self.write_guard = write_guard
        self.latest_read = None
        self.latest_write = None
        self.revision_observation = None

    def read_bytes(self, address, size):
        if not valid_range(address, size):
            raise MemoryUnavailable('invalid_memory_range')
        try:
            data = self.backend.read_bytes(address, size)
        except (RuntimeError, OSError, ValueError) as error:
            raise MemoryUnavailable(f'read_failed: {error}') from error
        if len(data) != size:
            raise MemoryUnavailable('partial_read')
        self.latest_read = {'time_utc': datetime.now(timezone.utc).isoformat(),
                            'address': f'0x{address:08X}', 'size': size}
        return bytes(data)

    def try_read_bytes(self, address, size):
        try:
            return self.read_bytes(address, size)
        except MemoryUnavailable:
            return None

    def read_u8(self, address): return self.read_bytes(address, 1)[0]
    def read_u16(self, address): return int.from_bytes(self.read_bytes(address, 2), 'big')
    def read_u32(self, address): return int.from_bytes(self.read_bytes(address, 4), 'big')
    def read_s32(self, address): return int.from_bytes(self.read_bytes(address, 4), 'big', signed=True)
    def read_f32(self, address): return struct.unpack('>f', self.read_bytes(address, 4))[0]

    def read_ptr_checked(self, address, size=4):
        pointer = self.read_u32(address)
        if pointer % 4 or not valid_range(pointer, size):
            raise MemoryUnavailable('invalid_pointer')
        return pointer

    def write_bytes_verified(self, address, data, *, expected, operation):
        if not valid_range(address, len(data)) or len(expected) != len(data):
            raise MemoryUnavailable('invalid_write_range')
        if self.write_guard is None:
            raise MemoryUnavailable('WRITE_BLOCKED: no verified write policy')
        if operation == 'map_availability' and (data != (2).to_bytes(4, 'big') or expected != (1).to_bytes(4, 'big')):
            raise MemoryUnavailable('WRITE_BLOCKED: map availability only permits locked-to-available')
        if operation == 'progression_reset' and data != bytes(4):
            raise MemoryUnavailable('WRITE_BLOCKED: disabled progression events may only reset to zero')
        if operation == 'map_lock' and (data != (1).to_bytes(4,'big') or int.from_bytes(expected,'big') not in (2,3,4)):
            raise MemoryUnavailable('WRITE_BLOCKED: map lock only permits available/entered/cleared-to-locked cache')
        token = self.write_guard(operation, address, len(data))
        if operation == 'global_map_refresh':
            _, request, actors, chain = token
            value = int.from_bytes(data, 'big')
            offset = address-request
            valid = (len(data)==4 and ((offset==0 and value in (0,actors[0]))
                     or (offset==4 and value in range(1,7))
                     or (offset==8 and value==chain[1]) or (offset==12 and value==chain[2])))
            if offset == 0 and value:
                zone = self.read_u32(request+4)
                valid = valid and zone in range(1,7) and self.read_progress_bit(chain[-1],20+zone)
                valid = valid and self.read_u32(request+8)==chain[1] and self.read_u32(request+12)==chain[2]
            if not valid:
                raise MemoryUnavailable('WRITE_BLOCKED: invalid or unauthorized Grand World Map request')
        before = self.read_bytes(address, len(data))
        if before != expected:
            raise MemoryUnavailable('WRITE_BLOCKED: compare_failed')
        if self.write_guard(operation, address, len(data)) != token:
            raise MemoryUnavailable('WRITE_BLOCKED: context_changed')
        if before == data:
            return
        try:
            self.backend.write_bytes(address, data)
        except (RuntimeError, OSError, ValueError) as error:
            raise MemoryUnavailable(f'WRITE_UNCERTAIN: {error}') from error
        readback = self.read_bytes(address, len(data))
        # This exact native mailbox is consumed asynchronously by the map's
        # update hook. A cleared request plus the released target lock is its
        # completion acknowledgement, not a failed ordinary-memory write.
        consumed = (operation == 'global_map_refresh' and offset == 0 and value
                    and readback == bytes(4)
                    and self.read_u32(actors[0]+0xb4+zone*8) == 0)
        if readback != data and not consumed:
            raise MemoryUnavailable('WRITE_UNCERTAIN: readback_mismatch')
        try:
            final_token = self.write_guard(operation, address, len(data))
        except MemoryUnavailable as error:
            raise MemoryUnavailable(f'WRITE_UNCERTAIN: context_revalidation_after_write: {error}') from error
        if final_token != token:
            raise MemoryUnavailable('WRITE_UNCERTAIN: context_changed_after_write')
        self.latest_write = {'time_utc': datetime.now(timezone.utc).isoformat(),
                             'address': f'0x{address:08X}', 'size': len(data), 'operation': operation,
                             'readback_verified': True}

    def write_u8(self, address, value, *, expected, operation):
        self.write_bytes_verified(address, bytes([value]), expected=bytes([expected]), operation=operation)

    def write_u16(self, address, value, *, expected, operation):
        self.write_bytes_verified(address, value.to_bytes(2, 'big'), expected=expected.to_bytes(2, 'big'), operation=operation)

    def write_u32(self, address, value, *, expected, operation):
        self.write_bytes_verified(address, value.to_bytes(4, 'big'), expected=expected.to_bytes(4, 'big'), operation=operation)

    def write_f32(self, address, value, *, expected, operation):
        self.write_bytes_verified(address, struct.pack('>f', value), expected=struct.pack('>f', expected), operation=operation)

    def read_modify_write_masked_u32(self, address, mask, value, *, operation):
        if address % 4 or not 0 <= mask <= 0xffffffff or value & ~mask:
            raise MemoryUnavailable('invalid_mask_or_alignment')
        old = self.read_u32(address)
        self.write_u32(address, (old & ~mask) | value, expected=old, operation=operation)

    def resolve_save_container(self):
        from .versions import VERSION
        manager = self.read_ptr_checked(VERSION['manager_global_candidate'], 0x34)
        container = self.read_ptr_checked(manager + 0x30, 8)
        return manager, container

    def resolve_selected_slot(self, *, allow_working=False):
        manager, container = self.resolve_save_container()
        index = self.read_u8(container)
        # 8015F9A4 initializes six records; 8015FA18 addresses the selected
        # record with this exact stride. Index 3 is a native working record,
        # never a fourth UI slot. Only read accessors may inspect it.
        if index > (3 if allow_working else 2):
            raise MemoryUnavailable('unknown_selected_slot')
        selected = container + 8 + index * 0x19608
        if not valid_range(selected, 0x19608):
            raise MemoryUnavailable('invalid_save_range')
        return manager, container, index, selected

    def resolve_flags_ptr(self, *, allow_working=False):
        chain = self.resolve_selected_slot(allow_working=allow_working)
        # 8015f940: lwz r3,0(r3); addi r3,r3,0x1c. The lwz unwraps
        # the stack-local selected-save wrapper, not a pointer at save+0x1c.
        return chain + (chain[-1] + 0x1c,)

    def trace_save_chain(self):
        """Bounded candidate reads with the first failing step preserved."""
        from .versions import VERSION
        report = {'grade': 'code-derived', 'steps': [], 'chain': None,
                  'scene': 'unresolved', 'no_save_yet': 'possible; requires independent scene evidence'}

        def read(step, address, size=4, pointer_size=None):
            entry = {'step': step, 'address': f'0x{address:08X}'}
            report['steps'].append(entry)
            try:
                value = int.from_bytes(self.read_bytes(address, size), 'big')
            except MemoryUnavailable as error:
                entry.update(reason='short_read' if 'partial_read' in str(error) else 'read_failed', detail=str(error))
                raise
            entry['raw'] = f'0x{value:0{size * 2}X}'
            if pointer_size is not None:
                reason = ('zero' if value == 0 else 'alignment' if value % 4 else
                          'outside_MEM1_MEM2' if not valid_range(value, pointer_size) else None)
                if reason:
                    entry['reason'] = reason
                    raise MemoryUnavailable(reason)
            entry['reason'] = 'ok'
            return value

        try:
            manager = read('manager', VERSION['manager_global_candidate'], pointer_size=0x34)
            container = read('container', manager + 0x30, pointer_size=8)
            index = read('selected_index', container, 1)
            if index > 3:
                report['steps'][-1]['reason'] = 'index_out_of_range'
                raise MemoryUnavailable('index_out_of_range')
            selected = container + 8 + index * 0x19608
            if not valid_range(selected, 0x19608):
                report['steps'].append({'step': 'selected_save', 'address': f'0x{selected:08X}',
                                        'reason': 'outside_MEM1_MEM2'})
                raise MemoryUnavailable('outside_MEM1_MEM2')
            flags = selected + 0x1c
            entry = {'step': 'c_bank', 'address': f'0x{flags + 0x10:08X}'}
            report['steps'].append(entry)
            try:
                bank = self.read_bytes(flags + 0x10, 40)
            except MemoryUnavailable as error:
                entry.update(reason='short_read' if 'partial_read' in str(error) else 'read_failed', detail=str(error))
                raise
            entry.update(reason='ok', hex=bank.hex())
            chain = (manager, container, index, selected, flags)
            if self.resolve_flags_ptr(allow_working=True) != chain:
                report['steps'].append({'step': 'context_recheck', 'reason': 'context_changed'})
                raise MemoryUnavailable('context_changed')
            report['chain'] = chain
            report['status'] = 'candidate_only'
        except MemoryUnavailable as error:
            report['status'] = str(error)
            report['first_failure'] = next((s for s in report['steps'] if s['reason'] != 'ok'),
                                           {'step': 'c_bank_or_context', 'reason': str(error)})
        return report

    def read_progress_bit(self, flags, bit):
        if not 0 <= bit <= 302:
            raise MemoryUnavailable('invalid_progress_bit')
        return bool(self.read_u32(flags + 0x10 + (bit // 32) * 4) & (1 << (bit % 32)))

    def write_progress_bit(self, flags, bit, enabled):
        if not 0 <= bit <= 302:
            raise MemoryUnavailable('invalid_progress_bit')
        mask = 1 << (bit % 32)
        self.read_modify_write_masked_u32(flags + 0x10 + (bit // 32) * 4,
                                        mask, mask if enabled else 0, operation='progress_c')

    def verify_revision(self):
        from .versions import verify_revision
        return verify_revision(self)
