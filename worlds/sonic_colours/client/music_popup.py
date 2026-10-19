"""Ephemeral now-playing model, driven only by native successful starts."""
from .ap_hud_ticker import ascii_text
from functools import lru_cache

RESULT_CUES={'bgm_jingle_stg_clear','bgm_jingle_boss_clear','bgm_jingle_mlt_clear'}


class MusicPopup:
    def __init__(self,metadata=None):
        if metadata is None:
            from ..world_constants import load_data
            try:metadata=load_data('music_display_names.json')['tracks']
            except (OSError,KeyError,ValueError):metadata={}
        self.metadata=metadata
        self.sequence=None;self.started=None;self.title=None;self.cue=None;self.heard=None
        self.restart_key=None
        self.generation=0;self.waiting_for_publish=False

    def observe(self,event,now,mapping=None,restart_key=None,defer_start=False):
        sequence=event.get('music_sequence')
        if sequence is None or sequence==self.sequence:return False
        self.sequence=sequence
        cue=event.get('cue_name','')
        if (not sequence or not cue.startswith('bgm_')
                or cue.startswith('bgm_jingle_') and cue not in RESULT_CUES):
            return False
        # The CRI wrapper can also report successful starts at loop boundaries.
        # Re-reading the same playback in the same scene must not renew the HUD.
        if cue==self.cue and restart_key==self.restart_key:
            return False
        self.restart_key=restart_key
        self.cue=cue;self.heard=(mapping or {}).get(cue,cue)
        self.title=ascii_text((self.metadata.get(self.heard,{}).get('title') or self.heard).replace('_',' '))
        self.started=now
        self.generation+=1;self.waiting_for_publish=defer_start
        return True

    def published(self,generation,now):
        if generation==self.generation and self.waiting_for_publish:
            self.started=now;self.waiting_for_publish=False

    def display(self,now):
        if self.started is None:return {'alpha':0,'title':'','cue':self.cue}
        elapsed=0. if self.waiting_for_publish else max(0.,now-self.started)
        alpha=255 if elapsed<=5 else round(255*max(0.,(10-elapsed)/5))
        # Keep the string at alpha zero: replacing it with a blank would bypass
        # the native per-cast fade and make the title disappear abruptly.
        return {'alpha':alpha,'title':self.title,'cue':self.cue,'heard':self.heard}


@lru_cache(maxsize=8)
def _seed_mapping(seed_name, music_randomization,version=1):
    # The global 87-cue matching is deterministic and seed-owned. Running its
    # recursive matching on every HUD fade tick can delay check/receipt polls.
    from .music_bank import plan
    mode='anywhere' if music_randomization else 'off'
    return plan(seed_name,mode) if version==1 else plan(seed_name,mode,version)


def update(runtime):
    if not hasattr(runtime,'music_popup'):runtime.music_popup=MusicPopup()
    mapping=_seed_mapping(runtime.slot_data.get('music_seed',runtime.slot_data['seed_name']),
                          bool(runtime.slot_data['options']['music_randomization']),runtime.slot_data.get('music_mapping_version',1))
    snapshot=getattr(runtime,'snapshot',None)
    restart_key=(getattr(snapshot,'session',None),getattr(snapshot,'stage_epoch',None),getattr(snapshot,'scene',None))
    runtime.music_popup.observe(getattr(runtime,'native_event_status',{}),runtime.clock(),mapping,restart_key,defer_start=True)
    runtime.music_popup_status=runtime.music_popup.display(runtime.clock())
    return runtime.music_popup_status
