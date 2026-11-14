"""Read-only current-mission collectibles and shield grouping policy."""
PARTS = ('TL', 'TR', 'BL', 'BR')
PICKUP_TYPES = {119: 'TL', 120: 'TR', 121: 'BL', 101: 'BR'}


def hero_complete(total,threshold,latch):
    if any(type(v) is not int for v in (total,threshold,latch)) or total<0 or threshold<0 or latch not in (0,1):
        raise ValueError('Invalid native hero state')
    return bool(threshold and latch and total>=threshold)


def read_mission_hero(read,base,shield):
    """Mirror threshold getter 0x7ecbe0 and completion branch 0xa12257."""
    import struct
    from inventory_reader import pointer
    from scene_reader import player_scene
    if shield.get('status')!='read':return dict(status='unresolved_scene',complete=False)
    scene=player_scene(read,base)
    level=scene['level'];meta=pointer(read,level+0x18)
    if not meta:return dict(status='unresolved_level',complete=False)
    slot=struct.unpack('<i',read(base+0x1C7E61C,4))[0]
    if struct.unpack('<I',read(base+0x1C7E608,4))[0]:slot=0
    if not 0<=slot<2:raise ValueError('Invalid hero threshold slot')
    mode=struct.unpack('<I',read(base+0x1C7EB60,4))[0]
    if mode==1:
        threshold=struct.unpack('<I',read(meta+0x160+slot*4,4))[0]
    else:
        index=struct.unpack('<b',read(meta+0xAB,1))[0]
        count=struct.unpack('<i',read(base+0x1C7D438,4))[0]
        if not 0<=index<count<=256:return dict(status='unresolved_level',complete=False)
        table=pointer(read,base+0x1C7D430)
        threshold=struct.unpack('<I',read(table+index*0x350+0x190+slot*4,4))[0]
    raw=read(base+0x1C7E6E0,12)
    total,latch=struct.unpack('<QI',raw)
    complete=hero_complete(total,threshold,latch)
    if read(base+0x1C7E6E0,12)!=raw or player_scene(read,base)['level']!=level:
        raise RuntimeError('Hero state changed during snapshot')
    return dict(status='read',mission=shield['mission'],scene=shield['scene'],
                studs=total,threshold=threshold,latch=latch,complete=complete,
                evidence='0xa12257 native threshold/latch; mine live validated')


def decode_shield_mask(mask):
    if type(mask) is not int or not 0<=mask<=15:raise ValueError('Invalid shield mask')
    return [part for index,part in enumerate(PARTS) if mask & (1<<index)]


def read_mission_shield(read,base):
    import json
    import struct
    from pathlib import Path
    from inventory_reader import pointer,cstring,MISSION_TOKENS_RVA
    actor=pointer(read,base+0x1C7D3E0)
    index=struct.unpack('<H',read(actor+0x28,2))[0]
    if index>2047:raise ValueError('Invalid actor scene index')
    registry=pointer(read,base+0x1C402D8)
    entry=pointer(read,registry+0x18+index*8)
    owner=pointer(read,entry+0xD8)
    tile=pointer(read,owner+0xB18)
    name=cstring(read,pointer(read,tile+0x68)).lower()
    mapping=json.loads((Path(__file__).parent/'mission_scene_names.json').read_text())
    mission=mapping.get(name)
    manager=pointer(read,base+MISSION_TOKENS_RVA)
    mask=read(manager+0x50,1)[0]
    parts=decode_shield_mask(mask & 15)
    if (pointer(read,base+MISSION_TOKENS_RVA)!=manager or read(manager+0x50,1)[0]!=mask
            or pointer(read,base+0x1C7D3E0)!=actor or struct.unpack('<H',read(actor+0x28,2))[0]!=index):
        raise RuntimeError('Mission shield changed during snapshot')
    return dict(status='read' if mission else 'unresolved_scene',mission=mission,scene=name,
                mask=mask,parts=parts,evidence='native callback 0x6d980; TR live validated')


def shield_locations(mission: str, mode: str) -> tuple[str, ...]:
    if not mission or mode not in ('whole', 'quarters'):
        raise ValueError('Mission and valid shield mode are required')
    if mode == 'whole':
        return (f'{mission}: Police Shield',)
    return tuple(f'{mission}: Police Shield {part}' for part in PARTS)


def completed_shield_locations(mission: str, mode: str, collected_parts) -> tuple[str, ...]:
    collected = set(collected_parts)
    if not collected.issubset(PARTS):
        raise ValueError('Unknown shield part identity')
    locations = shield_locations(mission, mode)
    if mode == 'whole':
        return locations if collected == set(PARTS) else ()
    return tuple(location for part, location in zip(PARTS, locations) if part in collected)
