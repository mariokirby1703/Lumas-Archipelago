DISC_IDS = ('SNCP8P', 'SNCE8P')
DISC_BYTES = tuple(disc.encode('ascii') for disc in DISC_IDS)
REVISION = 0


def supported_header(header):
    return len(header) >= 8 and header[:6] in DISC_BYTES and header[7] == REVISION
