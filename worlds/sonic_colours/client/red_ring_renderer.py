"""Apply scouted colors to independently owned ring materials."""
import time

from .memory import MemoryUnavailable
from .red_ring_render_test import apply, inspect


class RingRenderer:
    def __init__(self):
        self.epoch = None
        self.next_scan = 0
        self.rows = []
        self.applied = {}
        self.status = {'native_rendering': False, 'reason': 'waiting for an Act'}

    def poll(self, memory, snapshot, guard, colors):
        if (getattr(memory,'native_patch',None) or {}).get('red_ring_spawn'):
            if colors.options.get('colorblind_mode') and not memory.native_patch.get('accessible_ring_colors',False):
                self.status={'native_rendering':False,'reason':'Repatch ISO for Colorblind Mode ring colors'}
                return False
            from .red_ring_spawn import layout
            generation=memory.read_u32(layout()[0]+4)
            ready=bool(generation and not generation&1)
            self.status={'native_rendering':ready,
                         'reason':'native model creation; no delayed model writes' if ready else 'waiting for native palette publication',
                         'mode':'spawn','palette_generation':generation}
            return False
        if snapshot.scene != 'gameplay' or not snapshot.scene_verified or snapshot.death_state != 'alive':
            self.epoch = None
            self.rows = []
            self.applied.clear()
            self.status = {'native_rendering': False, 'reason': 'outside a normal Act'}
            return
        epoch = (snapshot.session, snapshot.stage_epoch, snapshot.actual_mission)
        if epoch != self.epoch:
            self.epoch = epoch
            self.next_scan = 0
            self.rows = []
            self.applied.clear()
        if not colors.enabled or not any(mission == snapshot.actual_mission for mission, ring in colors.locations):
            return
        if not (getattr(memory, 'native_patch', None) or {}).get('red_ring_materials'):
            self.status = {'native_rendering': False, 'reason': 'repatch ISO for Red Ring colors'}
            return
        now = time.monotonic()
        try:
            guard.check_visual(snapshot)
            if now >= self.next_scan:
                self.next_scan = now + .5
                stage = next(iter(snapshot.evidence.get('native_data',{}).get('stage_objects',[])),{})
                if 'red_ring_actors' not in stage:
                    self.status = {'native_rendering':False,'reason':'waiting for current ring actors'}
                    return
                self.rows = inspect(memory,stage=stage,actors=stage['red_ring_actors'],verify=False)
                active = {self.key(row) for row in self.rows}
                self.applied = {key: color for key, color in self.applied.items() if key in active}
            targets = colors.stage_colors(snapshot.actual_mission)
            changed = False
            for row in self.rows:
                if row['mission'] != snapshot.actual_mission:
                    continue
                color = targets[row['ring']-1]
                key = self.key(row)
                previous = self.applied.get(key)
                if previous == color:
                    continue
                memory._red_ring_color_source = colors
                memory._red_ring_visual_snapshot = snapshot
                memory._red_ring_visual_rows = self.rows
                try:
                    apply(memory, row, color + '_shaded' if color != 'red' else 'red',
                          operation='red_ring_material')
                finally:
                    memory._red_ring_color_source = None
                    memory._red_ring_visual_snapshot = None
                    memory._red_ring_visual_rows = None
                self.applied[key] = color
                changed = True
                # The caller yields to AP traffic between material changes.
                break
            self.status = {'native_rendering': True, 'reason': 'scouted colors active',
                           'loaded': len(self.rows), 'colored': sum(color != 'red' for color in self.applied.values())}
            return changed
        except (MemoryUnavailable, ValueError) as error:
            self.rows = []
            self.next_scan = now + .5
            self.status = {'native_rendering': False, 'reason': str(error)}

    @staticmethod
    def key(row):
        return tuple(row[name] for name in ('context', 'actor', 'model', 'resource', 'registers', 'stages'))

    def poll_steps(self, memory, snapshot, guard, colors):
        for _ in range(5):
            if not self.poll(memory,snapshot,guard,colors):
                break
            yield set(), False
