"""Category menu counts accept genuine discovery OR AP ownership."""
import struct
COUNTER_RVA=0x265489
COUNTER_ORIGINAL=bytes.fromhex('0f bf 04 0a 44 8b c0 99 83 e2 1f 41 83 e0 1f 03 c2 c1 f8 05 48 63 c8 41 8b 04 89 44 0f a3 c0')
# Keep the existing count increment at 0x2654aa. Only its UI eligibility changes.
COUNTER_PATCHED=(bytes.fromhex('0f bf 04 0a 41 80 bc 01 80 00 00 00 00 0f 85')+
                 struct.pack('<i',0x2654aa-(COUNTER_RVA+19))+
                 bytes.fromhex('41 0f a3 01')+b'\x90'*8)
LABEL_RVA=0x26f2c3
LABEL_ORIGINAL=bytes.fromhex('48 8b 05 86 09 5d 01')
LABEL_PATCHED=bytes.fromhex('48 8b 05 8e 09 5d 01')
CATEGORY_PATCHES=((COUNTER_RVA,COUNTER_ORIGINAL,COUNTER_PATCHED),
                  (LABEL_RVA,LABEL_ORIGINAL,LABEL_PATCHED))
assert len(COUNTER_ORIGINAL)==len(COUNTER_PATCHED)
