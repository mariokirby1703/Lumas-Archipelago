import re
import math
import struct
from contextlib import nullcontext
from .memory import MemoryUnavailable,valid_range
from .native_read import read_stage_objects,read_actors
from .ap_hud_ticker import ascii_text,item_colour
from .ap_hud_publisher import MAGIC,installed,HOOK

def result_origin(memory,layer):
    """Measured PAL result coordinate controller, never a mutable UI write.

    The 2x3 affine matrix translates result-local pixels. Its horizontal
    origin additionally includes the native widescreen centre adjustment.
    """
    style=memory.read_ptr_checked(layer+0x8c,16)
    if memory.read_u32(style)!=0x807ab988:
        raise MemoryUnavailable('Result coordinate-controller class differs')
    view=memory.read_ptr_checked(style+12,0xd0)
    width=struct.unpack('>f',memory.read_bytes(view+0x18,4))[0]
    viewport=struct.unpack('>f',memory.read_bytes(view+0x30,4))[0]
    matrix=struct.unpack('>6f',memory.read_bytes(view+0xb8,24))
    if (not all(math.isfinite(v) for v in (width,viewport,*matrix))
            or not 320<=width<=1920 or not 320<=viewport<=3840
            or any(abs(a-b)>0.0001 for a,b in zip((matrix[0],matrix[1],matrix[3],matrix[4]),(1,0,0,1)))
            or abs(matrix[2])>1920 or abs(matrix[5])>1080):
        raise MemoryUnavailable('Result transform is not a supported translation')
    origin=(matrix[2]+(viewport-width)*0.5,matrix[5])
    anchors=[(a,memory.read_bytes(a,n)) for a,n in
             ((layer+0x8c,4),(style,16),(view+0x18,4),(view+0x30,4),(view+0xb8,24))]
    return origin,anchors


def discover(memory):
    rows=read_stage_objects(memory,False)
    if len(rows)!=1 or rows[0].get('scene') not in ('gameplay','world_map','global_map','game_land_select','results','save_select'):
        raise MemoryUnavailable('HUD requires gameplay or a map')
    found={}
    actors=read_actors(memory,rows[0]['context'])
    menu_anchors=[]
    if rows[0]['scene']=='save_select':
        from .ap_hud_publisher import REGISTRY
        if not getattr(memory,'native_patch',None):
            raise MemoryUnavailable('Save Select requires the native HUD registry')
        control=memory.read_ptr_checked(REGISTRY,24)
        if memory.read_u32(control)!=MAGIC:
            raise MemoryUnavailable('Save Select HUD registry awaits first draw')
        if memory.read_u32(control+20)!=control+16:
            raise MemoryUnavailable('Save Select HUD reference not registered')
        handle=control+16
        menu_anchors=[(p,memory.read_bytes(p,4)) for p in (REGISTRY,control+16,control+20,rows[0]['context']+0x74)]
        actors=[handle]
    for actor in actors:
        # Native HUD owner classes, verified in gameplay and the shared maps.
        # Scanning every gameplay object's pointer fields caused thousands of
        # unnecessary cross-process reads on every Act transition.
        if rows[0]['scene']=='gameplay' and memory.read_u32(actor)!=0x80764440:continue
        raw=memory.read_bytes(actor,0x480)
        for offset in range(4,len(raw),4):
            pointer=struct.unpack_from('>I',raw,offset)[0]
            if not (0x80000000<=pointer<0x94000000 and pointer%4==0):continue
            try:
                layer=memory.read_ptr_checked(pointer,0xe0)
                if memory.read_u32(layer)!=0x807abc40:continue
                layout=memory.read_ptr_checked(layer+12,0x34)
                counts={'gameplay':(96,103),'world_map':(111,),'global_map':(111,),
                        'game_land_select':(93,104),'results':(95,),'save_select':(350,)}
                if memory.read_u32(layout+44) not in counts[rows[0]['scene']]:continue
                count=memory.read_u32(layout+44)
                table=memory.read_ptr_checked(layout+48,count*12)
                dictionary=memory.read_bytes(table,count*12)
                sourcegroups=memory.read_ptr_checked(layout+40,128)
                boxes={};control=None;arrays={}
                def checked_pointer(value,size):
                    if value%4 or not valid_range(value,size):raise MemoryUnavailable('invalid HUD resource pointer')
                    return value
                for i in range(count):
                    nameptr,group,index=struct.unpack_from('>III',dictionary,i*12)
                    checked_pointer(nameptr,4)
                    name=memory.read_bytes(nameptr,48).split(b'\0')[0].decode('ascii')
                    if not name.startswith('ap_'):continue
                    if not 1<=group<32 or not 0<=index<15:raise MemoryUnavailable('HUD cast index differs')
                    if group not in arrays:
                        sourcearray=memory.read_ptr_checked(sourcegroups+group*16+4,60)
                        arrays[group]=memory.read_bytes(sourcearray,60)
                    record=checked_pointer(struct.unpack_from('>I',arrays[group],index*4)[0],116)
                    font=memory.read_bytes(record,116)
                    if struct.unpack_from('>I',font,4)[0]!=2:raise MemoryUnavailable('HUD cast is not a font')
                    box=checked_pointer(struct.unpack_from('>I',font,64)[0],156)
                    mailbox=memory.read_bytes(box,156)
                    if struct.unpack_from('>I',mailbox,152)[0]!=0x41504d42:raise MemoryUnavailable('AP mailbox marker missing')
                    shared=checked_pointer(struct.unpack_from('>I',mailbox,4)[0],16)
                    if control is None:
                        header=memory.read_bytes(shared,16)
                        if struct.unpack_from('>I',header)[0]!=MAGIC or struct.unpack_from('>I',header,8)[0]!=128:
                            raise MemoryUnavailable('HUD mailbox signature missing')
                    if control not in (None,shared):raise MemoryUnavailable('HUD controller differs')
                    control=shared
                    boxname=checked_pointer(struct.unpack_from('>I',mailbox,12)[0],4)
                    if boxname!=nameptr:
                        # Builder may emit a second identical string for the dictionary.
                        if memory.read_bytes(boxname,48).split(b'\0')[0].decode('ascii')!=name:
                            raise MemoryUnavailable('HUD mailbox name differs')
                    boxes[name]=(record,box)
                if len(boxes)!=90:continue
                handle=actor+offset-4
                anchors=menu_anchors+([] if menu_anchors else [(actor,memory.read_bytes(actor,16))])+[(handle,memory.read_bytes(handle,8)),
                         (pointer,memory.read_bytes(pointer,4)),(layer,memory.read_bytes(layer,4)),
                         (layer+12,memory.read_bytes(layer+12,4)),(layer+0x8c,memory.read_bytes(layer+0x8c,4)),(control,memory.read_bytes(control,4))]
                origin=(0.,0.)
                music_y={}
                if rows[0]['scene']=='results':
                    origin,transform_anchors=result_origin(memory,layer)
                    anchors+=transform_anchors
                    from ..world_constants import BY_MISSION
                    offset=-50. if BY_MISSION.get(rows[0].get('mission'),{}).get('kind')=='Game Land' else 0.
                    for name,(record,box) in boxes.items():
                        if not name.startswith('ap_music_'):continue
                        info=memory.read_ptr_checked(record+48,60)
                        baseline=memory.read_f32(info+8)*480.
                        if not math.isfinite(baseline) or not -480<=baseline<=960:
                            raise MemoryUnavailable('Result music baseline invalid')
                        anchors.extend(((record+48,memory.read_bytes(record+48,4)),
                                        (info+8,memory.read_bytes(info+8,4))))
                        music_y[record+108]=struct.pack('>f',baseline+offset)
                found[layer]={'layer':layer,'handle':handle,'control':control,'boxes':boxes,'anchors':anchors,
                              'music_y_positions':music_y,
                              'key':(rows[0]['context'],rows[0]['scene']),'origin':origin,
                              'music_x_offset':(-25. if rows[0]['scene']=='gameplay'
                                                and memory.read_u32(layout+44) in (96,103) else 0.)}
            except (MemoryUnavailable,UnicodeDecodeError,ValueError):continue
    return unique_owner(found.values())


def unique_owner(owners):
    """Result UI instances can share one resource-owned mailbox set.

    PAL results owns two layers (owner offsets 0x88 and 0x90). Both
    reference the same relocated font records and controller. They are one
    publication target; unrelated resources must still fail closed.
    """
    targets={}
    for owner in owners:
        key=(owner['control'],tuple(sorted(owner['boxes'].items())))
        targets.setdefault(key,owner)
    if len(targets)!=1:
        raise MemoryUnavailable('AP HUD owner not uniquely resolved')
    return next(iter(targets.values()))

def validate(memory,owner):
    if any(memory.read_bytes(a,len(value))!=value for a,value in owner['anchors']):
        raise MemoryUnavailable('AP HUD owner changed')

def payloads(owner,events,metrics,music=None):
    result={}
    for name,(record,box) in owner['boxes'].items():
        base=name.split('_outline')[0];shadow='_outline' in name
        if base.startswith('ap_music_'):
            music=music or {'alpha':0,'title':''}
            text={'ap_music_icon':' ','ap_music_heading':'NOW PLAYING:','ap_music_title':music.get('title','')}.get(base,'')
            alpha=music.get('alpha',0);colour=0x00000000 if shadow else 0xffffff00
            colour|=alpha
            fitted='';width=0.
            for char in ascii_text(text):
                if width+metrics[char]>540 or len(fitted)>=127:break
                fitted+=char;width+=metrics[char]
            # Align the panel to the native right HUD edge. The icon sits just
            # before the heading; the title has its own right-aligned baseline.
            heading_width=sum(metrics[c] for c in 'NOW PLAYING:')
            x=800.+owner.get('music_x_offset',0.)-width-owner.get('origin',(0.,0.))[0]
            if base=='ap_music_icon':x=800.+owner.get('music_x_offset',0.)-heading_width-6.-width-owner.get('origin',(0.,0.))[0]
            if shadow:x+=(-0.8,0.8,0.,0.)[int(name[-1])]
            raw=(fitted or ' ').encode('ascii').ljust(128,b'\0')
            result[box+8]=struct.pack('>I',owner['handle']);result[box+16]=raw
            result[box+144]=struct.pack('>If',colour,x)
            continue
        if base.startswith('ap_prefix'):slot=int(base[len('ap_prefix'):]);kind='prefix'
        else:
            match=re.fullmatch(r'ap_(title|subtitle)(?:_(\d))?',base)
            if not match:raise MemoryUnavailable('unknown AP cast')
            kind=match[1];slot=int(match[2] or 0)
        if slot<len(events):
            event=events[slot];prefix=event['kind']+' '
            text=prefix if kind=='prefix' else event['item'] if kind=='title' else ('to ' if event['kind']=='Sent' else 'from ')+event['player']
            colour=int(item_colour(event.get('flags',0))[1:]+'ff',16) if kind=='title' else 0xffffffff
            if event.get('own'):
                prefix=''
                text='Found your own' if kind=='prefix' else ' ' if kind=='title' else event['item']
                colour=int(item_colour(event.get('flags',0))[1:]+'ff',16) if kind=='subtitle' else 0xffffffff
        else:text=' ';prefix='';colour=0xffffffff
        raw=ascii_text(text)
        # Use the full 400-pixel native text bounds, rather than the old narrow
        # 250-pixel column. Keep the prefix and title inside one shared line.
        fitted='';width=0.
        for char in raw:
            advance=metrics[char]
            limit=580.-sum(metrics[c] for c in prefix) if kind=='title' else 580.
            if width+advance>limit or len(fitted)>=127:break
            fitted+=char;width+=advance
        x=50.+(sum(metrics[c] for c in prefix) if kind=='title' else 0.)-owner.get('origin',(0.,0.))[0]
        if shadow:
            direction=int(name[-1]);x+=(-0.8,0.8,0.,0.)[direction];colour=0x000000ff
        if slot<len(events):colour=(colour&0xffffff00)|events[slot].get('alpha',255)
        textbytes=(fitted or ' ').encode('ascii');textbytes+=b'\0'*(128-len(textbytes))
        result[box+8]=struct.pack('>I',owner['handle'])
        result[box+16]=textbytes
        result[box+144]=struct.pack('>If',colour,x)
    return result

def mailbox_acks(memory, boxes):
    """Read 90 guest ACK words in bounded spans rather than 90 DME round trips.

    ACK ownership is already checked by discover()/validate(). Only coherent
    contiguous read-only snapshots are grouped. An unreadable span falls back
    to individual addresses; an invalid individual ACK still aborts the frame.
    """
    positions=sorted({box for record,box in boxes.values()})
    if not positions:
        return {}
    spans=[];start=positions[0];end=start+4;words=[start]
    for address in positions[1:]:
        if address-end<=512 and address+4-start<=4096 and valid_range(start,address+4-start):
            end=address+4;words.append(address)
        else:
            spans.append((start,end,words))
            start=address;end=address+4;words=[address]
    spans.append((start,end,words))
    result={}
    for start,end,words in spans:
        try:
            data=memory.read_bytes(start,end-start)
        except MemoryUnavailable:
            # A gap may cross an unmapped guest page. Never treat that as an ACK.
            for address in words:result[address]=memory.read_u32(address)
        else:
            for address in words:result[address]=struct.unpack_from('>I',data,address-start)[0]
    return result


def render(runtime,memory):
    enabled=True
    state=getattr(runtime,'_hud_connected',None)
    snapshot=runtime.snapshot
    if ((not enabled and state is None) or not snapshot.scene_verified
            or snapshot.scene not in ('gameplay','world_map','global_map','game_land_select','results','save_select')
            or snapshot.scene=='gameplay' and getattr(snapshot,'death_state','alive')!='alive'):
        runtime.hud_ticker.elapsed_visible(False)
        return {'hud_ready':False,'status':'HUD disabled or scene unavailable'}
    # A recent authenticated scene observation is sufficient for read-only
    # discovery. Every mailbox write separately validates guest-owned anchors
    # and the exact publisher entry point.
    if not (getattr(memory,'revision_observation',None) or {}).get('verified'):
        memory.verify_revision()
    if state is None and not installed(memory):
        return {'hud_ready':False,'status':'install AP-connected Riivolution patch'}
    identity=(snapshot.session,snapshot.stage_epoch,snapshot.scene)
    changed_owner = state is None or state['identity'] != identity
    if changed_owner:
        if state is not None and not installed(memory):
            return {'hud_ready':False,'status':'install AP-connected Riivolution patch'}
        owner=discover(memory)
        from ..world_constants import load_data
        state={'identity':identity,'owner':owner,'metrics':load_data('hud_glyph_metrics.json'),'pending':None,'shown':None,
               'publisher_verified_at':runtime.clock(),
               'publisher_hook':memory.read_bytes(HOOK,4)}
        runtime._hud_connected=state
    owner=state['owner']
    try:validate(memory,owner)
    except MemoryUnavailable:
        runtime._hud_connected=None
        raise
    pending=state['pending']
    if pending:
        acknowledgements=mailbox_acks(memory,owner['boxes'])
        outstanding=sum(value!=pending['generation'] for value in acknowledgements.values())
        if outstanding:
            return {'hud_ready':False,'font_ready':True,'owner_verified':True,'status':'waiting for game-thread ACK','generation':pending['generation'],
                    'pending_casts':outstanding}
        if pending['candidate']:runtime.hud_ticker.published(pending['candidate'])
        popup=getattr(runtime,'music_popup',None)
        if popup:popup.published(pending.get('music_generation'),runtime.clock())
        state['shown']=pending['events'];state['pending']=None
    runtime.hud_ticker.elapsed_visible(True)
    if runtime.hud_ticker.data['queue']:runtime.hud_ticker.remaining=0
    events=runtime.hud_ticker.panel_events() if enabled else []
    from .music_popup import update
    music=update(runtime)
    if events!=state['shown'] or music!=state.get('music'):
        # Complete publisher re-verification is expensive (~120 guest reads).
        # Perform it at most four times per second, and on each new owner.
        # On intervening frames check the exact entry instruction, while the
        # write policy independently checks owner anchors and native hook.
        if not changed_owner:
            if runtime.clock() - state['publisher_verified_at'] >= .25:
                if not installed(memory):
                    runtime._hud_connected=None
                    raise MemoryUnavailable('HUD publisher signature changed')
                state['publisher_verified_at']=runtime.clock()
            else:
                if memory.read_bytes(HOOK,4)!=state['publisher_hook']:
                    runtime._hud_connected=None
                    raise MemoryUnavailable('HUD publisher entry changed')
        writes=payloads(owner,events,state['metrics'],music)
        # One bounded data write per cast, preserving its relocated name.
        # Previously handle/text/colour each incurred separate pre/post owner
        # validation, tripling the initial publication's process round trips.
        previous=state.get('published_payloads',{})
        mailboxes={}
        for record,box in owner['boxes'].values():
            raw=writes[box+8]+writes[box+16]+writes[box+144]
            old=previous.get(box+8)
            mailboxes[box+8]=(old if old is not None and old[:4]+old[8:]==raw else
                             writes[box+8]+memory.read_bytes(box+12,4)+writes[box+16]+writes[box+144])
        writes=mailboxes
        writes.update(owner.get('music_y_positions',{}))
        # These mailbox payload bytes are host-owned; the guest writes only
        # ACKs outside them. Fade one row without republishing the other rows.
        desired=writes
        writes={a:data for a,data in desired.items() if previous.get(a)!=data}
        generation=(memory.read_u32(owner['control']+4)+2)&0xfffffffe
        if generation==0:generation=2
        memory._hud_transaction={'owner':owner,'allowed':{a:len(v) for a,v in writes.items()}|{owner['control']+4:4},
                                 'hook':memory.read_bytes(HOOK,4),'identity':identity}
        try:
            batch=getattr(getattr(memory,'backend',None),'hud_write_batch',None)
            with batch() if batch else nullcontext():
                def write(a,data):
                    before=memory.read_bytes(a,len(data))
                    if before!=data:memory.write_bytes_verified(a,data,expected=before,operation='hud_mailbox')
                write(owner['control']+4,struct.pack('>I',generation-1))
                for a,data in writes.items():write(a,data)
                write(owner['control']+4,struct.pack('>I',generation))
        finally:memory._hud_transaction=None
        state['published_payloads']=desired
        state['pending']={'generation':generation,'events':events,'candidate':runtime.hud_ticker.candidate() if enabled and runtime.hud_ticker.has_pending_candidate() else None,
                          'music_generation':getattr(getattr(runtime,'music_popup',None),'generation',None)}
        state['music']=dict(music)
    return {'hud_ready':enabled and state['shown'] is not None,'font_ready':True,'owner_verified':True,
            'publisher_ack':state['pending'] is None,'status':'AP panel connected','displayed':len(state['shown'] or [])}
