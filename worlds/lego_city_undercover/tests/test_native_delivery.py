import asyncio
import json
from pathlib import Path
import struct
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge'))
from client_journal import Journal
from delivery_marker import (binding_token,parse_marker,receipt_saved,marker_from_save,
                             CHARACTER_SAVE_OFFSET,MARKER_OFFSET,NATIVE_SAVE_SIZE)
from native_save import model_saved,cheat_saved,ability_saved,ABILITY_CHUNK,ensure_backup
from native_delivery import NativeDeliveryEngine
from reward_policy import reward_masks,encode_policy,POLICY
from research_profile import ABILITY_NAMES
from native_model_transport import grant_currency_batch


def blank_save(marker=bytes(22)):
    data=bytearray(NATIVE_SAVE_SIZE);data[:8]=b'HMGR\x01\0\0\0'
    offset=CHARACTER_SAVE_OFFSET+MARKER_OFFSET;data[offset:offset+22]=marker
    return bytes(data)


class MarkerTests(unittest.TestCase):
    def test_currency_batch_encodes_mixed_packages_once_and_rejects_reordering(self):
        rows=[dict(index=1,plan=dict(kind='add_studs',amount=1000)),
              dict(index=9,plan=dict(kind='add_bricks',amount=250))]
        with patch('native_model_transport._policy_command',return_value=dict(changes=2)) as rpc:
            result=grant_currency_batch(7,rows,b'x'*16,Path('test.dll'))
            self.assertEqual(rpc.call_count,1);self.assertEqual(result['credited'],2)
            packet=rpc.call_args.args[1]
            self.assertEqual(len(packet),320)
            self.assertEqual(struct.unpack_from('<4I',packet),(0x4c435542,1,7,2))
            self.assertEqual(struct.unpack_from('<6I',packet,32),(1,6,1000,9,7,250))
            with self.assertRaises(ValueError):grant_currency_batch(7,list(reversed(rows)),b'x'*16,Path('test.dll'))
            with self.assertRaises(ValueError):grant_currency_batch(7,rows*13,b'x'*16,Path('test.dll'))
    def test_backup_is_preserved_and_corruption_stops_reuse(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);slot=root/'slot1';slot.mkdir()
            source=slot/'game1.legocityundercoversavegamedata';source.write_bytes(blank_save())
            backup=root/'backup';ensure_backup(source,backup)
            original=(backup/source.name).read_bytes()
            changed=bytearray(blank_save());changed[-1]=1;source.write_bytes(changed)
            ensure_backup(source,backup)
            self.assertEqual((backup/source.name).read_bytes(),original)
            (backup/source.name).write_bytes(b'corrupt')
            with self.assertRaises(RuntimeError):ensure_backup(source,backup)

    def test_marker_is_bound_to_seed_and_server_index(self):
        token=binding_token(dict(seed='a',team=0,slot=1))
        marker=b'AP'+token+struct.pack('<I',12)
        self.assertTrue(receipt_saved(marker,token,11))
        self.assertFalse(receipt_saved(marker,token,12))
        self.assertFalse(receipt_saved(marker,binding_token(dict(seed='b',team=0,slot=1)),11))
        self.assertIsNone(parse_marker(bytes(22)))
        with self.assertRaises(ValueError):parse_marker(b'x'*22)
        with self.assertRaises(ValueError):marker_from_save(b'HMGR')
        self.assertEqual(marker_from_save(blank_save(marker)),marker)

    def test_model_disk_proof_is_owned_not_found(self):
        data=bytearray(blank_save());model=270
        data[CHARACTER_SAVE_OFFSET+model//8]|=1<<(model%8)
        self.assertFalse(model_saved(data,model))
        data[CHARACTER_SAVE_OFFSET+0x80+model]=1
        self.assertTrue(model_saved(data,model))
        with self.assertRaises(ValueError):model_saved(data,1002)

    def test_ability_save_proof_requires_existing_not_pending(self):
        data=bytearray(blank_save());offset=0x70000;index=ABILITY_NAMES.index('Scanner')
        data[offset:offset+len(ABILITY_CHUNK)]=ABILITY_CHUNK
        struct.pack_into('<QQ',data,offset+len(ABILITY_CHUNK),0,1<<index)
        self.assertFalse(ability_saved(data,'Scanner'))
        struct.pack_into('<QQ',data,offset+len(ABILITY_CHUNK),1<<index,0)
        self.assertTrue(ability_saved(data,'Scanner'))
        data[offset+100:offset+100+len(ABILITY_CHUNK)]=ABILITY_CHUNK
        with self.assertRaises(ValueError):ability_saved(data,'Scanner')

    def test_cheat_save_proof_requires_ownership_not_discovery(self):
        data=bytearray(blank_save());profile=CHARACTER_SAVE_OFFSET-0x122e0
        struct.pack_into('<Q',data,profile+0xfa70,1<<11)
        self.assertFalse(cheat_saved(data,11))
        struct.pack_into('<Q',data,profile+0xfa80,1<<11)
        self.assertTrue(cheat_saved(data,11))

    def test_policy_keeps_starting_civilian_and_respects_class_alias_receipts(self):
        effects=[dict(name='Character: CIVILIAN_CHASEMCCAIN',category='character',native_name='CIVILIAN_CHASEMCCAIN'),
                 dict(name='Ability: Miner',category='ability'),
                 dict(name='Ability: Map',category='ability'),
                 dict(name='Ability: Scanner',category='ability'),
                 dict(name='Red Brick Cheat: Studs x2',category='cheat',native_name='CHEAT_SCOREX2')]
        received=[dict(name='Character: MINER',category='character',native_name='MINER')]
        masks=reward_masks(effects,received,{'MINER':237,'CIVILIAN_CHASEMCCAIN':244},
                           [dict(native_name='CHEAT_SCOREX2',index=11)],dict(ability_items=True,cheat_items=True))
        self.assertEqual(masks['managed_models'],{237});self.assertEqual(masks['entitled_models'],{237})
        self.assertNotIn(ABILITY_NAMES.index('Map'),masks['managed_abilities'])
        self.assertIn(ABILITY_NAMES.index('Scanner'),masks['managed_abilities'])
        self.assertEqual(masks['managed_cheats'],{11});self.assertFalse(masks['entitled_cheats'])
        packet=encode_policy(7,b'x'*16,masks)
        self.assertEqual(len(packet),320);self.assertEqual(POLICY.unpack(packet)[:4],(0x4c435550,1,7,0))


class ReconciliationTests(unittest.TestCase):
    def run_game(self,crash_first=False,context=46):
        with tempfile.TemporaryDirectory() as directory:
            journal=Journal(Path(directory),dict(seed='currency-replay',team=0,slot=1))
            for i,amount in enumerate((1000,10000)):
                journal.receipt(i,SimpleNamespace(item=i,location=i,player=1))
                journal.plan_delivery(i,dict(kind='add_studs',amount=amount))
            engine=NativeDeliveryEngine(Path('test.dll'))
            game=SimpleNamespace(marker=bytes(22),disk=blank_save(),balance=0,calls=[],crashed=False,batches=[])
            base=0x10000000;bank=0x30000
            def read(address,size):
                if address==base+0x1c7f160:return struct.pack('<Q',0x20000)
                if address==base+0x1c7cbb8:return struct.pack('<Q',bank)
                if address==bank+MARKER_OFFSET:return game.marker
                raise AssertionError((hex(address),size))
            session=SimpleNamespace(pid=7,base=base,read=read)
            snapshot=dict(actor=dict(context=dict(index=context)),characters=[],cheats=dict(records=[]))
            def credit(pid,kind,amount,dll,index,token):
                game.calls.append(index)
                if not receipt_saved(game.marker,token,index):
                    game.balance+=amount;game.marker=b'AP'+token+struct.pack('<I',index+1)
                if crash_first and not game.crashed:
                    game.crashed=True;raise RuntimeError('Lost response after native credit')
                return dict(verified=True,save_requested=True,save_confirmed=False)
            def save(pid,dll):
                game.disk=blank_save(game.marker)
                return dict(requested=True,save_confirmed=False)
            def batch_credit(pid,rows,token,dll):
                game.batches.append([r['index'] for r in rows])
                for row in rows:credit(pid,row['plan']['kind'],row['plan']['amount'],dll,row['index'],token)
                return dict(verified=True,credited=len(rows),save_confirmed=False)
            async def poll():await engine.poll(session,snapshot,journal)
            with patch('native_delivery.resolve_save',return_value=Path('game1.test')),\
                 patch('native_delivery.ensure_backup'),\
                 patch('native_delivery.read_save',side_effect=lambda _:game.disk),\
                 patch('native_delivery.read_model_ids',return_value={}),\
                 patch('native_delivery.ownership_selection_supported',return_value=True),\
                 patch('native_delivery.enforce_rewards',return_value=dict(changes=0,switch_requested=False)) as enforcement,\
                 patch('native_delivery.read_save_controller',return_value=dict(enabled=True,requested=False)),\
                 patch('native_delivery.grant_currency_batch',side_effect=batch_credit),\
                 patch('native_delivery.request_save',side_effect=save):
                if crash_first:
                    with self.assertRaisesRegex(RuntimeError,'Lost response'):asyncio.run(poll())
                    journal.close();journal=Journal(Path(directory),dict(seed='currency-replay',team=0,slot=1))
                    engine=NativeDeliveryEngine(Path('test.dll'))
                for _ in range(8):asyncio.run(poll())
                self.assertEqual(game.balance,11000);self.assertEqual(game.calls,[0,1])
                self.assertEqual(game.batches,[[0,1],[1]] if crash_first else [[0,1]])
                self.assertEqual([d['state'] for d in journal.reconciliation_deliveries()],['applied','applied'])
                self.assertFalse(journal.pending_deliveries())
                # An older native save also restores its watermark. Reconcile
                # already-applied AP receipts without losing or doubling cash.
                game.marker=b'AP'+journal.binding_token+struct.pack('<I',1)
                game.disk=blank_save(game.marker);game.balance=1000
                for _ in range(5):asyncio.run(poll())
                self.assertEqual(game.balance,11000);self.assertEqual(game.calls,[0,1,1])
                if context!=46:enforcement.assert_not_called()
            journal.close()

    def test_currency_persists_in_ride_object_without_reward_revocation(self):self.run_game(context=157)
    def test_currency_persists_in_drop_point_without_reward_revocation(self):self.run_game(context=27)
    def test_currency_persists_once_and_recovers_older_save(self):self.run_game()
    def test_lost_native_response_and_journal_restart_do_not_duplicate_currency(self):self.run_game(True)


class BusyDeliveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_busy_native_command_defers_without_losing_engine_state(self):
        from unittest.mock import AsyncMock
        from native_model_transport import NativePlayerBusy
        engine=NativeDeliveryEngine(Path('test.dll'))
        engine.path=Path('bound-save');engine.requested.add(103)
        engine.identity=('existing-session',)
        args=(object(),object(),object())
        engine._poll=AsyncMock(side_effect=[NativePlayerBusy(),None])
        with self.assertNoLogs(level='WARNING'):
            await engine.poll(*args)
            await engine.poll(*args)
        self.assertEqual(engine._poll.await_count,2)
        self.assertEqual(engine.path,Path('bound-save'))
        self.assertEqual(engine.requested,{103})
        self.assertEqual(engine.identity,('existing-session',))
        self.assertIs(engine._poll.await_args_list[0].args[0],args[0])
        self.assertIs(engine._poll.await_args_list[1].args[0],args[0])

    async def test_other_native_errors_are_not_silenced(self):
        from unittest.mock import AsyncMock
        engine=NativeDeliveryEngine(Path('test.dll'))
        engine._poll=AsyncMock(side_effect=RuntimeError('native signature mismatch'))
        with self.assertRaisesRegex(RuntimeError,'signature mismatch'):
            await engine.poll(None,None,None)
