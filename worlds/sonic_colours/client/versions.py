import hashlib
from datetime import datetime, timezone
from ..world_constants import load_data

VERSION = load_data('versions.json')


def verify_revision(memory):
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
        digest = hashlib.sha256(memory.read_bytes(section['address'], section['size'])).hexdigest()
        if digest != section['sha256']:
            raise memory.error(f'unknown_revision: text at 0x{section["address"]:08X}, '
                               f'observed SHA256 {digest}, expected {section["sha256"]}')
    memory.revision_observation.update(verified=True, dol_sha256=VERSION['dol_sha256'])
    return VERSION['dol_sha256']
