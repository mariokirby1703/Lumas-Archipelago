import unicodedata
import time
CHARSET=set(' !#&()-./0123456789:;<>?@ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz')
DISPLAY_SECONDS=60
FADE_SECONDS=10
def item_colour(flags):
    return '#F05252' if flags&4 else '#AF70FF' if flags&1 else '#305BD8' if flags&2 else '#64C8FF'

def ascii_text(text):
    text=str(text).replace('\u00df','ss').replace('\u00c4','Ae').replace('\u00d6','Oe').replace('\u00dc','Ue').replace('\u00e4','ae').replace('\u00f6','oe').replace('\u00fc','ue')
    return ''.join(c if c in CHARSET else '?' for c in unicodedata.normalize('NFKD',text) if not unicodedata.combining(c))[:512]

def fit_text(text,width,metrics,capacity=128):
    """Only use caller-verified pixel metrics and byte capacity."""
    if width<=0 or capacity<2:return ''
    result='';pixels=0
    for c in ascii_text(text):
        if c not in metrics:raise ValueError('unverified glyph metric')
        if pixels+metrics[c]>width or len(result)>=capacity-1:break
        result+=c;pixels+=metrics[c]
    return result

class Ticker:
    LIMIT=32
    def __init__(self,journal,clock=time.monotonic,wall_clock=time.time):
        self.wall_clock=wall_clock
        self.journal=journal;self.clock=clock;self.remaining=5.;self.last_tick=None
        journal.data.setdefault('ap_hud',{'highwater':None,'sent':[],'queue':[],'current':None,'events_received':0,'overflow':0})
        journal.data['ap_hud'].setdefault('display_history',[])
        journal.data['ap_hud'].setdefault('display_times',[])
    @property
    def data(self):return self.journal.data['ap_hud']
    def save(self):self.journal.save()
    def history_ready(self,items):
        """Establish the initial baseline even when AP omits empty history."""
        if self.data['highwater'] is None:
            self.data['highwater']=len(items);self.save()
    def enqueue(self,event):
        if len(self.data['queue'])>=self.LIMIT:
            self.data['queue'].pop(0);self.data['overflow']+=1
        self.data['queue'].append(event);self.data['events_received']+=1;self.save()
    def received(self,items,index,name,player,slot=None):
        if type(index) is not int or index<0:return
        if self.data['highwater'] is None:
            if index!=0:return
            self.data['highwater']=len(items);self.save();return
        high=self.data['highwater']
        if index>high:return
        for offset,item in enumerate(items):
            if not all(type(getattr(item,key,None)) is int for key in ('item','location','player','flags')):return
            receipt=index+offset
            if receipt<high:continue
            if receipt!=self.data['highwater']:break
            flags=item.flags
            if item.location == -1 and item.player == slot and flags == 0:
                # MultiServer !getitem omits flags. Only infer classification
                # for our own known game items; real location flags stay exact.
                from ..Items import BY_ID,classification
                if item.item in BY_ID:flags=int(classification(BY_ID[item.item]))
            event={'kind':'Received','item':name(item.item),'player':player(item.player),'receipt':receipt,'flags':flags}
            if item.player==slot and item.location>=0:event['own']=True
            self.data['highwater']=receipt+1;self.enqueue(event)
    def sent(self,args,team,slot,name,player):
        if args.get('type')!='ItemSend':return
        item=args.get('item');target=args.get('receiving')
        try:
            values=[item[k] for k in ('item','location','player','flags')] if isinstance(item,dict) else list(item)
            if len(values)!=4 or any(type(v) is not int for v in values):return
            item_id,location,source,flags=values
            if type(target) is not int or target<=0 or source!=slot or target==slot or location<0:return
        except (KeyError,TypeError,ValueError):return
        key=[team,source,location,target,item_id]
        if key in self.data['sent']:return
        self.data['sent'].append(key)
        self.enqueue({'kind':'Sent','item':name(item_id,target),'player':player(target),'identity':key,'flags':flags})
    def tick(self,visible):
        now=self.clock()
        if visible and self.last_tick is not None:self.remaining-=max(0,now-self.last_tick)
        self.last_tick=now if visible else None
        if visible and self.data['queue'] and (self.data['current'] is None or self.remaining<=0):
            self.data['current']=self.data['queue'].pop(0);self.remaining=5.;self.save()
        return self.data['current'] if visible else None
    def candidate(self):
        """Inspect the next display without consuming an unpublished event."""
        if self.data['queue'] and (self.data['current'] is None or self.remaining<=0):
            return dict(self.data['queue'][0])
        return dict(self.data['current']) if self.data['current'] else None

    def published(self,event):
        """Commit only a matching two-line native acknowledgement."""
        if event != self.candidate():
            return False
        if self.data['queue'] and (self.data['current'] is None or self.remaining<=0):
            self.data['current']=self.data['queue'].pop(0)
            history=self.data.setdefault('display_history',[])
            history.append(dict(self.data['current']))
            del history[:-5]
            times=self.data.setdefault('display_times',[])
            times.append(self.wall_clock());del times[:-5]
            self.remaining=5.
            self.save()
        self.last_tick=self.clock()
        return True

    def panel_candidate(self):
        """Newest first, at most five messages; pending entry remains unconsumed."""
        now=self.wall_clock()
        history=[dict(e) for e,stamp in zip(self.data.get('display_history',[]),self.data.get('display_times',[]))
                 if 0<=now-stamp<DISPLAY_SECONDS]
        candidate=self.candidate()
        if candidate and self.data['queue'] and (self.data['current'] is None or self.remaining<=0):history.append(candidate)
        return [[e['kind']+' '+e['item'],('to ' if e['kind']=='Sent' else 'from ')+e['player']]
                for e in reversed(history[-5:])]

    def has_pending_candidate(self):
        return bool(self.data['queue'] and (self.data['current'] is None or self.remaining<=0))

    def panel_events(self):
        now=self.wall_clock()
        events=[]
        for e,stamp in zip(self.data['display_history'],self.data['display_times']):
            age=now-stamp
            # Keep a zero-alpha tail for native interpolation to settle before
            # compacting the panel; its text is no longer visibly displayed.
            if not 0<=age<DISPLAY_SECONDS+5:continue
            event=dict(e)
            if age>DISPLAY_SECONDS-FADE_SECONDS:
                event['alpha']=max(0,min(255,round(255*(DISPLAY_SECONDS-age)/FADE_SECONDS)))
            events.append(event)
        if self.has_pending_candidate():events.append(self.candidate())
        return list(reversed(events[-5:]))

    def elapsed_visible(self,visible):
        """Advance dwell only while the acknowledged generation is visible."""
        now=self.clock()
        if visible and self.last_tick is not None:
            self.remaining-=max(0,now-self.last_tick)
        self.last_tick=now if visible else None
    def diagnostics(self,enabled=False):
        e=self.data['current']
        return {'hud_ready':False,'font_ready':False,'owner_verified':False,'events_received':self.data['events_received'],
            'queued':len(self.data['queue']),'overflow':self.data['overflow'],'last_text':([e['kind']+' '+e['item'],('to ' if e['kind']=='Sent' else 'from ')+e['player']] if e else None),
            'blocked_reason':'native alphabetic font/overlay lifecycle and setter ABI not live verified' if enabled else 'ap_item_hud is Off'}
