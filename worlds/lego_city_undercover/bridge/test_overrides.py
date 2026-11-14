"""Session-local test policy; never writes AP receipts or acknowledges checks."""
from collections import deque
import logging
from item_delivery import effect_plan
from reward_policy import TOOL_ABILITIES,STARTING_MODELS
from research_profile import ABILITY_NAMES


def effect_key(effect):
    plan=effect_plan(effect)
    return (plan['kind'],plan.get('native_name',plan.get('ability')))


def supported(effect):
    plan=effect_plan(effect);kind=plan['kind']
    return (kind in ('model_unlock','add_studs','add_bricks') or
            kind=='cheat_unlock' and bool(plan.get('native_name')) or
            kind=='ability_unlock' and plan['ability'] in TOOL_ABILITIES)


class TestOverrides:
    def __init__(self):self.entries={};self.currency=deque();self.problem=None

    def set(self,effect,enabled):
        if not supported(effect):raise ValueError('Dieses Item hat noch keine native Test-Anbindung.')
        plan=effect_plan(effect);key=effect_key(effect)
        if plan['kind'] in ('add_studs','add_bricks'):
            self.currency.append((effect,enabled));return
        if not enabled and plan.get('native_name') in STARTING_MODELS:
            raise ValueError('Die Start-Zivilisten bleiben als Wechselmöglichkeit verfügbar.')
        self.entries[key]=(effect,enabled)

    def reset(self):
        self.currency.clear()
        self.entries={key:(effect,None) for key,(effect,_) in self.entries.items()}

    def blocks(self,plan):
        key=(plan['kind'],plan.get('native_name',plan.get('ability')))
        return key in self.entries and self.entries[key][1] is False

    def mask_snapshot(self,snapshot):
        names={key[1] for key in self.entries if key[0]=='model_unlock'}
        # Native test grants must not become source checks through pending queues.
        return dict(snapshot,characters=[dict(row,pending_grant=False) if row.get('internal_name','').upper() in names
                     else row for row in snapshot.get('characters',[])])

    def policy(self,masks,models,cheats):
        result={k:set(v) for k,v in masks.items()};cheat_ids={r['native_name']:r['index'] for r in cheats}
        for (kind,name),(_,enabled) in self.entries.items():
            if enabled is None:continue
            if kind=='model_unlock':group='models';index=models.get(name)
            elif kind=='ability_unlock':group='abilities';index=ABILITY_NAMES.index(name)
            else:group='cheats';index=cheat_ids.get(name)
            if index is None:continue
            result['managed_'+group].add(index)
            if enabled:result['entitled_'+group].add(index)
            else:result['entitled_'+group].discard(index)
        return result

    async def apply(self,session,snapshot,models,received,dll):
        import asyncio
        from native_model_transport import test_remove,test_currency,grant_model,grant_ability,grant_cheat,NativePlayerBusy
        normal={effect_key(effect) for effect in received}
        cheats={r['native_name']:r for r in snapshot.get('cheats',{}).get('records',[])}
        inventory={r['model_id']:r for r in snapshot.get('characters',[])}
        try:
            if self.currency:
                # Consume before dispatch: never retry an uncertain currency write.
                effect,enabled=self.currency.popleft();plan=effect_plan(effect)
                await asyncio.to_thread(test_currency,session.pid,plan['kind'],plan['amount'],enabled,dll)
                logging.info('TEST: %s %s', 'gegeben' if enabled else 'entfernt',effect['name'])
            for key,(effect,enabled) in list(self.entries.items()):
                kind,name=key
                if enabled is None and key in normal:
                    del self.entries[key];continue
                if kind=='model_unlock':index=models.get(name)
                elif kind=='ability_unlock':index=ABILITY_NAMES.index(name)
                else:index=cheats.get(name,{}).get('index')
                if index is None:raise ValueError('Native Item-ID noch nicht verfügbar: '+effect['name'])
                if enabled is not True:
                    await asyncio.to_thread(test_remove,session.pid,kind,index,name,dll)
                    if enabled is None:del self.entries[key]
                elif kind=='model_unlock':
                    if not inventory.get(index,{}).get('owned_byte'):
                        await asyncio.to_thread(grant_model,session.pid,index,name,dll)
                elif kind=='ability_unlock':
                    if snapshot.get('ability_raw',{}).get(name,{}).get('existing')!=1:
                        await asyncio.to_thread(grant_ability,session.pid,name,dll)
                elif not cheats[name].get('effect_flag'):
                    await asyncio.to_thread(grant_cheat,session.pid,index,name,dll)
            self.problem=None;return True
        except NativePlayerBusy:return False
        except (ValueError,OSError,RuntimeError) as error:
            if str(error)!=self.problem:logging.error('TEST: %s',error);self.problem=str(error)
            return False
