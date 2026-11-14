"""Persistent standalone progress from native descriptors and 20-byte records."""
import struct
from inventory_reader import pointer
from mission_checks import decode_shield_mask


def parse_level_progress(descriptor,record,index):
    if len(descriptor)!=0x80 or len(record)!=20:raise ValueError('Incomplete level progress')
    path=descriptor[:64].split(b'\0')[0].decode('ascii').replace('\\','/').lower()
    segments=path.split('/')
    if len(segments)!=2 or segments[0]!='standalones':return None
    if record[4] not in (0,1) or record[5] not in (0,1):raise ValueError('Invalid hero progress flag')
    native_name=descriptor[64:128].split(b'\0')[0].decode('ascii').lower()
    red_mission=segments[1]
    if red_mission=='blackwells_mansion':
        red_mission=native_name if native_name in ('blackwells_mansion_1','blackwells_mansion_2') else None
    return dict(mission=segments[1],level_index=index,complete=bool(record[10]&0x10),
                hero_complete=bool(record[4] or record[5]),shield_parts=decode_shield_mask(record[10]&15),
                red_brick=bool(record[9]&2),red_brick_mission=red_mission,
                raw_record=record.hex(),source_path=path)


def read_level_progress(read,base):
    table=pointer(read,base+0x1C7D430)
    count=struct.unpack('<i',read(base+0x1C7D438,4))[0]
    bank=pointer(read,base+0x1C7D510)
    if not table or not bank:return dict(status='not_initialized',records=[])
    if not 0<count<=256:raise ValueError('Invalid level descriptor count')
    records=[];observed=[]
    for index in range(count):
        descriptor=read(table+index*0x350,0x80)
        raw=read(bank+index*20,20)
        row=parse_level_progress(descriptor,raw,index)
        if row:records.append(row);observed.append((index,raw,descriptor))
    if (pointer(read,base+0x1C7D430)!=table or pointer(read,base+0x1C7D510)!=bank
            or struct.unpack('<i',read(base+0x1C7D438,4))[0]!=count
            or any(read(bank+i*20,20)!=raw or read(table+i*0x350,0x80)!=d for i,raw,d in observed)):
        raise RuntimeError('Persistent level progress changed during snapshot')
    return dict(status='read',records=records,evidence='native 0x9cb649 completion; 0x9cbd82 hero; mine live validated')


def completed_level_keys(state):
    if state.get('status')!='read':return set()
    groups={}
    for row in state.get('records',[]):groups.setdefault(row['mission'],[]).append(row)
    keys=set()
    for mission,rows in groups.items():
        for row in rows:
            red_mission=row.get('red_brick_mission',mission)
            if row.get('red_brick') and red_mission:keys.add('mission:'+red_mission+':Red Brick')
        if all(r['complete'] for r in rows):keys.add('mission:'+mission+':Complete')
        # Multiple native missions currently share one catalogue resource name
        # (Blackwell's Mansion). Do not merge their collectible rewards.
        if len(rows)!=1:continue
        row=rows[0];prefix='mission:'+mission+':'
        if row['hero_complete']:keys.add(prefix+'LEGO City Hero')
        keys.update(prefix+part for part in row['shield_parts'])
        if set(row['shield_parts'])=={'TL','TR','BL','BR'}:keys.add(prefix+'Police Shield')
    return keys
