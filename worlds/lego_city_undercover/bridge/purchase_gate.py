"""Self-contained x64 shop guards for the pinned Steam executable.

Generated blocks contain no calls or references to the temporary bridge DLL.
The game owns their allocation until process exit.
"""
import struct

MASK_OFFSET=0x380
SIGNATURE_OFFSET=0x360
SIGNATURE=b'LCUSHOP1'
SITES=((0x264e70,bytes.fromhex('40 55 56 57 48 83 ec 50'),0),
       (0x265b5c,bytes.fromhex('45 85 ed 0f 85 3c 03 00 00'),0x140),
       (0x266139,bytes.fromhex('44 8b cf 0f b7 d6'),0x240),
       (0x26210,bytes.fromhex('48 8b 05 b1 5d 7c 01'),0x500))

class Code:
    def __init__(self,address):self.address=address;self.data=bytearray();self.labels={};self.refs=[]
    def emit(self,data):self.data.extend(bytes.fromhex(data) if isinstance(data,str) else data)
    def label(self,name):self.labels[name]=len(self.data)
    def jump(self,opcode,target):
        self.emit(opcode);self.refs.append((len(self.data),target));self.emit(b'\0'*4)
    def absolute(self,address):self.emit('ff 25 00 00 00 00');self.emit(struct.pack('<Q',address))
    def mask(self,address):self.emit('49 bb');self.emit(struct.pack('<Q',address));self.emit('41 0f a3 03')
    def finish(self):
        for offset,target in self.refs:
            address=self.address+self.labels[target] if isinstance(target,str) else target
            struct.pack_into('<i',self.data,offset,address-(self.address+offset+4))
        return bytes(self.data)

def build_blocks(base,allocation):
    mask=allocation+MASK_OFFSET
    c=Code(allocation)
    # Shop's collection index -> int16 model in 44-byte collection records.
    c.emit('83 b9 20 04 00 00 06');c.jump('0f 84','original')
    c.emit('48 63 81 30 02 00 00 48 85 c0');c.jump('0f 88','original')
    c.emit('49 bb');c.emit(struct.pack('<Q',base+0x11827c2))
    c.emit('45 0f b7 1b 4c 39 d8');c.jump('0f 83','original')
    c.emit('49 bb');c.emit(struct.pack('<Q',base+0x11827b8))
    c.emit('4d 8b 1b 4d 85 db');c.jump('0f 84','original')
    c.emit('48 6b c0 2c 41 0f bf 04 03 3d ea 03 00 00');c.jump('0f 83','original')
    c.mask(mask);c.jump('0f 83','original')
    c.emit('31 c0 c3') # Return false before ownership and Stud writes.
    c.label('original');c.emit(SITES[0][1]);c.absolute(base+SITES[0][0]+len(SITES[0][1]))
    result=[(0,c.finish())]
    c=Code(allocation+0x140)
    # Preserve volatile registers too: this detour sits inside a function.
    c.emit('50 41 53 44 89 e0 3d ea 03 00 00');c.jump('0f 83','original')
    c.emit('83 bb 20 04 00 00 06');c.jump('0f 84','original') # Custom-character mode.
    c.mask(mask);c.jump('0f 83','original')
    c.emit('45 85 ed');c.jump('0f 85','hide')
    c.emit('45 31 f6') # Initial HUD callback also receives UI-only found=0.
    c.label('hide');c.emit('41 5b 58');c.absolute(base+0x265ea1) # Native hidden-price / no-buy branch.
    c.label('original');c.emit('41 5b 58 45 85 ed');c.jump('0f 85',base+0x265ea1)
    c.absolute(base+0x265b65);result.append((0x140,c.finish()))
    c=Code(allocation+0x240)
    c.emit(SITES[2][1]);c.emit('9c 50 41 53')
    c.emit('45 85 c0');c.jump('0f 85','done') # Owned remains selectable.
    c.emit('83 bb 20 04 00 00 06');c.jump('0f 84','done')
    c.emit('89 d0 3d ea 03 00 00');c.jump('0f 83','done')
    c.mask(mask);c.jump('0f 83','done')
    c.emit('45 31 c9') # Only UI discovery argument: native source flags untouched.
    c.label('done');c.emit('41 5b 58 9d');c.absolute(base+0x26613f)
    result.append((0x240,c.finish()))
    assert len(result[0][1])<=0x140 and len(result[1][1])<=0x100 and len(result[2][1])<=0x120
    c=Code(allocation+0x500)
    # Native category availability only considers genuine source discoveries.
    # Derive additional availability from ownership without altering those flags.
    c.emit('48 b8');c.emit(struct.pack('<Q',base+0x17ebfc8));c.emit('48 8b 00 48 0f be c9 84 d2')
    c.jump('0f 85','flag')
    c.emit('48 b8');c.emit(struct.pack('<Q',base+0x17ebfd0));c.emit('48 8b 00')
    c.label('flag');c.emit('48 85 c0');c.jump('0f 84','zero')
    c.emit('0f b6 04 08 84 c0');c.jump('0f 85','return')
    c.emit('48 85 c9');c.jump('0f 88','zero')
    c.emit('48 b8');c.emit(struct.pack('<Q',base+0x11827c2));c.emit('0f b7 10')
    c.emit('49 b8');c.emit(struct.pack('<Q',base+0x11827b8));c.emit('4d 8b 00 4d 85 c0');c.jump('0f 84','zero')
    c.emit('49 b9');c.emit(struct.pack('<Q',base+0x1c7cbb8));c.emit('4d 8b 09 4d 85 c9');c.jump('0f 84','zero')
    c.emit('45 31 d2')
    c.label('loop');c.emit('41 39 d2');c.jump('0f 83','zero')
    c.emit('41 38 48 17');c.jump('0f 85','next')
    c.emit('41 f6 40 16 08');c.jump('0f 84','next')
    c.emit('45 0f bf 18 41 81 fb ea 03 00 00');c.jump('0f 83','next')
    c.emit('43 80 bc 19 80 00 00 00 00');c.jump('0f 85','one')
    c.label('next');c.emit('49 83 c0 2c 41 ff c2');c.jump('e9','loop')
    c.label('one');c.emit('b8 01 00 00 00 c3')
    c.label('zero');c.emit('31 c0')
    c.label('return');c.emit('c3');result.append((0x500,c.finish()))
    return result

def header():
    # Relocations are absolute image/allocation addresses, materialized at runtime
    # by rebuilding the same byte template with each 8-byte address fixed up.
    base=0x140000000;allocation=0x180000000
    lines=['// Generated from purchase_gate.py; do not edit.']
    for index,((rva,original,offset),(_,data)) in enumerate(zip(SITES,build_blocks(base,allocation))):
        lines.append(f'static constexpr unsigned shop_rva_{index}=0x{rva:x},shop_offset_{index}=0x{offset:x};')
        for name,value in [('original',original),('code',data)]:
            lines.append(f'static const unsigned char shop_{name}_{index}[]={{'+','.join(str(x) for x in value)+'};')
        # Rel32 external branches require relocation too; generate runtime builder
        # using direct template comparison for both independently shifted bases.
        changed_base=dict(build_blocks(base+0x10000,allocation))[offset]
        changed_alloc=dict(build_blocks(base,allocation+0x10000))[offset]
        used=set();fixes=[]
        for start in range(len(data)-7):
            value=struct.unpack_from('<Q',data,start)[0]
            if base<=value<base+0x2000000 or allocation<=value<allocation+4096:
                if any(x in used for x in range(start,start+8)):continue
                kind=0 if base<=value<base+0x2000000 else 1
                fixes.append((start,8,kind,value-(base if kind==0 else allocation)))
                used.update(range(start,start+8))
        for start in range(len(data)-3):
            if any(x in used for x in range(start,start+4)):continue
            value=struct.unpack_from('<i',data,start)[0]
            if (struct.unpack_from('<i',changed_base,start)[0]==value+0x10000 and
                struct.unpack_from('<i',changed_alloc,start)[0]==value-0x10000):
                fixes.append((start,4,2,value));used.update(range(start,start+4))
        lines.append(f'static void RelocateShop{index}(unsigned char* p,std::uintptr_t base,std::uintptr_t block) {{')
        for start,size,kind,value in fixes:
            expr=f'{"base" if kind==0 else "block"}+0x{value:x}' if kind<2 else f'{value}LL+static_cast<long long>(base)-0x{base:x}LL-static_cast<long long>(block)+0x{allocation:x}LL'
            lines.append(f'{{ auto v=static_cast<std::{"uint64_t" if size==8 else "int32_t"}>({expr});std::memcpy(p+{start},&v,{size}); }}')
        lines.append('}')
    return '\n'.join(lines)
