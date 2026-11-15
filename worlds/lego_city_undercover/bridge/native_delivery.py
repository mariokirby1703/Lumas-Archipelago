"""Reconcile AP receipts with native memory and the serialized save, in order."""
import asyncio
import logging
from delivery_marker import MARKER_OFFSET,MARKER_SIZE,parse_marker,receipt_saved,marker_from_save
from inventory_reader import pointer,read_model_ids
from model_selection import ownership_selection_supported,model_delivery_ready
from native_model_transport import NativePlayerBusy,grant_model,grant_ability,grant_cheat,grant_currency_batch,request_save,enforce_rewards,configure_detective_scan,enable_superbuild_jobs
from reward_policy import reward_masks,encode_policy
from native_save import resolve_save,read_save,model_saved,cheat_saved,ability_saved,save_evidence,ensure_backup
from research_profile import ABILITY_NAMES
from save_reader import read_save_controller
from native_context_policy import PASSIVE_CONTEXTS
from class_entitlements import model_class_ready,tool_class_ready


class NativeDeliveryEngine:
    def __init__(self,dll,save_file=None):
        self.dll=dll;self.explicit_save=save_file;self.identity=None
        self.path=None;self.models=None;self.requested=set();self.last_problem=None;self.unbound=set()
        self.last_save_data=None
        self.runtime_states={}
        self.binding_ready=False

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

    async def prepare_binding(self,session,snapshot,journal):
        """Bind/backup before check reconciliation; never grant or revoke rewards."""
        context=snapshot['actor'].get('context',{}).get('index')
        self.binding_ready=False
        identity=(session.pid,journal.binding_token,pointer(session.read,session.base+0x1c7f160))
        if snapshot.get('actor',{}).get('address'):
            identity+=(snapshot['actor']['address'],(snapshot.get('native_binding',{}).get('marker') or {}).get('binding'))
        if identity!=self.identity:
            self.identity=identity;self.path=None;self.models=None;self.requested.clear()
            self.last_save_data=None
            self.runtime_states={}
        if self.path is None:
            try:
                path=await asyncio.to_thread(resolve_save,session.read,session.base,self.explicit_save)
                journal.bind_native_save(path)
                await asyncio.to_thread(ensure_backup,path,journal.directory/'native_backups'/journal.binding_token.hex())
                self.path=path
            except (OSError,ValueError,RuntimeError) as error:
                if str(error)!=self.last_problem:logging.warning('Native delivery waiting: %s',error);self.last_problem=str(error)
                if context in PASSIVE_CONTEXTS and str(error).startswith('No unique matching native save') and 'identity' not in self.requested:
                    await self._save(session,'identity')
                return False
            logging.info('Native save bound for disk verification: %s',self.path)
            self.last_problem=None
        try:
            data=await asyncio.to_thread(read_save,self.path)
            disk_marker=parse_marker(marker_from_save(data))
            if disk_marker and disk_marker['binding']!=journal.binding_token.hex():
                problem='Native save file is bound to another AP seed/slot; possible Cloud/file replacement; native writes stopped'
                if self.last_problem!=problem:logging.error(problem)
                self.last_problem=problem
                return False
            self.last_save_data=data
        except (OSError,ValueError,RuntimeError) as error:
            self.last_problem='Native save file not stable: '+str(error)
            return False
        if (self.last_problem or '').startswith('Native save file'):self.last_problem=None
        self.binding_ready=True
        return True

    async def _poll(self,session,snapshot,journal,effects=(),received=(),options=None,overrides=None):
        if not await self.prepare_binding(session,snapshot,journal):return
        context=snapshot['actor'].get('context',{}).get('index')
        if context not in PASSIVE_CONTEXTS:return
        data=self.last_save_data
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
            await overrides.verify_save(session,self.path,self.dll)
            masks=overrides.policy(masks,self.models,snapshot.get('cheats',{}).get('records',[]))
        policy=encode_policy(session.pid,journal.binding_token,masks)
        # Do not revoke equipped models, tools or cheats while driving/riding.
        enforced=(await asyncio.to_thread(enforce_rewards,session.pid,policy,journal.binding_token,self.dll)
                  if context==46 else dict(changes=0,switch_requested=False))
        if context==46 and 0 in masks.get('managed_runtime',()):
            self.runtime_states['DetectiveScan']=0 in masks.get('entitled_runtime',())
        elif context==46:
            self.runtime_states.pop('DetectiveScan',None)
        if enforced['switch_requested']:
            if self.last_problem!='equipped-unreceived':
                logging.warning('Select an AP-owned or starting civilian outfit to finish deferred reward locking')
                self.last_problem='equipped-unreceived'
            return
        if enforced['changes']:
            logging.info('Vanilla rewards suppressed after check reconciliation: %s native changes',enforced['changes'])
            return  # All inventory/ability observations must now be refreshed.
        # AP SuperBuild precedes the vanilla tutorial in non-linear seeds.
        # Enable its original job-tree branch, then let tile scripts award/save
        # each finished build exactly once. Never fabricate counters or gold.
        superbuild=snapshot.get('story',{}).get('jobs',{}).get('SuperBuild_Saves',{})
        if (context==46 and snapshot.get('abilities',{}).get('SuperBuild') and
                superbuild.get('SuperBuildsActive') is False):
            result=await asyncio.to_thread(enable_superbuild_jobs,session.pid,journal.binding_token,self.dll)
            if result['changed']:
                logging.info('Native Superbuild jobs enabled; original completion scripts resumed')
                await self._save(session,'SuperBuild jobs')
                return
        inventory={r['model_id']:r for r in snapshot['characters']}
        selection_supported=ownership_selection_supported(session.read,session.base)
        deliveries=journal.reconciliation_deliveries()
        for delivery in deliveries:
            index=delivery['index'];plan=delivery['plan'];kind=plan['kind']
            if overrides and overrides.blocks(plan):continue
            if kind in ('ability_unlock','runtime_unlock') and not tool_class_ready(plan,received,options or {}):continue
            if kind=='area_access':
                if delivery['state']!='runtime_verified':journal.record_runtime_verification(index,
                    dict(verified=True,native_save_flag=False,reason='Area policy entitlement is journal-backed; not a native ability bit'))
                continue
            if kind=='noop':
                if delivery['state']!='runtime_verified':journal.record_runtime_verification(index,
                    dict(verified=True,native_save_flag=False,reason=plan['reason']))
                continue
            if kind=='runtime_unlock' and plan['ability']=='DetectiveScan':
                if context!=46:continue
                # The policy call above installed/read back the gate. The durable
                # entitlement is the AP journal, not an invented native save bit.
                if delivery['state']!='runtime_verified' or not self.runtime_states.get('DetectiveScan'):
                    evidence=await asyncio.to_thread(configure_detective_scan,session.pid,True,self.dll)
                    self.runtime_states['DetectiveScan']=True
                    journal.record_runtime_verification(index,evidence)
                    logging.info('Detective Scan gate verified; entitlement persisted in AP receipt journal (%s)',index)
                continue
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
                if not model_class_ready(name,received,options or {}):continue
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
