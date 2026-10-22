from ..client.patch_progress import PatchProgress


def test_progress_window_initializes_and_uses_worker_instead_of_silent_fallback(monkeypatch):
    import sys
    import threading
    from types import SimpleNamespace
    from ..client import iso_patch
    widgets=[];roots=[];calls=[]
    class Widget:
        def __init__(self,*args,**kwargs):self.values=kwargs;widgets.append(self)
        def pack(self,**kwargs):pass
        def config(self,**kwargs):self.values.update(kwargs)
        def start(self):pass
    class Root:
        def __init__(self):roots.append(self);self.closed=False
        def title(self,text):self.title_text=text
        def protocol(self,*args):pass
        def destroy(self):self.closed=True
        def mainloop(self):pass
    class Thread:
        def __init__(self,target,**kwargs):self.target=target
        def start(self):self.target()
        def is_alive(self):return False
        def join(self):pass
    ttk=SimpleNamespace(Label=Widget,Progressbar=Widget,Button=Widget)
    monkeypatch.setitem(sys.modules,'tkinter',SimpleNamespace(Tk=Root,ttk=ttk))
    monkeypatch.setattr(threading,'Thread',Thread)
    def install(patch,**kwargs):
        calls.append(kwargs)
        kwargs['progress']('Building all native AP hooks and patch handshake')
        return 'patched.iso'
    monkeypatch.setattr(iso_patch,'install',install)
    assert iso_patch.install_with_progress(object(),source='original.iso')=='patched.iso'
    assert len(calls)==1 and 'cancel' in calls[0] and roots[0].closed
    assert any(w.values.get('text')=='Adding Archipelago support…' for w in widgets)


def test_log_noise_never_replaces_phase_or_exposes_local_paths():
    p=PatchProgress()
    p.receive('Building gameplay, maps, Game Land HUD and seed music together')
    text=p.message
    p.receive('WIT VERSION: wit: Wiimms ISO Tool v3.05a r8638')
    p.receive('Checking C:/Users/Luma/private/game.iso: 40/100 MiB')
    assert p.message==text and p.detail=='40/100 MiB'


def test_step_eta_clears_on_phase_change_instead_of_becoming_total_eta():
    p=PatchProgress()
    p.receive('Rebuilding Wii filesystem, encrypted DATA partition and hashes')
    p.receive('WIT COPY: 32% copied in 0:06 (202 MiB/sec) -> ETA 0:12')
    assert p.detail=='32% of this step · Estimated time left for this step: 0:12'
    p.receive('Verifying generated Wii partition integrity')
    assert not p.detail and p.message=='Checking the new ISO…'
    assert p.timing(65)=='Elapsed: 1:05'


def test_queued_phase_and_following_output_keep_useful_status():
    p=PatchProgress()
    for line in ('Validating original ISO and cached output',
                 'Checking source.iso: 800/4482 MiB',
                 'WIT VERSION: banner',
                 'Checking/copying cached original partition: 503/3641 MiB'):
        p.receive(line)
    assert p.message=='Loading the saved original game files…'
    assert p.detail=='503/3641 MiB'
    p.receive('Building all native AP hooks and patch handshake')
    assert not p.detail
