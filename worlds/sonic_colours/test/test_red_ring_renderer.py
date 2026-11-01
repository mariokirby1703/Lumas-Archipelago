from types import SimpleNamespace

import pytest

from ..client import red_ring_renderer as module
from ..client.red_ring_colors import RedRingColors
from ..client.memory import MemoryUnavailable
from .test_red_ring_colors import data_for


def setup(monkeypatch):
    clock = [100.]
    monkeypatch.setattr(module.time, 'monotonic', lambda: clock[0])
    colors = RedRingColors(data_for(), 1, 0)
    rows = [dict(ring=n, mission='stg110', context=1, actor=100+n, model=200+n,
                 resource=300, registers=400+n, stages=500+n) for n in (1, 2)]
    scans, writes = [], []
    monkeypatch.setattr(module, 'inspect', lambda memory,**kwargs: scans.append(True) or list(rows))
    monkeypatch.setattr(module, 'apply', lambda memory,row,color,**kw:
                        writes.append((row['ring'],color,kw['operation'])))
    snapshot = SimpleNamespace(scene='gameplay',scene_verified=True,death_state='alive',
                               session='session',stage_epoch='epoch',actual_mission='stg110',
                               evidence={'native_data':{'stage_objects':[{'red_ring_actors':[101,102]}]}})
    memory = SimpleNamespace(native_patch={'red_ring_materials':True})
    guard = SimpleNamespace(check_visual=lambda snapshot: None)
    return colors, rows, snapshot, memory, guard, clock, scans, writes


def test_late_scouts_independent_rings_and_no_repeated_writes(monkeypatch):
    colors, rows, snap, memory, guard, clock, scans, writes = setup(monkeypatch)
    render = colors.renderer
    render.poll(memory,snap,guard,colors)
    assert writes == [(1,'red','red_ring_material')]
    writes.clear()
    colors.receive([(1,colors.locations['stg110',1],2,1),
                    (2,colors.locations['stg110',2],2,2)])
    render.poll(memory,snap,guard,colors)
    render.poll(memory,snap,guard,colors)
    assert writes == [(1,'purple_shaded','red_ring_material'),(2,'blue_shaded','red_ring_material')]
    for _ in range(20):
        render.poll(memory,snap,guard,colors)
    assert len(scans) == 1 and len(writes) == 2
    clock[0] += .5
    render.poll(memory,snap,guard,colors)
    assert len(scans) == 2 and len(writes) == 2
    assert memory._red_ring_color_source is None


def test_respawn_recolors_even_if_native_reuses_addresses(monkeypatch):
    colors, rows, snap, memory, guard, clock, scans, writes = setup(monkeypatch)
    colors.receive([(1,colors.locations['stg110',1],2,1)])
    colors.renderer.poll(memory,snap,guard,colors)
    snap.death_state = 'dead'
    colors.renderer.poll(memory,snap,guard,colors)
    snap.death_state = 'alive'
    colors.renderer.poll(memory,snap,guard,colors)
    assert len(writes) == 2


@pytest.mark.parametrize('scene', ('global_map','results','game_land_select','title'))
def test_other_scenes_never_discover_or_write_materials(monkeypatch,scene):
    colors, rows, snap, memory, guard, clock, scans, writes = setup(monkeypatch)
    snap.scene = scene
    colors.renderer.poll(memory,snap,guard,colors)
    assert not scans and not writes


def test_old_iso_fails_closed_without_discovery(monkeypatch):
    colors, rows, snap, memory, guard, clock, scans, writes = setup(monkeypatch)
    memory.native_patch = {'red_ring_materials':False}
    colors.renderer.poll(memory,snap,guard,colors)
    assert not scans and not writes
    assert 'repatch' in colors.renderer.status['reason']


def test_changed_owner_retries_without_marking_applied(monkeypatch):
    colors, rows, snap, memory, guard, clock, scans, writes = setup(monkeypatch)
    colors.receive([(1,colors.locations['stg110',1],2,1)])
    def fail(*args,**kwargs):
        raise MemoryUnavailable('owner changed')
    monkeypatch.setattr(module,'apply',fail)
    colors.renderer.poll(memory,snap,guard,colors)
    assert not colors.renderer.applied
    assert memory._red_ring_color_source is None
    assert not colors.renderer.status['native_rendering']


def test_reconnect_restores_unknown_ring_until_scouts_arrive(monkeypatch):
    colors, rows, snap, memory, guard, clock, scans, writes = setup(monkeypatch)
    # A replacement reward cache cannot assume the actor is still vanilla:
    # its previous authenticated connection may already have colored it.
    colors.renderer.poll(memory,snap,guard,colors)
    colors.renderer.poll(memory,snap,guard,colors)
    assert writes == [(1,'red','red_ring_material'),(2,'red','red_ring_material')]


def test_no_actor_evidence_never_falls_back_to_extra_world_scan(monkeypatch):
    colors, rows, snap, memory, guard, clock, scans, writes = setup(monkeypatch)
    snap.evidence = {}
    colors.renderer.poll(memory,snap,guard,colors)
    assert not scans and not writes


def test_loaded_rings_finish_in_one_cycle_with_network_yields(monkeypatch):
    colors, rows, snap, memory, guard, clock, scans, writes = setup(monkeypatch)
    colors.receive([(1,colors.locations['stg110',1],2,1),
                    (2,colors.locations['stg110',2],2,2)])
    steps = colors.renderer.poll_steps(memory,snap,guard,colors)
    assert next(steps) == (set(),False)
    assert writes == [(1,'purple_shaded','red_ring_material')]
    assert next(steps) == (set(),False)
    assert writes[-1] == (2,'blue_shaded','red_ring_material')
    with pytest.raises(StopIteration):
        next(steps)
    assert len(scans) == 1


def test_visual_guard_does_not_wait_for_stats_or_save_binding():
    from ..client.state import SaveGuard
    guard = SaveGuard(SimpleNamespace(data={'save_identity':None}))
    snap = SimpleNamespace(scene='gameplay',scene_verified=True,death_state='alive',
                           stage_epoch='epoch',actual_mission='stg110',session='session',stable_polls=1)
    assert guard.check_visual(snap) == ('session','epoch','stg110')
    snap.stable_polls = 0
    with pytest.raises(MemoryUnavailable):
        guard.check_visual(snap)
