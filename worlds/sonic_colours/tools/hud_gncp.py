"""Append-only PAL GNCP overlay rewrite; input-specific and experimental.

Layout reference: TGE's sonic_xncp_yncp.bt. All existing project offsets stay
fixed. Added offsets are registered in NOF0; chunk/header lengths are rebuilt.
"""
import struct

BASE=32
HUD_LEFT=50.
SAMPLE_MESSAGES=(('Received Test Item','from 64 Player'),('Sent Test Item','to Player'),
                 ('Received Double Jump','from HK Player'),('Sent Progressive Key','to SM64 Player'),
                 ('Received Red Ring','from Player'))

def compact_glyph_uv(entry,tls,character):
    """Trim transparent IA4 cell columns; retain height/baseline and atlas."""
    image=u(tls,u(tls,8)+3*8)
    height,width=struct.unpack_from('>HH',tls,image);data=u(tls,image+8)
    if u(tls,image+4)!=2:raise ValueError('font atlas must be IA4')
    left,top,right,bottom=struct.unpack_from('>ffff',entry,4)
    x0,x1=round(left*width),round(right*width);y0,y1=round(top*height),round(bottom*height)
    if not 0<=x0<x1<=width or not 0<=y0<y1<=height:raise ValueError('invalid glyph cell')
    columns=[]
    for x in range(x0,x1):
        for y in range(y0,y1):
            pixel=data+((y//4)*((width+7)//8)+x//8)*32+(y%4)*8+x%8
            if pixel>=len(tls):raise ValueError('atlas pixel outside file')
            if tls[pixel]>>4:
                columns.append(x);break
    if columns:
        lo=max(x0,min(columns)-1);hi=min(x1,max(columns)+2)
    elif character==32:lo=x0;hi=min(x1,x0+7)
    else:raise ValueError('empty non-space glyph')
    result=bytearray(entry)
    struct.pack_into('>ffff',result,4,lo/width,top,hi/width,bottom)
    return result

def u(b,o):return struct.unpack_from('>I',b,o)[0]
def ptr(b,o):return u(b,o)+BASE if u(b,o) else None
def string(b,o):return b[o:b.index(0,o)].decode('ascii')

def scene(b,name):
    root=ptr(b,48);table=ptr(b,root+4);names=ptr(b,root+8)
    for i in range(u(b,root)):
        if string(b,ptr(b,names+i*8))==name:return ptr(b,table+i*4)
    raise ValueError('missing scene '+name)

def cast(b,s,name):
    table=ptr(b,s+48);groups=ptr(b,s+40)
    for i in range(u(b,s+44)):
        row=table+i*12
        if string(b,ptr(b,row))==name:
            group=groups+16*u(b,row+4)
            return ptr(b,ptr(b,group+4)+4*u(b,row+8))
    raise ValueError('missing cast '+name)

def overlay(gameplay,keyboard,texture_index=12,keyboard_tls=None,messages=SAMPLE_MESSAGES,scene_name='info_2',base_y=140.,ap_connected=False,music_y_offset=0.):
    """Build static PoC casts. Visual placement and lifetime need Dolphin QA."""
    s=scene(gameplay,scene_name);ks=scene(keyboard,'Scene_soft_keyboad_bg')
    original_ngroups=u(gameplay,s+36);original_casts=u(gameplay,s+44)
    animation_count=u(gameplay,s+52)
    if not 1<=animation_count<=32:raise ValueError('unsupported animation count')
    original_textures=u(gameplay,s+20)
    no=u(gameplay,20)
    if gameplay[no:no+4]!=b'NOF0':raise ValueError('missing relocation chunk')
    reloc=[u(gameplay,no+16+4*i) for i in range(u(gameplay,no+8))]
    out=bytearray(gameplay[:no])
    def append(blob,alignment=4):
        out.extend(b'\0'*((-len(out))%alignment));o=len(out);out.extend(blob);return o
    def word(o,value):struct.pack_into('>I',out,o,value)
    def offset(o,target):
        word(o,target-BASE if target else 0)
        if target and o-BASE not in reloc:reloc.append(o-BASE)
    def text(value):return append(value.encode('ascii')+b'\0')

    # Per-texture dimensions are normalized to the 640x480 UI canvas.
    if u(keyboard,ks+20)!=4 or texture_index!=original_textures:
        raise ValueError('texture dimension tables differ')
    dimensions=ptr(gameplay,s+24);source_dimensions=ptr(keyboard,ks+24)
    offset(s+24,append(gameplay[dimensions:dimensions+original_textures*8]+keyboard[source_dimensions+24:source_dimensions+32]))
    word(s+20,original_textures+1)

    # Append scene-local UV entries and translate font-global glyph mappings.
    ft=ptr(keyboard,60);maps=ptr(keyboard,ft+4);names=ptr(keyboard,ft+8)
    glyph=None
    for i in range(u(keyboard,ft)):
        if string(keyboard,ptr(keyboard,names+i*8))=='common_text':
            glyph=keyboard[ptr(keyboard,maps+i*8+4):ptr(keyboard,maps+i*8+4)+8*u(keyboard,maps+i*8)]
    if glyph is None or len(glyph)!=77*8:raise ValueError('alphabet differs')
    oldsubs=u(gameplay,s+28);subtable=ptr(gameplay,s+32)
    sub=bytearray(gameplay[subtable:subtable+oldsubs*20]);newmap=bytearray()
    source_sub=ptr(keyboard,ks+32)
    for i in range(77):
        character,index=struct.unpack_from('>II',glyph,i*8)
        if index>=u(keyboard,ks+28):raise ValueError('invalid glyph subimage')
        entry=bytearray(keyboard[source_sub+index*20:source_sub+(index+1)*20])
        if u(entry,0)!=3:raise ValueError('unexpected source glyph texture')
        if keyboard_tls is not None:entry=compact_glyph_uv(entry,keyboard_tls,character)
        struct.pack_into('>I',entry,0,texture_index);sub.extend(entry)
        newmap.extend(struct.pack('>II',character,oldsubs+i))
    offset(s+32,append(sub));word(s+28,oldsubs+77)
    fontname=text('ap_common_text');mapping=append(newmap)
    gf=ptr(gameplay,60);nf=u(gameplay,gf);gt=ptr(gameplay,gf+4);gn=ptr(gameplay,gf+8)
    table=append(gameplay[gt:gt+nf*8]+struct.pack('>II',77,mapping-BASE))
    font_ids=[gameplay[gn+i*8:gn+(i+1)*8] for i in range(nf)]
    font_ids.append(struct.pack('>II',fontname-BASE,nf))
    font_ids.sort(key=lambda row:string(out,u(row,0)+BASE))
    ids=append(b''.join(font_ids))
    for i in range(nf+1):
        offset(table+i*8+4,ptr(out,table+i*8+4));offset(ids+i*8,ptr(out,ids+i*8))
    fontroot=append(struct.pack('>III',nf+1,table-BASE,ids-BASE))
    offset(fontroot+4,table);offset(fontroot+8,ids);offset(60,fontroot)

    controller=append(struct.pack('>4I',0x41504844,0,128,90)) if ap_connected else None
    source=cast(keyboard,ks,'text_name');records=[]
    if not 1<=len(messages)<=5 or any(len(message)!=2 for message in messages):
        raise ValueError('overlay requires one to five two-line messages')
    # Separate item name from white prefix so classification affects only it.
    palette=(0xAF70FFFF,0x305BD8FF,0x64C8FFFF,0xF05252FF,0xAF70FFFF)
    specs=[]
    metrics={}
    for j in range(77):
        ch=chr(u(newmap,j*8));uv=struct.unpack_from('>ffff',sub,(oldsubs+j)*20+4)
        metrics[ch]=(uv[2]-uv[0])*312*0.45
    for message,(title,subtitle) in enumerate(tuple(messages)+(('BGM Now Playing','Track'),)):
        if message==len(messages):
            parts=(('ap_music_icon',' ',775.,365.+music_y_offset,0xffffffff),
                   ('ap_music_heading','NOW PLAYING:',790.,365.+music_y_offset,0xffffffff),
                   ('ap_music_title','Track',760.,382.+music_y_offset,0xffffffff))
            for name,label,x,y,colour in parts:
                for shadow,(dx,dy) in enumerate(((-0.8,0.),(0.8,0.),(0.,-0.8),(0.,0.8))):
                    specs.append((name+'_outline'+str(shadow),label,x+dx,y+dy,0x000000ff))
                specs.append((name,label,x,y,colour))
            break
        prefix,item=title.split(' ',1);prefix+=' '
        y=base_y+message*40.
        parts=((f'ap_prefix{message}',prefix,HUD_LEFT,y,0xffffffff),
               (('ap_title'+('_'+str(message) if message else '')),item,
                HUD_LEFT+sum(metrics[c] for c in prefix),y,palette[message]),
               (('ap_subtitle'+('_'+str(message) if message else '')),subtitle,HUD_LEFT,y+17.,0xffffffff))
        for name,label,x,y,colour in parts:
            for shadow,(dx,dy) in enumerate(((-0.8,0.),(0.8,0.),(0.,-0.8),(0.,0.8))):
                specs.append((name+'_outline'+str(shadow),label,x+dx,y+dy,0x000000ff))
            specs.append((name,label,x,y,colour))
    group_count=len(messages)+1
    count=len(specs);per_message=count//group_count
    for i,(name,label,x,y,colour_value) in enumerate(specs):
        rec=append(keyboard[source:source+116]);records.append(rec)
        info=append(keyboard[ptr(keyboard,source+48):ptr(keyboard,source+48)+60])
        if ap_connected:
            material=append(b'\0'*156)
            offset(material+4,controller);offset(material+12,text(name))
            out[material+16:material+18]=b' \0'
            word(material+144,colour_value);word(material+152,0x41504d42);struct.pack_into('>f',out,material+148,x)
        else:material=append(keyboard[ptr(keyboard,source+64):ptr(keyboard,source+64)+128])
        offset(rec+48,info);offset(rec+64,material);offset(rec+68,text(' ' if ap_connected else label));offset(rec+72,fontname)
        word(rec+80,400);word(rec+84,32)
        # Font-cast flags 0x18 use the pixel position fallback (805E08E8),
        # not the normalized CastInfo translation edited by v1/v2 alone.
        # Use a small white two-line block below the main left HUD.

        struct.pack_into('>ff',out,info+4,x/640.,y/480.)
        struct.pack_into('>ff',out,info+16,0.45,0.45)
        struct.pack_into('>f',out,rec+76,0.)
        source_colour=(0x000000ff if '_outline' in name else 0xffffffff) if ap_connected else colour_value
        for colour in range(0x1c,0x30,4):word(info+colour,source_colour)
        struct.pack_into('>8f',out,rec+12,0.,-16/480.,0.,16/480.,400/640.,-16/480.,400/640.,16/480.)
        struct.pack_into('>ff',out,rec+96,0.,0.)
        struct.pack_into('>ff',out,rec+104,x,y)
    # Replicate the live-validated two-cast group per message. Do not grow
    # its sibling traversal to ten casts (the v4 variant failed live).
    group_rows=[]
    for message in range(group_count):
        pair=records[message*per_message:(message+1)*per_message]
        casts=append(struct.pack('>'+'I'*per_message,*(r-BASE for r in pair)))
        for i,r in enumerate(pair):offset(casts+4*i,r)
        tree=append(b''.join(struct.pack('>ii',-1,i+1 if i+1<per_message else -1) for i in range(per_message)))
        group_rows.append(struct.pack('>IIII',per_message,casts-BASE,0,tree-BASE))
    original_groups=ptr(gameplay,s+40)
    ngroups=original_ngroups+group_count
    groups=append(gameplay[original_groups:original_groups+original_ngroups*16]+b''.join(group_rows))
    for i in range(ngroups):
        offset(groups+16*i+4,ptr(out,groups+16*i+4));offset(groups+16*i+12,ptr(out,groups+16*i+12))
    offset(s+40,groups);word(s+36,ngroups)
    original_dict=ptr(gameplay,s+48)
    entries=[gameplay[original_dict+i*12:original_dict+(i+1)*12] for i in range(original_casts)]
    castnames=[spec[0] for spec in specs]
    for i,name in enumerate(castnames):
        entries.append(struct.pack('>III',text(name)-BASE,original_ngroups+i//per_message,i%per_message))
    entries.sort(key=lambda row:string(out,u(row,0)+BASE))
    dictionary=append(b''.join(entries))
    for i in range(original_casts+count):offset(dictionary+i*12,ptr(out,dictionary+i*12))
    offset(s+48,dictionary);word(s+44,original_casts+count)
    # Preserve every original animation; overlay groups have no timed tracks.
    animation=ptr(gameplay,s+56)
    empty=append(b'\0'*(8*per_message))
    animations=[];a2groups=[];a2=ptr(gameplay,s+72)
    for index in range(animation_count):
        entry=animation+index*8;adata=ptr(gameplay,entry+4)
        if u(gameplay,entry)!=original_ngroups:raise ValueError('animation group count differs')
        agroups=append(gameplay[adata:adata+original_ngroups*8]+struct.pack('>II',per_message,empty-BASE)*group_count)
        for i in range(ngroups):offset(agroups+i*8+4,ptr(out,agroups+i*8+4))
        animations.append((ngroups,agroups))
        a2group=ptr(gameplay,a2+index*4);a2data=ptr(gameplay,a2group+4)
        a2entries=append(gameplay[a2data:a2data+original_ngroups*4]+b'\0'*(4*group_count))
        for i in range(original_ngroups):offset(a2entries+i*4,ptr(out,a2entries+i*4))
        a2new=append(gameplay[a2group:a2group+8]);offset(a2new+4,a2entries);a2groups.append(a2new)
    anew=append(b''.join(struct.pack('>II',count,groups-BASE) for count,groups in animations))
    for i,(_,groups) in enumerate(animations):offset(anew+i*8+4,groups)
    offset(s+56,anew)
    a2table=append(b''.join(struct.pack('>I',group-BASE) for group in a2groups))
    for i,group in enumerate(a2groups):offset(a2table+i*4,group)
    offset(s+72,a2table)
    out.extend(b'\0'*((-len(out))%32));newno=len(out)
    struct.pack_into('<I',out,36,newno-40)
    word(16,newno-32);word(20,newno)
    payload=struct.pack('>II',len(reloc),0)+b''.join(struct.pack('>I',r) for r in reloc)
    payload+=b'\0'*((-(8+len(payload)))%16)
    out.extend(b'NOF0'+struct.pack('<I',len(payload))+payload)
    word(24,len(payload)+8);out.extend(b'NEND'+b'\0'*12)
    for r in reloc:
        target=ptr(out,r+BASE)
        if target is None or not BASE<=target<newno:raise ValueError('invalid rebuilt relocation')
    for name in ('ap_title','ap_subtitle'):
        if u(out,cast(out,s,name)+4)!=2:raise ValueError('rebuilt font cast missing')
    return bytes(out)
