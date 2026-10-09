import hashlib
from ..world_constants import load_data

VERSION = load_data('versions.json')


def verify_revision(memory):
    if memory.read_bytes(0x80000000, 6) != VERSION['disc_id'].encode('ascii'):
        raise memory.error('wrong_game: expected PAL SNCP8P')
    if memory.read_u8(0x80000007) != VERSION['revision']:
        raise memory.error('unknown_revision: disc revision byte')
    for section in VERSION['text_sections']:
        digest = hashlib.sha256(memory.read_bytes(section['address'], section['size'])).hexdigest()
        if digest != section['sha256']:
            raise memory.error('unknown_revision: executable text SHA256 mismatch')
    return VERSION['dol_sha256']
