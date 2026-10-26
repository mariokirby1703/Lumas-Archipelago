import io
import subprocess

import pytest
import ModuleUpdate


def test_ci_never_waits_for_dependency_confirmation(monkeypatch):
    monkeypatch.setenv('CI','true')
    monkeypatch.setattr('builtins.input',lambda *_:pytest.fail('CI tried to read input'))
    with pytest.raises(RuntimeError,match='--yes'):ModuleUpdate.confirm('Install dependency')


def test_redirected_input_never_prompts(monkeypatch):
    monkeypatch.delenv('CI',raising=False)
    monkeypatch.setattr(ModuleUpdate.sys,'stdin',io.StringIO())
    with pytest.raises(RuntimeError,match='non-interactive'):ModuleUpdate.confirm('Install dependency')


def test_failed_pip_install_is_not_ignored(monkeypatch):
    monkeypatch.setattr(ModuleUpdate,'check_pip',lambda:None)
    monkeypatch.setattr(ModuleUpdate,'requirements_files',{'test-requirements.txt'})
    def fail(command):raise subprocess.CalledProcessError(1,command)
    monkeypatch.setattr(ModuleUpdate.subprocess,'check_call',fail)
    with pytest.raises(subprocess.CalledProcessError):ModuleUpdate.update_command()


def test_explicit_yes_force_installs_without_confirmation(monkeypatch):
    monkeypatch.setattr(ModuleUpdate,'update_ran',False)
    monkeypatch.setattr(ModuleUpdate,'install_pkg_resources',lambda **_:None)
    monkeypatch.setattr(ModuleUpdate,'confirm',lambda *_:pytest.fail('Unexpected confirmation'))
    calls=[]
    monkeypatch.setattr(ModuleUpdate,'update_command',lambda:calls.append(True))
    ModuleUpdate.update(yes=True,force=True)
    assert calls==[True]
