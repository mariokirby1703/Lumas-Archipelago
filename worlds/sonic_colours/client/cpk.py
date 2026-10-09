"""Read and copy-patch player-owned CRI archives without loading a CPK into RAM."""
from pathlib import Path
import hashlib
import os
import shutil
import struct
import tempfile


def decompress(data):
    if data[:8] != b'CRILAYLA':
        return data
    size, header_offset = struct.unpack_from('<II', data, 8)
    if size > 64 * 1024 * 1024 or header_offset + 0x110 > len(data):
        raise ValueError('invalid CRILAYLA size/header')
    output = bytearray(size + 0x100)
    output[:0x100] = data[header_offset + 0x10:header_offset + 0x110]
    cursor, buffered, available = header_offset + 0xf, 0, 0

    def bits(count):
        nonlocal cursor, buffered, available
        value = 0
        for _ in range(count):
            if not available:
                if cursor < 0x10:
                    raise ValueError('truncated CRILAYLA bitstream')
                buffered, available = data[cursor], 8
                cursor -= 1
            available -= 1
            value = (value << 1) | ((buffered >> available) & 1)
        return value

    position = len(output) - 1
    while position >= 0x100:
        if not bits(1):
            output[position] = bits(8)
            position -= 1
            continue
        distance, length = bits(13) + 3, 3
        for width in (2, 3, 5, 8):
            value = bits(width)
            length += value
            if value != (1 << width) - 1:
                break
        else:
            while True:
                value = bits(8)
                length += value
                if value != 255:
                    break
        if position - length < 0xff or position + distance >= len(output):
            raise ValueError('invalid CRILAYLA backreference')
        for _ in range(length):
            output[position] = output[position + distance]
            position -= 1
    return bytes(output)


class UTF:
    FORMATS = {0: '>B', 1: '>b', 2: '>H', 3: '>h', 4: '>I', 5: '>i',
               6: '>Q', 7: '>q', 8: '>f', 10: '>I', 11: '>II'}

    def __init__(self, data):
        self.data = data
        if len(data) < 32 or data[:4] != b'@UTF':
            raise ValueError('encrypted or unsupported UTF table')
        size, rows, strings, binary, name, columns, stride, count = struct.unpack_from('>5I2HI', data, 4)
        if (size + 8 > len(data) or columns > 256 or count > 100000 or stride > 4096 or
                not 32 <= rows + 8 <= strings + 8 <= binary + 8 <= size + 8 or
                rows + 8 + stride * count > strings + 8):
            raise ValueError('UTF table bounds invalid')
        self.strings = strings + 8
        self.binary = binary + 8
        self.rows, self.cells = [], []
        cursor = 32
        definitions = []
        for _ in range(columns):
            flags, key = struct.unpack_from('>BI', data, cursor)
            cursor += 5
            kind, storage = flags & 15, flags & 0xf0
            if kind not in self.FORMATS or storage not in (0x10, 0x30, 0x50):
                raise ValueError('unsupported UTF column type')
            constant = cursor if storage == 0x30 else None
            if constant is not None:
                cursor += struct.calcsize(self.FORMATS[kind])
            definitions.append((self.string(key), kind, storage, constant))
        for index in range(count):
            cursor = rows + 8 + index * stride
            row, cells = {}, {}
            for key, kind, storage, constant in definitions:
                position = constant if storage == 0x30 else cursor if storage == 0x50 else None
                fmt = self.FORMATS[kind]
                raw = struct.unpack_from(fmt, data, position) if position is not None else (0,)
                value = raw[0] if len(raw) == 1 else raw
                row[key] = self.string(value) if kind == 10 else value
                cells[key] = (position, fmt)
                if storage == 0x50:
                    cursor += struct.calcsize(fmt)
            self.rows.append(row)
            self.cells.append(cells)

    def string(self, offset):
        start = self.strings + offset
        if not self.strings <= start < self.binary:
            raise ValueError('UTF string offset invalid')
        return self.data[start:self.data.index(0, start, self.binary)].decode('utf-8')


class CPK:
    def __init__(self, path):
        self.path = Path(path)
        self.header = self.table(0, b'CPK ')
        self.toc_offset = self.header.rows[0]['TocOffset']
        self.toc = self.table(self.toc_offset, b'TOC ')
        self.content_base = min(self.toc_offset, self.header.rows[0]['ContentOffset'])

    def table(self, offset, magic):
        with self.path.open('rb') as stream:
            stream.seek(offset)
            packet = stream.read(16)
            if packet[:4] != magic:
                raise ValueError('CPK packet signature mismatch')
            size = int.from_bytes(packet[8:16], 'little')
            if not 0 < size < 16 * 1024 * 1024:
                raise ValueError('CPK table size out of range')
            return UTF(stream.read(size))

    def read(self, row):
        size = row['FileSize']
        if not 0 < size <= 64 * 1024 * 1024:
            raise ValueError('CPK member size out of range')
        with self.path.open('rb') as stream:
            stream.seek(self.content_base + row['FileOffset'])
            data = stream.read(size)
        if len(data) != size:
            raise ValueError('truncated CPK member')
        data = decompress(data)
        if len(data) != row['ExtractSize']:
            raise ValueError('CPK extracted size mismatch')
        return data

    def replace_member(self, output, index, replacement, expected_sha256):
        """Publish a separate owned-data archive; preserve the original.

        The PAL archive has no TOC CRC, and group tables reference TOC indices,
        not file offsets. Append a raw, aligned member and update its TOC row.
        Existing files and duplicate resource entries retain their offsets.
        """
        output = Path(output)
        if output.resolve() == self.path.resolve() or output.exists():
            raise ValueError('output must be a new file, distinct from original CPK')
        with self.path.open('rb') as source:
            digest = hashlib.file_digest(source, 'sha256').hexdigest()
        if digest != expected_sha256:
            raise ValueError('original PAL CPK SHA256 mismatch')
        if self.header.rows[0]['TocCrc'] or self.header.rows[0].get('GtocCrc', 0):
            raise ValueError('archive CRC layout unsupported')
        old = self.toc.rows[index]
        alignment = self.header.rows[0]['Align']
        if alignment != 2048 or not 0 < len(replacement) < 64 * 1024 * 1024:
            raise ValueError('unsupported alignment or replacement size')
        append = (self.path.stat().st_size + alignment - 1) // alignment * alignment
        header, toc = bytearray(self.header.data), bytearray(self.toc.data)
        for key, value in [('FileOffset', append - self.content_base),
                           ('FileSize', len(replacement)), ('ExtractSize', len(replacement))]:
            position, fmt = self.toc.cells[index][key]
            if position is None:
                raise ValueError('CPK member field is not writable')
            struct.pack_into(fmt, toc, position, value)
        values = {'ContentSize': append + len(replacement) - self.header.rows[0]['ContentOffset'],
                  'EnabledPackedSize': self.header.rows[0]['EnabledPackedSize'] + len(replacement) - old['FileSize'],
                  'EnabledDataSize': self.header.rows[0]['EnabledDataSize'] + len(replacement) - old['ExtractSize']}
        for key, value in values.items():
            position, fmt = self.header.cells[0][key]
            if position is None:
                raise ValueError('CPK header field is not writable')
            struct.pack_into(fmt, header, position, value)
        output.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix='.sonic-cpk-', dir=output.parent)
        try:
            with os.fdopen(descriptor, 'w+b') as stream, self.path.open('rb') as original:
                shutil.copyfileobj(original, stream, 1024 * 1024)
                stream.seek(append)
                stream.write(replacement)
                stream.seek(16)
                stream.write(header)
                stream.seek(self.toc_offset + 16)
                stream.write(toc)
                stream.flush()
                os.fsync(stream.fileno())
            verify = CPK(temporary)
            if verify.read(verify.toc.rows[index]) != replacement:
                raise ValueError('patched CPK readback mismatch')
            # Atomic no-overwrite publication on both Windows and POSIX.
            os.link(temporary, output)
        finally:
            os.unlink(temporary)
