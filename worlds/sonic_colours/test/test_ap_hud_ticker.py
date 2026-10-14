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

def test_empty_history_barrier_does_not_swallow_first_self_item():
    t=ticker();t.history_ready([])
    item=NetworkItem(77,123,1,1)
    t.received([item],0,str,lambda p:'Self')
    assert t.data['queue']==[dict(kind='Received',item='77',player='Self',receipt=0,flags=1)]
    t.history_ready([item]);t.received([item],0,str,str)
    assert len(t.data['queue'])==1

def test_history_barrier_preserves_existing_silent_baseline():
    t=ticker();items=[NetworkItem(1,10,2,0)]
    t.history_ready(items);t.received(items,0,str,str)
    assert t.data['queue']==[]
    t.received([NetworkItem(2,11,1,0)],1,str,str)
    assert [e['item'] for e in t.data['queue']]==['2']

def test_own_receipt_and_fade_before_expiry():
    wall=[1000.]
    t=Ticker(SimpleNamespace(data={},save=lambda:None),wall_clock=lambda:wall[0])
    t.history_ready([])
    t.received([NetworkItem(77,123,1,1)],0,str,str,slot=1)
    assert t.data['queue'][0]['own']
    t.published(t.candidate())
    wall[0]+=50;assert t.panel_events()[0].get('alpha',255)==255
    wall[0]+=5;assert t.panel_events()[0]['alpha']==128
    wall[0]+=5;assert t.panel_events()[0]['alpha']==0
    wall[0]+=5;assert t.panel_events()==[]

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

def test_publication_waits_for_matching_ack_and_visible_dwell():
    clock=[0];t=ticker(lambda:clock[0])
    first=dict(kind='Received',item='One',player='P')
    second=dict(kind='Received',item='Two',player='P')
    t.enqueue(first);t.enqueue(second)
    clock[0]=100;t.elapsed_visible(False)
    assert t.candidate()==first and t.data['current'] is None
    assert not t.published(second) and len(t.data['queue'])==2
    assert t.published(first)
    clock[0]=104;t.elapsed_visible(True)
    assert t.candidate()==first
    t.elapsed_visible(False);clock[0]=200;t.elapsed_visible(True)
    assert t.candidate()==first
    clock[0]=201;t.elapsed_visible(True)
    assert t.candidate()==second and t.data['current']==first
    clock[0]=300;t.elapsed_visible(False)
    assert t.data['current']==first and len(t.data['queue'])==1
    assert t.published(second) and t.remaining==5
    assert Ticker(t.journal).candidate()==second

def test_five_message_panel_commits_history_only_on_ack():
    clock=[0];t=ticker(lambda:clock[0])
    for i in range(7):t.enqueue(dict(kind='Sent' if i%2 else 'Received',item=str(i),player='P'))
    assert t.panel_candidate()==[['Received 0','from P']]
    assert t.data['display_history']==[]
    for i in range(7):
        assert t.published(t.candidate())
        clock[0]+=5;t.elapsed_visible(True)
    assert len(t.data['display_history'])==5
    assert t.panel_candidate()[0]==['Received 6','from P']
    assert t.panel_candidate()[-1]==['Received 2','from P']
    assert Ticker(t.journal).panel_candidate()==t.panel_candidate()

def test_panel_expires_after_one_minute_without_restarting_on_reconnect():
    wall=[1000.];clock=[0.]
    t=Ticker(SimpleNamespace(data={},save=lambda:None),lambda:clock[0],lambda:wall[0])
    t.enqueue(dict(kind='Received',item='Test',player='P',flags=1))
    assert t.published(t.candidate())
    wall[0]+=59;assert t.panel_candidate()==[['Received Test','from P']]
    resumed=Ticker(t.journal,lambda:clock[0],lambda:wall[0])
    wall[0]+=1;assert resumed.panel_candidate()==[]

def test_ap_classification_colours():
    from ..client.ap_hud_ticker import item_colour
    assert [item_colour(f) for f in (1,2,0,4)]==['#AF70FF','#305BD8','#64C8FF','#F05252']
    assert item_colour(3)==item_colour(1)
