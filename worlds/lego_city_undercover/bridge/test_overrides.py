"""Session-only test grants with observed outcomes and bounded retries.

A click is a request, never evidence of a successful native mutation. An
uncertain timeout is *not* automatically replayed; the next snapshot may prove
that it succeeded, otherwise the operator must explicitly issue a fresh click.
No operation changes AP receipts, source discovery, or location acknowledgements.
"""
from collections import deque
import logging
from datetime import datetime
from item_delivery import effect_plan
from reward_policy import TOOL_ABILITIES, STARTING_MODELS
from research_profile import ABILITY_NAMES


def effect_key(effect):
    plan = effect_plan(effect)
    return (plan['kind'], plan.get('native_name', plan.get('ability')))


def supported(effect):
    if not effect:
        return False
    plan = effect_plan(effect)
    kind = plan['kind']
    return (kind in ('model_unlock', 'add_studs', 'add_bricks') or
            kind == 'runtime_unlock' and plan.get('ability')=='DetectiveScan' or
            kind == 'cheat_unlock' and bool(plan.get('native_name')) or
            kind == 'ability_unlock' and plan['ability'] in TOOL_ABILITIES)


class TestOverrides:
    def __init__(self):
        self.entries = {}
        self.currency = deque()
        self.problem = None
        self.attempted = set()
        self.verified = set()
        self.errors = {}
        self.saved=set()
        self.native_ids={}
        self.save_request=None
        self.save_problem=None
        self.history=[]
        self.latest={}
        self.currency_history=deque()
        self.currency_save_pending=False

    def history_rows(self):
        for key,index in self.latest.items():
            row=self.history[index]
            row['ram']='Fehler / unklar' if key in self.errors else 'Bestätigt' if key in self.verified else 'Wird geprüft' if key in self.attempted else 'Ausstehend'
            row['save']='Bestätigt' if key in self.saved else 'Fehler: '+self.save_problem if self.save_problem else 'Ausstehend'
            if key[0]=='runtime_unlock':row['save']='Client-Regel; kein natives Save-Flag'
            if key not in self.entries:row['ram']='AP-Regel wiederhergestellt';row['save']='AP-Abgleich'
            index=self.native_ids.get(key)
            row['native_id']=index
            proof=row.get('proof',{})
            row['detail']=self.errors.get(key,('Native ID '+str(index) if index is not None else '')+
                                          (' · Save '+proof['offset'] if proof.get('offset') else ''))
        return [dict(row) for row in self.history]

    def set(self, effect, enabled):
        if not supported(effect):
            raise ValueError('Dieses Item hat noch keine native Test-Anbindung.')
        plan = effect_plan(effect)
        key = effect_key(effect)
        if plan['kind'] in ('add_studs', 'add_bricks'):
            self.currency.append((effect, enabled))
            self.currency_history.append(len(self.history))
            self.history.append(dict(id=len(self.history)+1,time=datetime.now().strftime('%H:%M:%S'),item=effect['name'],
                                     action='Geben' if enabled else 'Nehmen',ram='Ausstehend',save='Keine Einzel-Flag-Prüfung',detail='Währungsbuchung'))
            return
        if not enabled and plan.get('native_name') in STARTING_MODELS:
            raise ValueError('Die Start-Zivilisten bleiben als Wechselmöglichkeit verfügbar.')
        self.entries[key] = (effect, enabled)
        self.saved.discard(key);self.save_request=None;self.save_problem=None
        self.latest[key]=len(self.history)
        self.history.append(dict(id=len(self.history)+1,time=datetime.now().strftime('%H:%M:%S'),item=effect['name'],
                                 action='Geben' if enabled else 'Nehmen',ram='Ausstehend',save='Ausstehend',detail=''))
        # A new explicit click permits a new attempt, even after a timeout.
        self.attempted.discard(key)
        self.verified.discard(key)
        self.errors.pop(key, None)
        self.problem = None

    def reset(self):
        # Currency cannot be undone automatically. Already dispatched amounts
        # are intentionally not inverted or silently retried.
        self.currency.clear()
        for index in self.currency_history:self.history[index]['ram']='Abgebrochen'
        self.currency_history.clear()
        self.attempted.clear()
        self.verified.clear()
        self.errors.clear()
        self.problem = None
        self.saved.clear();self.save_request=None
        self.entries = {key: (effect, None) for key, (effect, _) in self.entries.items()}

    def blocks(self, plan):
        key = (plan['kind'], plan.get('native_name', plan.get('ability')))
        return key in self.entries and self.entries[key][1] is False

    def mask_snapshot(self, snapshot):
        names = {key[1] for key in self.entries if key[0] == 'model_unlock'}
        # Do not report native test grants as actual world pickups.
        return dict(snapshot, characters=[
            dict(row, pending_grant=False) if row.get('internal_name', '').upper() in names else row
            for row in snapshot.get('characters', [])])

    def policy(self, masks, models, cheats):
        result = {key: set(values) for key, values in masks.items()}
        cheat_ids = {r['native_name']: r['index'] for r in cheats}
        for (kind, name), (_, enabled) in self.entries.items():
            if enabled is None or (kind, name) in self.errors:
                # Uncertain native outcome must not activate a second mutation
                # via the independent reward-enforcement command.
                continue
            if kind == 'model_unlock':
                group, index = 'models', models.get(name)
            elif kind == 'runtime_unlock':
                group, index = 'runtime', 0
                result.setdefault('managed_runtime',set());result.setdefault('entitled_runtime',set())
            elif kind == 'ability_unlock':
                group, index = 'abilities', ABILITY_NAMES.index(name)
            else:
                group, index = 'cheats', cheat_ids.get(name)
            if index is None:
                continue
            result['managed_' + group].add(index)
            if enabled:
                result['entitled_' + group].add(index)
            else:
                result['entitled_' + group].discard(index)
        return result

    def status_rows(self):
        rows = []
        for key, (effect, enabled) in self.entries.items():
            if key in self.errors:
                status = '⚠ Unklar / fehlgeschlagen, erneut klicken'
            elif key in self.verified:
                status = '✓ RAM + Save bestätigt' if key in self.saved else '✓ Im Spielspeicher bestätigt · Save wird geprüft'
                if key[0]=='runtime_unlock':status='✓ Native Client-Regel bestätigt · kein natives Save-Flag'
            elif key in self.attempted:
                status = '⏳ Ergebnis wird überprüft'
            elif enabled is None:
                status = '↺ AP-Zustand wiederherstellen'
            else:
                status = '⏳ Vergabe ausstehend' if enabled else '⏳ Entzug ausstehend'
            rows.append(f"{effect['name']} · {status}")
        if self.currency:
            rows.append(f'{len(self.currency)} Währungstest(s) noch ausstehend')
        return rows

    @staticmethod
    def _native_state(kind, name, index, snapshot, inventory, cheats):
        """Return True/False when a fresh native read can prove an entitlement."""
        if kind == 'model_unlock':
            # read_characters() deliberately returns a SPARSE roster: models
            # with no found/owned/pending bits are absent. When read_model_ids()
            # supplied a validated index, absence means NOT OWNED, not an
            # unknown state. Otherwise fresh class grants never run until the
            # disguise has first been collected in vanilla gameplay.
            row = inventory.get(index)
            if row is None:
                return False
            return bool(row['owned_byte']) if 'owned_byte' in row else None
        if kind == 'ability_unlock':
            row = snapshot.get('ability_raw', {}).get(name)
            return bool(row['existing'] or row.get('pending')) if row and 'existing' in row else None
        row = cheats.get(name)
        return bool(row['effect_flag']) if row and 'effect_flag' in row else None

    async def apply(self, session, snapshot, models, received, dll):
        import asyncio
        from native_model_transport import (
            test_remove, test_currency, grant_model, grant_ability, grant_cheat,
            NativePlayerBusy,
        )
        normal = {effect_key(effect) for effect in received}
        cheats = {row['native_name']: row for row in snapshot.get('cheats', {}).get('records', [])}
        inventory = {row['model_id']: row for row in snapshot.get('characters', [])}
        if self.currency:
            effect, enabled = self.currency.popleft()  # No replay on uncertain result.
            history_index=self.currency_history.popleft() if self.currency_history else None
            plan = effect_plan(effect)
            try:
                await asyncio.to_thread(test_currency, session.pid, plan['kind'], plan['amount'], enabled, dll)
                logging.info('TEST: Währungsbefehl bestätigt: %s (%s). Speicherstand separat prüfen.',
                             effect['name'], 'hinzugefügt' if enabled else 'abgezogen')
                self.problem = None
                if history_index is not None:self.history[history_index]['ram']='Nativer Befehl bestätigt'
                self.currency_save_pending=True
            except NativePlayerBusy:
                self.currency.appendleft((effect, enabled))
                if history_index is not None:self.currency_history.appendleft(history_index)
                return False
            except (ValueError, OSError, RuntimeError) as error:
                self.problem = str(error)
                if history_index is not None:
                    self.history[history_index].update(ram='Fehler / unklar',detail=str(error))
                logging.error('TEST: Währung NICHT bestätigt: %s. Aus Sicherheitsgründen keine automatische Wiederholung.', error)
            return False  # Refresh native state before the next command.

        for key, (effect, enabled) in list(self.entries.items()):
            kind, name = key
            if enabled is None and key in normal:
                self.entries.pop(key, None)
                self.attempted.discard(key)
                self.verified.discard(key)
                self.errors.pop(key, None)
                continue  # Normal AP receipt reclaims this entitlement.
            if kind=='runtime_unlock':
                from native_model_transport import configure_detective_scan
                if key not in self.attempted and key not in self.errors:
                    self.attempted.add(key)
                    try:
                        await asyncio.to_thread(configure_detective_scan,session.pid,enabled is True,dll)
                        self.verified.add(key);self.native_ids[key]=0
                        if enabled is None:
                            self.entries.pop(key,None);self.verified.discard(key)
                    except NativePlayerBusy:
                        self.attempted.discard(key);return False
                    except (OSError,ValueError,RuntimeError) as error:self.errors[key]=str(error)
                continue
            if kind == 'model_unlock':
                index = models.get(name)
            elif kind == 'ability_unlock':
                index = ABILITY_NAMES.index(name)
            else:
                index = cheats.get(name, {}).get('index')
            if index is None:
                self.errors[key] = 'Native Item-ID nicht verfügbar'
                if self.errors[key] != self.problem:
                    logging.warning('TEST: %s: native Zuordnung fehlt oder Cheat-Liste nicht geladen.', effect['name'])
                    self.problem = self.errors[key]
                continue
            self.native_ids[key]=index
            observed = self._native_state(kind, name, index, snapshot, inventory, cheats)
            desired = bool(enabled) if enabled is not None else False
            if observed is not None and observed == desired:
                if enabled is None:
                    self.entries.pop(key, None)
                    self.attempted.discard(key)
                    self.errors.pop(key, None)
                    self.verified.discard(key)
                    logging.info('TEST: %s · AP-Zustand für lokale Testfreigabe wiederhergestellt.', effect['name'])
                elif key not in self.verified:
                    self.verified.add(key)
                    self.errors.pop(key, None)
                    logging.info('TEST BESTÄTIGT (Spiel-RAM): %s ist %s. Save-Persistenz nicht separat nachgewiesen.',
                                 effect['name'], 'freigeschaltet' if enabled else 'gesperrt')
                    if enabled and kind == 'model_unlock':
                        logging.info('TEST: Charakter/Fahrzeug nur freigeschaltet, nicht automatisch ausgerüstet. Ingame auswählen.')
                    if enabled and kind == 'cheat_unlock':
                        logging.info('TEST: Red-Brick-Cheat-Besitz bestätigt. Sichtbaren Effekt ggf. im Extras-Menü aktivieren bzw. in passender Spielsituation prüfen.')
                continue
            if key in self.attempted or key in self.errors:
                # A timeout may already have changed memory. Never replay blindly.
                continue
            if observed is None:
                continue  # No safe proof source, do not guess or write.
            self.attempted.add(key)
            try:
                if enabled is not True:
                    await asyncio.to_thread(test_remove, session.pid, kind, index, name, dll)
                elif kind == 'model_unlock':
                    await asyncio.to_thread(grant_model, session.pid, index, name, dll)
                elif kind == 'ability_unlock':
                    await asyncio.to_thread(grant_ability, session.pid, name, dll)
                else:
                    await asyncio.to_thread(grant_cheat, session.pid, index, name, dll)
                logging.info('TEST: Nativer Befehl für %s ausgeführt; prüfe Ergebnis im nächsten Spiel-Snapshot.', effect['name'])
                self.problem = None
            except NativePlayerBusy:
                self.attempted.discard(key)  # Explicit safe busy rejection; no mutation.
                return False
            except (ValueError, OSError, RuntimeError) as error:
                self.errors[key] = str(error)
                self.problem = str(error)
                logging.error('TEST: %s konnte nicht bestätigt werden: %s. Keine automatische Wiederholung.',
                              effect['name'], error)
            return False  # Only one native test mutation per polling iteration.
        return True

    async def verify_save(self,session,path,dll):
        """Prove both grants and removals using the exact bound save, not receipts."""
        import asyncio
        from native_save import read_save,model_saved,ability_saved,cheat_saved
        from native_model_transport import request_save
        from save_reader import read_save_controller
        targets=[(key,effect,enabled) for key,(effect,enabled) in self.entries.items()
                 if enabled is not None and key in self.verified and key not in self.saved and key[0]!='runtime_unlock']
        if not targets and not self.currency_save_pending:return
        try:
            data=await asyncio.to_thread(read_save,path)
            for key,effect,enabled in targets:
                kind,name=key;index=self.native_ids.get(key)
                if index is None:continue
                present=(model_saved(data,index) if kind=='model_unlock' else
                         ability_saved(data,name) if kind=='ability_unlock' else cheat_saved(data,index))
                if present==enabled:
                    self.saved.add(key)
                    from delivery_marker import CHARACTER_SAVE_OFFSET
                    from native_save import ABILITY_CHUNK
                    offset=(CHARACTER_SAVE_OFFSET+0x80+index if kind=='model_unlock' else
                            CHARACTER_SAVE_OFFSET-0x122e0+0xfa80 if kind=='cheat_unlock' else
                            data.find(ABILITY_CHUNK)+len(ABILITY_CHUNK))
                    proof=dict(file=str(path),kind=kind,index=index,owned=present,offset=hex(offset))
                    if kind!='model_unlock':proof['bit']=index
                    if key in self.latest:self.history[self.latest[key]]['proof']=proof
                    logging.info('TEST SAVE BESTÄTIGT: %s · %s · %s',effect['name'],'freigeschaltet' if enabled else 'gesperrt',path)
            pending=tuple((key,enabled) for key,_,enabled in targets if key not in self.saved)
            if self.currency_save_pending or (pending and pending!=self.save_request):
                state=read_save_controller(session.read,session.base)
                if state.get('enabled') and not state.get('requested') and state.get('state',0)==0:
                    await asyncio.to_thread(request_save,session.pid,dll)
                    self.save_request=pending
                    self.currency_save_pending=False
                    logging.info('TEST: Autosave für %s bestätigte Teständerung(en) angefordert.',len(pending))
            self.save_problem=None
        except (OSError,ValueError,RuntimeError) as error:
            if str(error)!=self.save_problem:logging.warning('TEST Save-Prüfung wartet: %s',error)
            self.save_problem=str(error)
