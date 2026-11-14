"""Recognize only the reviewed native entry or its absolute jump encoding."""
import ntpath
import struct

DETECTIVE_ORIGINAL=bytes.fromhex('40574883ec5048c7442420feffffff')


def detective_owner(prefix,modules):
    if prefix==DETECTIVE_ORIGINAL:return dict(status='vanilla')
    if len(prefix)!=15 or prefix[:6]!=bytes.fromhex('ff2500000000') or prefix[14]!=0x90:
        return dict(status='unknown_patch')
    target=struct.unpack_from('<Q',prefix,6)[0]
    matches=[m for m in modules if m['base']<=target<m['base']+m['size']]
    if len(matches)!=1:return dict(status='unknown_owner',target=hex(target))
    return dict(status='pinned_module',target=hex(target),path=matches[0]['path'])


def require_current_owner(observation,dll):
    status=observation.get('status')
    if status=='vanilla':return
    if status=='pinned_module' and ntpath.normcase(ntpath.abspath(observation['path']))==ntpath.normcase(ntpath.abspath(str(dll))):return
    raise RuntimeError('Detective Scan hook belongs to another or unknown bridge. Restart the game before using this DLL; no command was sent.')
