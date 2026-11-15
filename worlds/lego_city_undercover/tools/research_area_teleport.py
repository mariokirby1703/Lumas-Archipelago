"""Read-only PE references for real scripted teleport/vehicle APIs; never executes them."""
import bisect
import hashlib
import json
from pathlib import Path
import capstone
import pefile

WORLD=Path(__file__).resolve().parents[1]
EXE=WORLD/'notes/gamefiles/LEGOLCUR_DX11.exe'


def main():
    raw=EXE.read_bytes();digest=hashlib.sha256(raw).hexdigest()
    if digest!='624fed07274bbd105d1d571ecb97a290df6f6f0aff76898c516890da6d136f76':raise ValueError('Unknown EXE')
    pe=pefile.PE(data=raw);base=pe.OPTIONAL_HEADER.ImageBase;image=pe.get_memory_mapped_image()
    words=(b'Teleport',b'GetVehicle',b'ClearVehicle',b'SetPosition',b'SetTransform',b'SetVelocity')
    strings={}
    import re
    for m in re.finditer(rb'[ -~]{4,}\x00',image):
        if any(word.lower() in m[0].lower() for word in words):strings[base+m.start()]=m[0][:-1].decode('ascii')
    functions=sorted((e.struct.BeginAddress,e.struct.EndAddress) for e in pe.DIRECTORY_ENTRY_EXCEPTION)
    starts=[x[0] for x in functions]
    md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64);md.detail=True;md.skipdata=True;refs=[]
    for section in pe.sections:
        if not section.Characteristics&0x20000000:continue
        for i in md.disasm(section.get_data(),base+section.VirtualAddress):
            if not i.id:continue
            for op in i.operands:
                target=i.address+i.size+op.mem.disp if op.type==capstone.CS_OP_MEM and op.mem.base==capstone.x86_const.X86_REG_RIP else None
                if target in strings:
                    rva=i.address-base;idx=bisect.bisect_right(starts,rva)-1
                    function=functions[idx][0] if idx>=0 and rva<functions[idx][1] else None
                    refs.append(dict(string=strings[target],string_rva=hex(target-base),reference_rva=hex(rva),function_rva=hex(function) if function else None))
    out=WORLD.parents[1]/'build/lego_city_undercover/next_pass/teleport_references.json'
    out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(dict(exe_sha256=digest,references=refs),indent=2),encoding='utf-8')
    print(json.dumps(refs,indent=2))


if __name__=='__main__':main()
