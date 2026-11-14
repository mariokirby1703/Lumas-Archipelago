"""Reconcile AP receipts with native memory and the serialized save, in order."""
import asyncio
import logging
from delivery_marker import MARKER_OFFSET,MARKER_SIZE,parse_marker,receipt_saved,marker_from_save
from inventory_reader import pointer,read_model_ids
from model_selection import ownership_selection_supported,model_delivery_ready
from native_model_transport import NativePlayerBusy,grant_model,grant_ability,grant_cheat,grant_currency_batch,request_save,enforce_rewards
from reward_policy import reward_masks,encode_policy
from native_save import resolve_save,read_save,model_saved,cheat_saved,ability_saved,save_evidence,ensure_backup
from research_profile import ABILITY_NAMES
from save_reader import read_save_controller
from native_context_policy import PASSIVE_CONTEXTS


class NativeDeliveryEngine:
    def __init__(self,dll,save_file=None):
        self.dll=dll;self.explicit_save=save_file;self.identity=None
        self.path=None;self.models=None;self.requested=set();self.last_problem=None;self.unbound=set()

    async def _save(self,session,index):
        status=read_save_controller(session.read,session.base)
        if not status.get('enabled') or status.get('requested'):return False
        await asyncio.to_thread(request_save,session.pid,self.dll)
        self.requested.add(index)
        logging.info('Native autosave requested for AP receipt %s',index)
        return True

    async def poll(self,session,snapshot,journal,effects=(),received=(),options=None,overrides=None):
        try:
            return await self._poll(session,snapshot,journal,effects,received,options,overrides)
        except NativePlayerBusy:
            # A snapshot can become stale while the user starts an interaction.
            # This is a deferred command, not a failed reader: preserve the
            # session, previous check snapshot and durable delivery queue.
            logging.debug('Native delivery deferred until ordinary gameplay')

    async def _poll(self,session,snapshot,journal,effects=(),received=(),options=None,overrides=None):
        context=snapshot['actor'].get('context',{}).get('index')
        if context not in PASSIVE_CONTEXTS:return
        identity=(session.pid,journal.binding_token,pointer(session.read,session.base+0x1c7f160))
        if identity!=self.identity:
            self.identity=identity;self.path=None;self.models=None;self.requested.clear()
        if self.path is None:
            try:
                path=await asyncio.to_thread(resolve_save,session.read,session.base,self.explicit_save)
                journal.bind_native_save(path)
                await asyncio.to_thread(ensure_backup,path,journal.directory/'native_backups'/journal.binding_token.hex())
                self.path=path
            except (OSError,ValueError,RuntimeError) as error:
                if str(error)!=self.last_problem:logging.warning('Native delivery waiting: %s',error);self.last_problem=str(error)
                if str(error).startswith('No unique matching native save') and 'identity' not in self.requested:
                    await self._save(session,'identity')
                return
            logging.info('Native save bound for disk verification: %s',self.path)
            self.last_problem=None
        try:data=await asyncio.to_thread(read_save,self.path)
        except (OSError,ValueError,RuntimeError):return  # Native writer may be replacing the file.
        if self.models is None:self.models=await asyncio.to_thread(read_model_ids,session.read,session.base)
        bank=pointer(session.read,session.base+0x1c7cbb8)
        marker=session.read(bank+MARKER_OFFSET,MARKER_SIZE)
        parsed=parse_marker(marker)
        if parsed and parsed['binding']!=journal.binding_token.hex():
            problem='Loaded native save is bound to another AP seed/slot; native delivery stopped'
            if problem!=self.last_problem:logging.error(problem);self.last_problem=problem
            return
        masks=reward_masks(effects,received,self.models,snapshot.get('cheats',{}).get('records',[]),options or {})
        if overrides and context==46:
            if not await overrides.apply(session,snapshot,self.models,received,self.dll):return
            masks=overrides.policy(masks,self.models,snapshot.get('cheats',{}).get('records',[]))
        policy=encode_policy(session.pid,journal.binding_token,masks)
        # Do not revoke equipped models, tools or cheats while driving/riding.
        enforced=(await asyncio.to_thread(enforce_rewards,session.pid,policy,journal.binding_token,self.dll)
                  if context==46 else dict(changes=0,switch_requested=False))
        if enforced['switch_requested']:
            if self.last_problem!='equipped-unreceived':
                logging.warning('Select an AP-owned or starting civilian outfit to finish deferred reward locking')
                self.last_problem='equipped-unreceived'
            return
        if enforced['changes']:
            logging.info('Vanilla rewards suppressed after check reconciliation: %s native changes',enforced['changes'])
            return  # All inventory/ability observations must now be refreshed.
        inventory={r['model_id']:r for r in snapshot['characters']}
        selection_supported=ownership_selection_supported(session.read,session.base)
        deliveries=journal.reconciliation_deliveries()
        for delivery in deliveries:
            index=delivery['index'];plan=delivery['plan'];kind=plan['kind']
            if overrides and overrides.blocks(plan):continue
            if kind in ('add_studs','add_bricks'):
                if receipt_saved(marker,journal.binding_token,index) and receipt_saved(marker_from_save(data),journal.binding_token,index):
                    if delivery['state']!='applied':journal.record_saved(index,save_evidence(self.path,data))
                    continue
                if receipt_saved(marker,journal.binding_token,index):
                    await self._save(session,index)
                    return
                status=read_save_controller(session.read,session.base)
                if not status.get('enabled') or status.get('requested') or status.get('state',0)!=0:return
                # The native persisted watermark makes a retry safe even if the
                # previous process died between the native call and SQLite commit.
                batch=[r for r in deliveries if r['plan']['kind'] in ('add_studs','add_bricks')
                       and not receipt_saved(marker,journal.binding_token,r['index'])][:24]
                evidence=await asyncio.to_thread(grant_currency_batch,session.pid,batch,journal.binding_token,self.dll)
                for row in batch:journal.record_memory_verification(row['index'],evidence)
                logging.info('AP currency batch credited: %s packages; Studs +%s, bricks +%s; one native save',
                    len(batch),sum(r['plan']['amount'] for r in batch if r['plan']['kind']=='add_studs'),
                    sum(r['plan']['amount'] for r in batch if r['plan']['kind']=='add_bricks'))
                return
            if kind=='model_unlock':
                name=plan['native_name'];model=self.models.get(name)
                if model is None:
                    key=(journal.binding_token,index)
                    if key not in self.unbound:
                        logging.warning('AP receipt %s is waiting for an absent or ambiguous native model: %s',index,name)
                        self.unbound.add(key)
                    continue
                row=inventory.get(model,{})
                if model_delivery_ready(row,selection_supported):
                    if model_saved(data,model):
                        if delivery['state']!='applied':journal.record_saved(index,save_evidence(self.path,data))
                    else:await self._save(session,index)
                    continue
                evidence=await asyncio.to_thread(grant_model,session.pid,model,name,self.dll)
            elif kind=='ability_unlock' and plan['ability'] in ABILITY_NAMES:
                name=plan['ability']
                if snapshot.get('ability_raw',{}).get(name,{}).get('existing')==1:
                    if ability_saved(data,name):
                        if delivery['state']!='applied':journal.record_saved(index,save_evidence(self.path,data))
                    else:await self._save(session,index)
                    continue
                evidence=await asyncio.to_thread(grant_ability,session.pid,name,self.dll)
            elif kind=='cheat_unlock' and snapshot.get('cheats',{}).get('status')=='read':
                matches=[r for r in snapshot['cheats']['records'] if r['native_name']==plan.get('native_name')]
                if len(matches)!=1:continue
                cheat=matches[0]
                if cheat['effect_flag']:
                    if cheat_saved(data,cheat['index']):
                        if delivery['state']!='applied':journal.record_saved(index,save_evidence(self.path,data))
                    else:await self._save(session,index)
                    continue
                evidence=await asyncio.to_thread(grant_cheat,session.pid,cheat['index'],cheat['native_name'],self.dll)
            else:
                key=(journal.binding_token,index)
                if key not in self.unbound and (kind=='unbound' or kind=='ability_unlock'):
                    logging.warning('AP receipt %s is waiting for an unbound native effect: %s',index,plan)
                    self.unbound.add(key)
                continue
            journal.record_memory_verification(index,evidence)
            logging.info('Native grant verified in memory: %s (receipt %s)',plan.get('native_name',plan.get('ability',kind)),index)
            await self._save(session,index)
            return  # Refresh all native state before another grant.
