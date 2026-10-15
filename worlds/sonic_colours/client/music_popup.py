"""Ephemeral now-playing model, driven only by native successful starts."""
from .ap_hud_ticker import ascii_text


class MusicPopup:
    def __init__(self,metadata=None):
        if metadata is None:
            from ..world_constants import load_data
            try:metadata=load_data('music_display_names.json')['tracks']
            except (OSError,KeyError,ValueError):metadata={}
        self.metadata=metadata
        self.sequence=None;self.started=None;self.title=None;self.cue=None;self.heard=None
        self.restart_key=None

    def observe(self,event,now,mapping=None,restart_key=None):
        sequence=event.get('music_sequence')
        if sequence is None or sequence==self.sequence:return False
        self.sequence=sequence
        cue=event.get('cue_name','')
        if not sequence or not cue.startswith('bgm_') or cue.startswith('bgm_jingle_'):
            return False
        # The CRI wrapper can also report successful starts at loop boundaries.
        # Re-reading the same playback in the same scene must not renew the HUD.
        if cue==self.cue and restart_key==self.restart_key:
            return False
        self.restart_key=restart_key
        self.cue=cue;self.heard=(mapping or {}).get(cue,cue)
        self.title=ascii_text((self.metadata.get(self.heard,{}).get('title') or self.heard).replace('_',' '))
        self.started=now
        return True

    def display(self,now):
        if self.started is None:return {'alpha':0,'title':'','cue':self.cue}
        elapsed=max(0.,now-self.started)
        alpha=255 if elapsed<=5 else round(255*max(0.,(10-elapsed)/5))
        return {'alpha':alpha,'title':self.title if alpha else '', 'cue':self.cue,'heard':self.heard}


def update(runtime):
    if not hasattr(runtime,'music_popup'):runtime.music_popup=MusicPopup()
    from .music_bank import plan
    mapping=plan(runtime.slot_data['seed_name'],'anywhere' if runtime.slot_data['options']['music_randomization'] else 'off')
    snapshot=getattr(runtime,'snapshot',None)
    restart_key=(getattr(snapshot,'session',None),getattr(snapshot,'stage_epoch',None),getattr(snapshot,'scene',None))
    runtime.music_popup.observe(getattr(runtime,'native_event_status',{}),runtime.clock(),mapping,restart_key)
    runtime.music_popup_status=runtime.music_popup.display(runtime.clock())
    return runtime.music_popup_status
