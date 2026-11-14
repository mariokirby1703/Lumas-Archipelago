"""Pinned booth navigation compatibility, separate from world discovery flags."""
import struct

LEGACY_SELECTION_RVA = 0x26E067
LEGACY_SELECTION_ORIGINAL = bytes.fromhex('45 85 f6')
LEGACY_SELECTION_PATCHED = bytes.fromhex('41 09 de')


def _navigation_patch(rva, owned_register, original):
    # The input collection model is int16 [rcx+rax]. Both original blocks
    # discard volatile rcx/rdx/rax immediately afterwards. Keep the result in
    # the original nonvolatile register (esi, then ebx) and preserve all others.
    load,combine = ('b4','ce') if owned_register=='esi' else ('9c','cb')
    patched=(bytes.fromhex('0f bf 14 01 48 8b 05')+
             struct.pack('<i',0x1c7cbb8-(rva+11))+
             bytes.fromhex(f'0f b6 {load} 10 80 00 00 00 89 d1 c1 ea 05 8b 14 90 '
                           f'0f a3 ca 0f 92 c1 0f b6 c9 09 {combine} 90 90'))
    return rva,bytes.fromhex(original),patched


NAVIGATION_PATCHES = (
    _navigation_patch(0x267fb4,'esi','0f bf 14 01 8b ca 83 e1 1f be 01 00 00 00 d3 e6 8b c2 99 83 e2 1f 03 c2 c1 f8 05 48 63 c8 48 8b 05 df 4b a1 01 23 34 88'),
    _navigation_patch(0x268202,'ebx','0f bf 14 01 8b ca 83 e1 1f bb 01 00 00 00 d3 e3 8b c2 99 83 e2 1f 03 c2 c1 f8 05 48 63 c8 48 8b 05 91 49 a1 01 23 1c 88'),
)


def ownership_selection_supported(read, base):
    ready=True
    for rva,original,patched in NAVIGATION_PATCHES:
        code=read(base+rva,len(original))
        if code not in (original,patched):raise RuntimeError('Unexpected native booth navigation code')
        ready &= code==patched
    legacy=read(base+LEGACY_SELECTION_RVA,3)
    if legacy not in (LEGACY_SELECTION_ORIGINAL,LEGACY_SELECTION_PATCHED):
        raise RuntimeError('Unexpected native booth selection code')
    return bool(ready and legacy==LEGACY_SELECTION_ORIGINAL)


def model_delivery_ready(row, selection_supported):
    return bool(row.get('owned_byte') and (row.get('found_bit') or selection_supported))
