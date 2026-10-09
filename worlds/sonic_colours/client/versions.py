import hashlib
from datetime import datetime, timezone
from ..world_constants import load_data

VERSION = load_data('versions.json')


def verify_revision(memory):
    disc = memory.read_bytes(0x80000000, 6)
    # DME can briefly return a zero-filled header during a coherent PAL run.
    # Bound retries; never reuse a previous executable identity for writes.
    for _ in range(2):
        if disc != b'\0' * 6:
            break
        disc = memory.read_bytes(0x80000000, 6)
    revision = memory.read_u8(0x80000007)
    memory.revision_observation = {'time_utc': datetime.now(timezone.utc).isoformat(),
                                   'disc_id': disc.decode('ascii', errors='backslashreplace'),
                                   'disc_id_hex': disc.hex(), 'revision': revision, 'verified': False}
    if disc != VERSION['disc_id'].encode('ascii'):
        raise memory.error(f'wrong_game: observed {disc!r} (hex={disc.hex()}), expected PAL SNCP8P')
    if revision != VERSION['revision']:
        raise memory.error(f'unknown_revision: observed disc revision {revision}, expected {VERSION["revision"]}')
    for section in VERSION['text_sections']:
        data = memory.read_bytes(section['address'], section['size'])
        from .capsule_refresh import HOOK, ORIGINAL, installed
        if section['address'] <= HOOK < section['address'] + section['size']:
            offset = HOOK - section['address']
            instruction = int.from_bytes(data[offset:offset + 4], 'big')
            memory.revision_observation['capsule_hook_instruction'] = f'0x{instruction:08X}'
            if instruction != ORIGINAL and installed(memory):
                data = data[:offset] + ORIGINAL.to_bytes(4, 'big') + data[offset + 4:]
        from .progression_hook import HOOK as PROGRESSION_HOOK, ORIGINAL as PROGRESSION_ORIGINAL, installed_data
        if section['address'] <= PROGRESSION_HOOK < section['address'] + section['size']:
            offset = PROGRESSION_HOOK - section['address']
            word = int.from_bytes(data[offset:offset+4], 'big')
            if word != PROGRESSION_ORIGINAL and installed_data(memory) is not None:
                data = data[:offset] + PROGRESSION_ORIGINAL.to_bytes(4,'big') + data[offset+4:]
        digest = hashlib.sha256(data).hexdigest()
        if digest != section['sha256']:
            raise memory.error(f'unknown_revision: text at 0x{section["address"]:08X}, '
                               f'observed SHA256 {digest}, expected {section["sha256"]}')
    memory.revision_observation.update(verified=True, dol_sha256=VERSION['dol_sha256'])
    return VERSION['dol_sha256']
