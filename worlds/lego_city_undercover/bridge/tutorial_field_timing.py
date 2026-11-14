"""Delay tutorial-pad changes until the observed scene has settled.

This is a timing mitigation under live visual test, not proof that the native
floor graphic is initialized. No story/interaction state is advanced here.
"""
import time


class TutorialFieldTiming:
    def __init__(self, clock=time.monotonic, delay=8.0):
        self.clock=clock;self.delay=delay;self.identity=None;self.ready_at=0.0

    def ready(self,pid,scene_fields):
        level=scene_fields.get('level') if scene_fields.get('status')=='read' else None
        identity=(pid,level) if level else None
        now=self.clock()
        if identity!=self.identity:
            self.identity=identity;self.ready_at=now+self.delay
        return identity is not None and now>=self.ready_at
