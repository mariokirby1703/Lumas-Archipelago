import json
from types import SimpleNamespace
from ..client import client


def test_large_diagnostic_preserves_every_character_in_bounded_gui_records(monkeypatch):
    messages=[]
    monkeypatch.setattr(client.logger,'info',messages.append)
    value={'native_evidence':{str(i):{'rank':255,'path':'C:\\Sonic\\'+str(i)} for i in range(150)},
           'long_string':'ä'*5000}
    client.log_diagnostic(value)
    assert len(messages)>1
    assert all(len(m)<=1800 and m.count('\n')<=12 for m in messages)
    assert ''.join(messages)==json.dumps(value,indent=2)


def test_status_remains_readable_after_runtime_reconnect(monkeypatch):
    messages=[]
    monkeypatch.setattr(client.logger,'info',messages.append)
    monkeypatch.setattr(client,'diagnostic',lambda ctx: {'connected':ctx.runtime is not None,
        'history':[{'index':i} for i in range(100)]})
    ctx=SimpleNamespace(runtime=None)
    command=client.SonicCommands(ctx)
    command('/sonicstatus')
    assert json.loads(''.join(messages))['connected'] is False
    messages.clear();ctx.runtime=object()
    command('/sonicstatus')
    assert json.loads(''.join(messages))['connected'] is True
    assert all(m.count('\n')<=12 for m in messages)
