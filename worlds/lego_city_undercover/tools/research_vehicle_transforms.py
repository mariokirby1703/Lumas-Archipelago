"""Index actual vehicle RTTI/vtables and scripted rail movement; never execute game code."""
import hashlib
import json
from pathlib import Path
import re
import struct
import pefile

WORLD = Path(__file__).resolve().parents[1]


def main():
    raw = (WORLD/'notes/gamefiles/LEGOLCUR_DX11.exe').read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != '624fed07274bbd105d1d571ecb97a290df6f6f0aff76898c516890da6d136f76':
        raise ValueError('Unknown executable')
    pe = pefile.PE(data=raw)
    image = pe.get_memory_mapped_image()
    base = pe.OPTIONAL_HEADER.ImageBase
    tables = []
    # Search actual immutable table entries, then validate MSVC x64 RTTI.
    for getter in (0x506fe0, 0x4a9370):
        for match in re.finditer(re.escape(struct.pack('<Q',base+getter)),image):
            table = match.start()-0xf0
            try:
                col = struct.unpack_from('<Q',image,table-8)[0]-base
                if not 0 <= col < len(image)-24:
                    continue
                signature,offset,_,descriptor,_,self_rva=struct.unpack_from('<6I',image,col)
                if signature != 1 or self_rva != col or offset != 0:
                    continue
                name = image[descriptor+16:descriptor+200].split(b'\0')[0].decode('ascii')
                if not name.startswith('.?AV'):
                    continue
                setter=struct.unpack_from('<Q',image,table+0xf8)[0]-base
                tables.append(dict(vtable_rva=hex(table),rtti=name,getter_rva=hex(getter),
                    setter_rva=hex(setter),getter_prefix=image[getter:getter+7].hex(),
                    actual_vehicle=name.startswith('.?AVApiVehicle'),
                    transform='vehicle+348 -> physics+60' if getter==0x4a9370 else 'placeable+50'))
            except (ValueError,struct.error,UnicodeError):
                continue
    scripts=[]
    root=WORLD/'notes/extracted/GAME4/jobs/scripts/city_setup/general'
    for folder in ('sf_trams','train_setup'):
        for path in sorted((root/folder).glob('*.sf')):
            text=path.read_text(encoding='utf-8-sig')
            evidence=[dict(line=i,text=line.strip()) for i,line in enumerate(text.splitlines(),1)
                      if any(word in line for word in ('AttachToSpline','DisableManualAIControl','Teleport(',
                          'GetOccupant','GetDriver','SetLinearVelocity','SetAngularVelocity'))]
            if evidence:
                scripts.append(dict(source=path.relative_to(WORLD/'notes/extracted').as_posix(),
                    sha256=hashlib.sha256(path.read_bytes()).hexdigest(),evidence=evidence))
    report=dict(version=1,exe_sha256=digest,vtables=tables,rail_scripts=scripts,
        limitation='RTTI proves shared getter/setter dispatch, not physics or rail rollback correctness in gameplay')
    out=WORLD/'docs/research/vehicle_transform_inventory.json'
    out.write_text(json.dumps(report,indent=2),encoding='utf-8')
    # Package only reviewed metadata; no executable bytes except bounded signatures.
    manifest={row['vtable_rva']:dict(native_class=row['rtti'][4:-2],getter_rva=row['getter_rva'],
                 setter_rva=row['setter_rva']) for row in tables if row['actual_vehicle']}
    (WORLD/'bridge/vehicle_types.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(f'{len(manifest)} actual vehicle classes; {len(scripts)} rail scripts; {out}')


if __name__=='__main__':
    main()
