"""Bounded Nintendo TPL texture import, preserving existing texture indices.

Sonic's .tls files are TPL containers. Offsets are file-relative big endian;
image headers are 36 bytes, table entries contain image and palette offsets.
"""
import struct

MAGIC=0x0020af30
BLOCKS={0:(8,8,32),1:(8,4,32),2:(8,4,32),3:(4,4,32),4:(4,4,32),
        5:(4,4,32),6:(4,4,64),8:(8,8,32),9:(8,4,32),10:(4,4,32),14:(8,8,32)}


def u32(blob,offset):
    if offset<0 or offset+4>len(blob):raise ValueError('TPL offset outside file')
    return struct.unpack_from('>I',blob,offset)[0]


def textures(blob):
    if u32(blob,0)!=MAGIC:raise ValueError('unsupported TLS signature')
    count=u32(blob,4);table=u32(blob,8)
    if not 0<count<=256 or table<12 or table+8*count>len(blob):
        raise ValueError('invalid TLS texture table')
    result=[]
    for i in range(count):
        image=u32(blob,table+i*8);palette=u32(blob,table+i*8+4)
        if image<12 or image+36>len(blob):raise ValueError('invalid image header')
        height,width=struct.unpack_from('>HH',blob,image)
        fmt=u32(blob,image+4);data=u32(blob,image+8)
        if not width or not height or fmt not in BLOCKS:raise ValueError('unsupported texture format')
        # This importer accepts only the proven single-level resource variant.
        if blob[image+33: image+35]!=b'\0\0':raise ValueError('mipmapped TLS requires separate audit')
        bw,bh,block=BLOCKS[fmt]
        size=((width+bw-1)//bw)*((height+bh-1)//bh)*block
        if data%32 or data+size>len(blob):raise ValueError('invalid image data bounds/alignment')
        if palette:raise ValueError('paletted TLS requires separate audit')
        result.append({'header':image,'palette':palette,'data':data,'size':size,
                       'width':width,'height':height,'format':fmt})
    return result


def append_texture(destination,source,index):
    """Return a new container; original texture bytes and indices stay intact."""
    originals=textures(destination);imports=textures(source)
    if type(index) is not int or not 0<=index<len(imports):raise ValueError('invalid source index')
    chosen=imports[index];out=bytearray(destination)
    def append(blob,alignment):
        out.extend(b'\0'*((-len(out))%alignment));offset=len(out);out.extend(blob);return offset
    pixels=append(source[chosen['data']:chosen['data']+chosen['size']],32)
    header=bytearray(source[chosen['header']:chosen['header']+36])
    struct.pack_into('>I',header,8,pixels)
    image=append(header,4)
    entries=b''.join(struct.pack('>II',t['header'],t['palette']) for t in originals)
    table=append(entries+struct.pack('>II',image,0),4)
    struct.pack_into('>II',out,4,len(originals)+1,table)
    rebuilt=textures(out)
    for old,new in zip(originals,rebuilt):
        if old!=new:raise ValueError('original TLS entry changed')
    if out[pixels:pixels+chosen['size']]!=source[chosen['data']:chosen['data']+chosen['size']]:
        raise ValueError('atlas copy mismatch')
    return bytes(out)
