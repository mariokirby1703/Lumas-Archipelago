"""Index PE unwind function ranges and direct call edges; no code execution.

This is a navigation index, not a semantic decompilation. Indirect calls remain
unresolved and chained unwind fragments may represent parts of one function.
"""
import bisect
import json
from pathlib import Path
import struct

from capstone import Cs, CS_ARCH_X86, CS_MODE_64
from inspect_game import inspect_pe


def main():
    world=Path(__file__).resolve().parents[1]
    data=(world/'notes/gamefiles/LEGOLCUR_DX11.exe').read_bytes()
    pe=inspect_pe(data);base=int(pe['image_base'],16)
    text=next(s for s in pe['sections'] if s['name']=='.text')
    pdata=next(s for s in pe['sections'] if s['name']=='.pdata')
    decoder=Cs(CS_ARCH_X86,CS_MODE_64);decoder.skipdata=True
    functions=[]
    for offset in range(pdata['raw_offset'],pdata['raw_offset']+pdata['virtual_size'],12):
        start,end,unwind=struct.unpack_from('<III',data,offset)
        if not text['rva']<=start<end<=text['rva']+text['raw_size']:continue
        raw=text['raw_offset']+start-text['rva'];calls=[];indirect=[];instructions=0
        for insn in decoder.disasm(data[raw:raw+end-start],base+start):
            instructions+=1
            if insn.mnemonic=='call':
                if insn.op_str.startswith('0x'):calls.append(int(insn.op_str,16)-base)
                else:indirect.append(dict(at=insn.address-base,operand=insn.op_str))
        functions.append(dict(start=start,end=end,unwind=unwind,instructions=instructions,
                              direct_calls=sorted(set(calls)),indirect_calls=indirect))
    functions.sort(key=lambda r:r['start'])
    starts=[f['start'] for f in functions];reverse={}
    for f in functions:
        for target in f['direct_calls']:
            reverse.setdefault(str(target),[]).append(f['start'])
    report=dict(function_ranges=len(functions),decoded_instructions=sum(f['instructions'] for f in functions),
                direct_call_edges=sum(len(f['direct_calls']) for f in functions),
                functions=functions,callers=reverse,semantic_analysis_complete=False)
    (world/'notes/analysis/native_function_index.json').write_text(json.dumps(report),encoding='utf-8')
    print({k:v for k,v in report.items() if k not in ('functions','callers')})


if __name__=='__main__':main()
