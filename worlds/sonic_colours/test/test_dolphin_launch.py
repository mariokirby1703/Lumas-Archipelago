from types import SimpleNamespace
import pytest
from ..client import dolphin_launch as d


def test_first_selection_is_saved_and_reused_without_second_dialog(tmp_path,monkeypatch):
    import Utils,settings
    executable=tmp_path/'Dolphin.exe';executable.write_bytes(b'test')
    group=SimpleNamespace(dolphin_path='',auto_start=False);calls=[];saved=[]
    monkeypatch.setattr(Utils,'open_filename',lambda *a:(calls.append(a) or str(executable)))
    monkeypatch.setattr(settings,'get_settings',lambda:SimpleNamespace(save=lambda:saved.append(True)))
    assert d.select_executable(group)==executable
    assert group.auto_start
    group.auto_start=False
    assert d.select_executable(group)==executable
    assert not group.auto_start
    assert len(calls)==1 and saved


def test_cancel_is_optional_and_headless_missing_path_is_explicit(monkeypatch):
    import Utils
    monkeypatch.setattr(Utils,'open_filename',lambda *a:None)
    assert d.select_executable(SimpleNamespace(dolphin_path='')) is None
    with pytest.raises(ValueError,match='--dolphin'):d.select_executable(SimpleNamespace(dolphin_path=''),gui=False)


def test_start_uses_argument_list_and_exact_iso_path(monkeypatch):
    calls=[]
    monkeypatch.setattr(d,'running_processes',lambda:[])
    monkeypatch.setattr(d.subprocess,'Popen',lambda args,**kw:(calls.append((args,kw)) or SimpleNamespace(pid=10)))
    result=d.start_or_reuse('Dolphin.exe','Game with spaces.iso')
    assert result['started'] and calls[0][0]==['Dolphin.exe','--exec','Game with spaces.iso']


def test_existing_instance_closes_before_launching_exact_new_iso(monkeypatch):
    state=[dict(pid=25)];calls=[]
    monkeypatch.setattr(d,'running_processes',lambda:list(state))
    def close(pid):
        calls.append(('close',pid));state.clear()
    monkeypatch.setattr(d,'close_existing',close)
    def start(args,**kw):
        assert not state
        calls.append(('start',args));return SimpleNamespace(pid=26)
    monkeypatch.setattr(d.subprocess,'Popen',start)
    result=d.start_or_reuse('Dolphin.exe','new.iso')
    assert result['started'] and result['restarted'] and not result['reused']
    assert calls==[('close',25),('start',['Dolphin.exe','--exec','new.iso'])]


def test_cancelled_close_never_launches_second_instance(monkeypatch):
    monkeypatch.setattr(d,'running_processes',lambda:[dict(pid=25)])
    requests=[]
    monkeypatch.setattr(d,'request_close',requests.append)
    close=d.close_existing
    monkeypatch.setattr(d,'close_existing',lambda pid:close(pid,timeout=0))
    monkeypatch.setattr(d.subprocess,'Popen',lambda *a,**kw:pytest.fail('second Dolphin started'))
    with pytest.raises(ValueError,match='not closed'):
        d.start_or_reuse('Dolphin.exe','new.iso')
    assert requests==[25]


def test_graceful_close_waits_for_process_exit_and_refuses_another_instance(monkeypatch):
    monkeypatch.setattr(d,'request_close',lambda pid:None)
    states=iter([[dict(pid=25)],[]])
    monkeypatch.setattr(d,'running_processes',lambda:next(states))
    monkeypatch.setattr(d.time,'sleep',lambda _:None)
    d.close_existing(25)
    monkeypatch.setattr(d,'running_processes',lambda:[dict(pid=26)])
    with pytest.raises(ValueError,match='Another Dolphin'):
        d.close_existing(25)



def test_multiple_instances_refuse_automatic_launch(monkeypatch):
    monkeypatch.setattr(d,'running_processes',lambda:[dict(pid=25),dict(pid=26)])
    with pytest.raises(ValueError,match='Multiple'):d.start_or_reuse('Dolphin.exe','new.iso')


def test_installer_uses_registered_world_settings_key(monkeypatch):
    import settings
    from ..world import SonicColoursWorld
    from ..client.iso_patch import settings_group
    group=object()
    monkeypatch.setattr(settings,'get_settings',lambda:{SonicColoursWorld.settings_key:group})
    assert settings_group() is group

