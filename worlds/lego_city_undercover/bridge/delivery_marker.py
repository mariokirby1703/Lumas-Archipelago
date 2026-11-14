"""Receipt watermark in 22 unused owned-model bytes of the pinned 1002-model build.

Indices 1002..1023 are outside the loaded model table. The entire character bank
is serialized at save offset 0x14318 in the supported 2579512-byte HMGR save.
The marker and currency are changed on the same game thread before requesting
autosave. It is neither a discovery flag nor an AP location.
"""
import hashlib
import json
import struct

MODEL_COUNT=1002
MARKER_OFFSET=0x80+MODEL_COUNT
MARKER_SIZE=22
CHARACTER_SAVE_OFFSET=0x14318
NATIVE_SAVE_SIZE=2579512


def binding_token(binding):
    encoded=json.dumps(binding,sort_keys=True,separators=(',',':')).encode()
    return hashlib.sha256(encoded).digest()[:16]


def parse_marker(data):
    if len(data)!=MARKER_SIZE:raise ValueError('Incomplete delivery marker')
    if data==bytes(MARKER_SIZE):return None
    if data[:2]!=b'AP':raise ValueError('Reserved model bytes are already used')
    return dict(binding=data[2:18].hex(),next_index=struct.unpack_from('<I',data,18)[0])


def receipt_saved(data,token,index):
    marker=parse_marker(data)
    return bool(marker and marker['binding']==token.hex() and index<marker['next_index'])


def marker_from_save(data):
    if len(data)!=NATIVE_SAVE_SIZE or data[:8]!=b'HMGR\x01\0\0\0':
        raise ValueError('Unsupported native save layout')
    offset=CHARACTER_SAVE_OFFSET+MARKER_OFFSET
    return data[offset:offset+MARKER_SIZE]
