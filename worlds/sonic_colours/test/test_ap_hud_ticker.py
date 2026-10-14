from types import SimpleNamespace
from ..client.ap_hud_ticker import Ticker,ascii_text,fit_text
from NetUtils import NetworkItem

def ticker(clock=lambda:0):
    return Ticker(SimpleNamespace(data={},save=lambda:None),clock)

def test_received_history_and_reconnect():
    t=ticker();items=[NetworkItem(1,10,2,0)]
    t.received(items,0,str,str);assert t.data['queue']==[]
    t.received(items+[NetworkItem(2,11,3,0)],0,str,str)
    assert [e['item'] for e in t.data['queue']]==['2']
    Ticker(t.journal).received(items+[NetworkItem(2,11,3,0)],0,str,str)
    assert len(t.data['queue'])==1

def test_sent_uses_recipient_lookup_and_deduplicates():
    t=ticker();calls=[]
    lookup=lambda i,s:(calls.append((i,s)) or 'Foreign Item')
    args=dict(type='ItemSend',item=NetworkItem(77,123,1,0),receiving=2)
    t.sent(args,0,1,lookup,str);t.sent(args,0,1,lookup,str)
    assert calls==[(77,2)] and len(t.data['queue'])==1
    t.sent({**args,'receiving':1},0,1,lookup,str)
    t.sent({**args,'item':[77,123,3,0]},0,1,lookup,str)
    assert len(t.data['queue'])==1

def test_fifo_dwell_pause_and_persistent_last():
    clock=[0];t=ticker(lambda:clock[0])
    for i in range(3):t.enqueue(dict(kind='Sent',item=str(i),player='P'))
    assert t.tick(True)['item']=='0'
    clock[0]=4;assert t.tick(True)['item']=='0'
    t.tick(False);clock[0]=100;assert t.tick(True)['item']=='0'
    clock[0]=102;assert t.tick(True)['item']=='1'
    clock[0]=107;assert t.tick(True)['item']=='2'
    clock[0]=1000;assert t.tick(True)['item']=='2'

def test_encoding_capacity_and_overflow():
    assert ascii_text('Gr\u00fcn \U0001f600')=='Gruen ?'
    assert fit_text('Received Item',16,{c:8 for c in 'Received Item'},3)=='Re'
    t=ticker()
    for i in range(40):t.enqueue(dict(kind='Received',item=str(i),player='P'))
    assert len(t.data['queue'])==32 and t.data['overflow']==8
    assert not t.diagnostics(True)['hud_ready']
