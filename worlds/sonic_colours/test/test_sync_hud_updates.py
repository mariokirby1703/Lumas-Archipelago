import struct
from types import SimpleNamespace
from ..client import ap_hud_connected as hud, music_popup
from ..client.ap_hud_ticker import Ticker
from .test_ap_hud_connected import Memory


def test_music_fade_does_not_republish_item_payloads(monkeypatch):
    memory=Memory();boxes={'ap_title':(0x90100000,0x90200000),
                          'ap_music_title':(0x90101000,0x90201000)}
    owner={'control':0x90001000,'handle':0x90002000,'layer':0x90003000,
           'boxes':boxes,'anchors':[]}
    for record,box in boxes.values():memory.put(box+12,struct.pack('>I',0x900af000))
    monkeypatch.setattr(hud,'installed',lambda m:True)
    monkeypatch.setattr(hud,'discover',lambda m:owner)
    music={'title':'Track','alpha':255}
    monkeypatch.setattr(music_popup,'update',lambda r:dict(music))
    runtime=SimpleNamespace(slot_data={'options':{}},clock=lambda:1.,
        hud_ticker=Ticker(SimpleNamespace(data={},save=lambda:None)),
        snapshot=SimpleNamespace(scene='global_map',scene_verified=True,session='S',stage_epoch=None))
    hud.render(runtime,memory)
    generation=runtime._hud_connected['pending']['generation']
    for record,box in boxes.values():memory.put(box,struct.pack('>I',generation))
    hud.render(runtime,memory)
    memory.writes=[];music['alpha']=128
    hud.render(runtime,memory)
    assert [a for a,data in memory.writes]==[owner['control']+4,0x90201008,owner['control']+4]
    assert runtime._hud_connected['pending'] is not None  # unchanged casts still require native ACK
