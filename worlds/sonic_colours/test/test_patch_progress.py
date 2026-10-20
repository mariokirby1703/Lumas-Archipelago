from ..client.patch_progress import PatchProgress


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
