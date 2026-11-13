"""Export all registered model/context names using verified read-only layouts."""
import csv
from pathlib import Path
import struct
import sys

WORLD=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(WORLD/'bridge'))
from live_monitor import Session
from inventory_reader import pointer,cstring


def main():
    session=Session()
    try:
        read,base=session.read,session.base
        manager=pointer(read,base+0x17EC090)
        count=struct.unpack('<I',read(manager+0x8F0,4))[0]
        if count>256:raise ValueError('Invalid context count')
        contexts=[]
        for index in range(count):
            definition=pointer(read,manager+0xF0+index*8)
            contexts.append(dict(index=index,name=cstring(read,pointer(read,definition+8))))
        manager=pointer(read,base+0x17EBD38)
        count=struct.unpack('<I',read(manager+0xE0,4))[0]
        if count>1024:raise ValueError('Invalid model count')
        table=pointer(read,manager+0x118);models=[]
        for index in range(count):
            definition=pointer(read,table+index*8)
            if not definition:continue
            models.append(dict(model_id=index,internal_name=cstring(read,pointer(read,definition+0x30))))
        for filename,rows in (('runtime_contexts.csv',contexts),('runtime_models.csv',models)):
            with (WORLD/'notes/analysis'/filename).open('w',newline='',encoding='utf-8') as f:
                writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
        print(f'{len(contexts)} contexts; {len(models)} models; no inferred pickup coordinates')
    finally:session.close()


if __name__=='__main__':main()
