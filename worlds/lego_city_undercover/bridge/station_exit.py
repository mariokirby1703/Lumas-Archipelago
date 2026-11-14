"""Read-only identification/arming of the existing station exterior and lift doors."""
import math
import struct
from inventory_reader import pointer,cstring
from scene_reader import player_scene

DOOR_NAME='POLICE_LOBBY_EXTERNAL_DOOR'
DOOR_ROUTES={
    'POLICE_STATION_LOBBY':(DOOR_NAME,(0.0,0.0,0.0)),
    'POLICE_STATION_GARAGE':('POLICE_GARAGE_DOOR',(-0.6,0.0,0.0)),
}
EXIT_RADIUS=0.8
ARM_DISTANCE=2.0

def read_station_exit(read,base):
    scene=player_scene(read,base);actor=scene['actor']
    registry=pointer(read,base+0x1c402d8)
    index=struct.unpack('<H',read(actor+0x28,2))[0]
    owner=pointer(read,pointer(read,registry+0x18+index*8)+0xd8)
    tile=pointer(read,owner+0xb18)
    scene_name=cstring(read,pointer(read,tile+0x68)).upper()
    if scene_name not in DOOR_ROUTES:return None
    door_name,offset=DOOR_ROUTES[scene_name]
    if scene_name=='POLICE_STATION_GARAGE':
        bank=pointer(read,base+0x1c7cbb8)
        if not bank:raise ValueError('Character bank unavailable')
        if read(bank+0x80+227,1)!=b'\0':return None
    manager=pointer(read,scene['table']+18*8)
    if not manager or pointer(read,manager)!=base+0xd603f8:raise ValueError('Unsupported lobby door manager')
    node=pointer(read,manager+0xe0);seen=set();matches=[]
    while node:
        if node in seen or len(seen)>=64:raise ValueError('Invalid lobby door list')
        seen.add(node);raw=read(node,0x90)
        if struct.unpack_from('<Q',raw)[0]!=base+0xd5fc98:raise ValueError('Unsupported lobby door instance')
        if struct.unpack_from('<Q',raw,0x48)[0]!=manager:raise ValueError('Unexpected lobby door owner')
        if raw[0x58:0x78].split(b'\0')[0].decode('ascii')==door_name:
            matches.append((node,struct.unpack_from('<3f',raw,0x78)))
        node=struct.unpack_from('<Q',raw,0x28)[0]
    if len(matches)!=1:raise ValueError('No unique lobby exterior door')
    position=struct.unpack('<3f',read(actor+0x1f0,12));door,at=matches[0]
    if not all(math.isfinite(x) for x in (*position,*at)):raise ValueError('Invalid lobby exit transform')
    if pointer(read,base+0x1c7d3e0)!=actor:raise RuntimeError('Player changed during exit probe')
    center=tuple(b+c for b,c in zip(at,offset))
    return dict(owner=owner,door=door,scene=scene_name,door_name=door_name,
                distance_squared=sum((a-b)**2 for a,b in zip(position,center)))

class StationExitGate:
    def __init__(self):self.identity=None;self.armed=False;self.triggered=False
    def update(self,pid,probe,context):
        identity=(pid,probe['owner']) if probe else None
        if identity!=self.identity:
            self.identity=identity;self.armed=False;self.triggered=False
        if not probe or context!=46 or self.triggered:return False
        distance=probe['distance_squared']
        if distance>ARM_DISTANCE**2:self.armed=True
        return self.armed and distance<=EXIT_RADIUS**2
    def mark_triggered(self):self.triggered=True


def can_resume_first_lobby(story):
    jobs=story.get('jobs',{})
    act=jobs.get('Flow_Setup.Act_1',{})
    lobby=jobs.get('Flow_Setup.Act_1.LCPD.LCPD_Level.LCPD_Lobby',{})
    return (jobs.get('PDA',{}).get('acquired') is False and
            jobs.get('Flow_Setup',{}).get('Flow_Act')==1 and
            act.get('Act1_Mission')==1 and act.get('Act1_Stage')==2 and
            type(lobby.get('LCPD_MainframeActive')) is bool and
            type(lobby.get('LCPD_LobbyEntered')) is int and
            (lobby['LCPD_LobbyEntered']==1 or
             (lobby['LCPD_LobbyEntered']==2 and not lobby['LCPD_MainframeActive'])))


def read_lobby_lift(read,base):
    scene=player_scene(read,base);actor=scene['actor']
    registry=pointer(read,base+0x1c402d8);index=struct.unpack('<H',read(actor+0x28,2))[0]
    owner=pointer(read,pointer(read,registry+0x18+index*8)+0xd8)
    tile=pointer(read,owner+0xb18)
    if cstring(read,pointer(read,tile+0x68)).upper()!='POLICE_STATION_LOBBY':return None
    manager=pointer(read,scene['table']+8)
    if pointer(read,manager)!=base+0xc2e468:raise ValueError('Unsupported lobby obstacle manager')
    node=pointer(read,manager+0xe0);seen=set();opening=[];closing=[]
    while node:
        if node in seen or len(seen)>=256:raise ValueError('Invalid lobby obstacle list')
        seen.add(node);raw=read(node,0x90)
        if struct.unpack_from('<Q',raw)[0]!=base+0xc2dec8 or struct.unpack_from('<Q',raw,0x48)[0]!=manager:
            raise ValueError('Unsupported lobby obstacle instance')
        name=raw[0x58:0x78].split(b'\0')[0]
        if name==b'DoorsOpening':opening.append((node,struct.unpack_from('<3f',raw,0x78)))
        if name==b'DoorsClosing':closing.append(node)
        node=struct.unpack_from('<Q',raw,0x28)[0]
    if len(opening)!=1 or len(closing)!=1:raise ValueError('No unique lobby lift animation pair')
    position=struct.unpack('<3f',read(actor+0x1f0,12));at=opening[0][1]
    if not all(math.isfinite(v) for v in (*position,*at)):raise ValueError('Invalid lift transform')
    return dict(owner=owner,distance_squared=sum((a-b)**2 for a,b in zip(position,at)))
