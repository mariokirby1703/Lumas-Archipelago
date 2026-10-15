from types import SimpleNamespace
import struct
from ..client import ap_hud_connected as hud
from ..client.ap_hud_ticker import Ticker

class Memory:
    def __init__(self):self.data={};self.writes=[]
    def verify_revision(self):pass
    def read_bytes(self,a,n):return bytes(self.data.get(a+i,0) for i in range(n))
    def read_u32(self,a):return int.from_bytes(self.read_bytes(a,4),'big')
    def put(self,a,data):self.data.update({a+i:v for i,v in enumerate(data)})
    def write_bytes_verified(self,a,data,expected,operation):
        assert operation=='hud_mailbox' and self._hud_transaction['allowed'][a]==len(data)
        assert self.read_bytes(a,len(data))==expected
        self.writes.append((a,data));self.put(a,data)

def test_long_foreign_item_name_uses_full_native_line_width():
    from ..world_constants import load_data
    name='Quarry Boathouse Ramp Horizontal Control (Panel)'
    owner={'handle':0x90001000,'boxes':{'ap_title':(0x90100000,0x90200000)}}
    result=hud.payloads(owner,[dict(kind='Sent',item=name,player='LumaWitness',flags=1)],load_data('hud_glyph_metrics.json'))
    assert result[0x90200010].split(b'\0')[0].decode('ascii')==name
    assert len(result[0x90200010])==128

def test_own_item_two_lines_and_faded_outline():
    from ..world_constants import load_data
    boxes={'ap_prefix0':(0,0x1000),'ap_title':(0,0x2000),
           'ap_subtitle':(0,0x3000),'ap_subtitle_outline0':(0,0x4000)}
    event=dict(kind='Received',item='Progressive Yellow Drill Wisp',player='Self',own=True,flags=1,alpha=128)
    result=hud.payloads({'handle':0x90001000,'boxes':boxes},[event],load_data('hud_glyph_metrics.json'))
    assert result[0x1010].split(b'\0')[0]==b'Found your own'
    assert result[0x2010].split(b'\0')[0]==b' '
    assert result[0x3010].split(b'\0')[0]==event['item'].encode()
    assert result[0x3090][:4]==bytes.fromhex('af70ff80')
    assert result[0x4090][:4]==bytes.fromhex('00000080')

def test_two_phase_panel_ack_expiry_and_always_enabled(monkeypatch):
    memory=Memory();boxes={};i=0
    for slot in range(5):
        for base in ('ap_prefix'+str(slot),'ap_title'+('_'+str(slot) if slot else ''),'ap_subtitle'+('_'+str(slot) if slot else '')):
            for name in [base+'_outline'+str(j) for j in range(4)]+[base]:
                boxes[name]=(0x90100000+i*0x100,0x90200000+i*0x100);i+=1
    owner={'control':0x90000000,'handle':0x90001000,'layer':0x90002000,'boxes':boxes,'anchors':[],'key':(1,'gameplay')}
    for record,box in boxes.values():memory.put(box+12,struct.pack('>I',0x900af000))
    monkeypatch.setattr(hud,'installed',lambda m:True)
    monkeypatch.setattr(hud,'discover',lambda m:owner)
    wall=[1000.];clock=[0.]
    ticker=Ticker(SimpleNamespace(data={},save=lambda:None),lambda:clock[0],lambda:wall[0])
    event=dict(kind='Received',item='Double Jump',player='P',flags=1)
    ticker.enqueue(event)
    runtime=SimpleNamespace(slot_data={'seed_name':'Fixture','options':{'ap_item_hud':1,'music_randomization':0}},clock=lambda:clock[0],hud_ticker=ticker,
                            snapshot=SimpleNamespace(scene='gameplay',scene_verified=True,session='S',stage_epoch='A'))
    hud.render(runtime,memory)
    pending=runtime._hud_connected['pending']
    assert memory.writes[0]==(owner['control']+4,struct.pack('>I',1))
    assert memory.writes[-1]==(owner['control']+4,struct.pack('>I',2))
    assert len(memory.writes)<=77
    assert all(len(blob)==144 for address,blob in memory.writes[1:-1])
    assert all(memory.read_u32(box+12)==0x900af000 for record,box in boxes.values())
    assert ticker.data['current'] is None and ticker.data['queue']==[event]
    waiting=hud.render(runtime,memory)
    assert waiting['status']=='waiting for game-thread ACK'
    assert ticker.data['queue']==[event]
    for record,box in boxes.values():memory.put(box,struct.pack('>I',pending['generation']))
    assert hud.render(runtime,memory)['publisher_ack']
    assert ticker.data['current']==event and not ticker.data['queue']
    title=boxes['ap_title'][1]
    assert memory.read_bytes(title+16,128).split(b'\0')[0]==b'Double Jump'
    assert memory.read_u32(title+144)==0xaf70ffff
    wall[0]+=120;hud.render(runtime,memory)
    assert runtime._hud_connected['pending']['events']==[]
    assert ticker.data['display_times']==[1000.]
    for record,box in boxes.values():memory.put(box,struct.pack('>I',runtime._hud_connected['pending']['generation']))
    runtime._hud_enabled_override=False
    runtime.slot_data['options']['ap_item_hud']=0
    ticker.data['enabled_override']=False
    assert hud.render(runtime,memory)['hud_ready']

def test_missing_publisher_does_not_consume(monkeypatch):
    ticker=Ticker(SimpleNamespace(data={},save=lambda:None))
    event=dict(kind='Sent',item='Test',player='P');ticker.enqueue(event)
    runtime=SimpleNamespace(slot_data={'options':{'ap_item_hud':1}},hud_ticker=ticker,
                            snapshot=SimpleNamespace(scene='global_map',scene_verified=True))
    monkeypatch.setattr(hud,'installed',lambda m:False)
    assert not hud.render(runtime,Memory())['hud_ready']
    assert ticker.data['queue']==[event] and ticker.data['current'] is None

def test_discovery_does_not_scan_non_hud_actor_fields(monkeypatch):
    import pytest
    from ..client.memory import MemoryUnavailable
    monkeypatch.setattr(hud,'read_stage_objects',lambda m,p:[dict(scene='gameplay',context=1)])
    monkeypatch.setattr(hud,'read_actors',lambda m,c:range(1000,2000))
    class NonHUD:
        def read_u32(self,a):return 0x80750000
        def read_bytes(self,a,n):raise AssertionError('non-HUD actor pointer scan')
    with pytest.raises(MemoryUnavailable,match='not uniquely resolved'):hud.discover(NonHUD())

def test_area_map_owner_is_not_excluded_by_gameplay_class_filter(monkeypatch):
    import pytest
    from ..client.memory import MemoryUnavailable
    monkeypatch.setattr(hud,'read_stage_objects',lambda m,p:[dict(scene='world_map',context=1)])
    monkeypatch.setattr(hud,'read_actors',lambda m,c:[0x90001000])
    reads=[]
    class MapOwner:
        def read_u32(self,a):return 0x80777100
        def read_bytes(self,a,n):reads.append((a,n));return bytes(n)
    with pytest.raises(MemoryUnavailable,match='not uniquely resolved'):hud.discover(MapOwner())
    assert reads==[(0x90001000,0x480)]


def test_music_right_alignment_and_independent_fade():
    from ..world_constants import load_data
    metrics=load_data('hud_glyph_metrics.json')
    boxes={'ap_music_title':(0,0x1000),'ap_music_title_outline0':(0,0x2000),'ap_title':(0,0x3000)}
    event=dict(kind='Received',item='Double Jump',player='P',flags=1,alpha=255)
    result=hud.payloads({'handle':0x90001000,'boxes':boxes},[event],metrics,{'alpha':64,'title':'Test Song'})
    colour,x=struct.unpack('>If',result[0x1090])
    assert abs(x+sum(metrics[c] for c in 'Test Song')-590.)<0.001
    assert colour==0xffffff40
    assert result[0x2090][:4]==bytes.fromhex('00000040')
    assert result[0x3090][:4]==bytes.fromhex('af70ffff')
