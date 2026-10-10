import json
from types import SimpleNamespace
from ..client import client


def test_large_diagnostic_is_one_copyable_record_without_data_loss(monkeypatch):
    messages=[]
    monkeypatch.setattr(client.logger,'info',messages.append)
    value={'native_evidence':{str(i):{'rank':255,'path':'C:\\Sonic\\'+str(i)} for i in range(150)},
           'long_string':'ä'*5000}
    client.log_diagnostic(value)
    assert len(messages)==1
    assert json.loads(messages[0])==value
    assert messages[0].count('\n')==len(value)+1


def test_status_remains_readable_after_runtime_reconnect(monkeypatch):
    messages=[]
    monkeypatch.setattr(client.logger,'info',messages.append)
    monkeypatch.setattr(client,'diagnostic',lambda ctx: {'connected':ctx.runtime is not None,
        'native_evidence':{'rank_records':{str(i):{'rank':255} for i in range(100)}},
        'item_receipts':[{'index':i} for i in range(100)]})
    ctx=SimpleNamespace(runtime=None)
    command=client.SonicCommands(ctx)
    command('/sonicstatus')
    assert json.loads(''.join(messages))['connected'] is False
    messages.clear();ctx.runtime=object()
    command('/sonicstatus')
    assert json.loads(''.join(messages))['connected'] is True
    assert len(messages)==1
    status=json.loads(messages[0])
    assert 'native_evidence' not in status and 'item_receipts' not in status
    assert status['native_evidence_command']=='/sonicdebug'
    assert status['item_receipt_count']==100 and status['item_receipts_command']=='/sonicitems'


def test_debug_retains_full_native_evidence_in_one_record(monkeypatch):
    messages=[]
    monkeypatch.setattr(client.logger,'info',messages.append)
    value={'native_evidence':{'rank_records':{'stg110':{'rank':255}}}}
    monkeypatch.setattr(client,'diagnostic',lambda *args:value)
    command=client.SonicCommands(SimpleNamespace(memory=None))
    command('/sonicdebug')
    assert len(messages)==1 and json.loads(messages[0])==value
