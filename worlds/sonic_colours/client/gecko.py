"""Exact Gecko C2 payload verification; no arbitrary executable normalization."""
import struct
from .memory import MemoryUnavailable, valid_range


def branch_target(address, word):
    if word & 0xfc000003 != 0x48000000:
        return None
    delta=word & 0x03fffffc
    if delta & 0x02000000:delta-=0x04000000
    return address+delta


def inspect_c2(memory, hook, original, variants, mutable=(), label='capsule'):
    word=memory.read_u32(hook)
    if word==original:return {'installed':False,'variant':'original PAL'}
    target=branch_target(hook,word)
    if target is None or not valid_range(target,4):
        raise MemoryUnavailable(f'unknown_revision: invalid C2 branch at 0x{hook:08X}, observed 0x{word:08X}')
    failures=[]
    header=memory.read_bytes(target-8,8) if valid_range(target-8,8) else bytes(8)
    header_code,header_lines=struct.unpack('>2I',header)
    actual_length=header_lines*8 if header_code==0xc2000000 | (hook-0x80000000) and 0<header_lines<=1024 else None
    for name,words in variants.items():
        size=len(words)*4
        if not valid_range(target,size):continue
        raw=bytearray(memory.read_bytes(target,size));expected=struct.pack('>'+'I'*(len(words)-1),*words[:-1])
        for start,length in mutable:
            raw[start:start+length]=bytes(length)
        back=int.from_bytes(raw[-4:],'big');return_target=branch_target(target+size-4,back)
        mismatch=next((i for i in range(len(words)-1) if raw[i*4:i*4+4]!=expected[i*4:i*4+4]),None)
        if mismatch is None and return_target==hook+4 and (actual_length is None or actual_length==size):
            return {'installed':True,'variant':name,'hook':hook,'target':target,'payload_length':size,
                    'actual_header_length':actual_length,'return_instruction':back,'return_target':return_target}
        failures.append({'variant':name,'expected_length':size,'first_differing_word':mismatch,
                         'expected_word':words[mismatch] if mismatch is not None else None,
                         'actual_word':int.from_bytes(raw[mismatch*4:mismatch*4+4],'big') if mismatch is not None else None,
                         'return_instruction':back,'computed_return':return_target})
    import json
    raise MemoryUnavailable(f'unknown_revision: unrecognized {label} thunk or return; '+json.dumps(
        {'hook':hex(hook),'target':hex(target),'actual_header_length':actual_length,'expected_return':hex(hook+4),
         'comparisons':failures},sort_keys=True))
