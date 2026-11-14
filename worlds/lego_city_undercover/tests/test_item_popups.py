"""Notification transport/reconnect tests; never touch the game or native save."""
import asyncio
from pathlib import Path
import struct
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge'))
from client_journal import Journal
from item_popups import ItemPopupQueue,popup_packet,CLASS_IDS
from native_model_transport import NativePlayerBusy
from native_context_policy import allows_native_command


class PopupTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.binding=dict(seed='popup-test',team=0,slot=2)
        self.journal=Journal(Path(self.tmp.name),self.binding)
        self.addCleanup(lambda:self.journal.close())
        self.queue=ItemPopupQueue();self.session=SimpleNamespace(pid=123)
        self.snapshot=dict(actor=dict(context=dict(index=46)))

    def receipt(self,index=0,classification='progression'):
        self.journal.receipt(index,SimpleNamespace(item=42,location=5,player=1))
        self.journal.plan_delivery(index,dict(kind='ability_unlock',ability='Jetpack'))
        self.journal.queue_popup(index,dict(name='Ability: Jetpack',classification=classification))

    def ready(self):
        self.journal.record_memory_verification(0,dict(verified=True))

    def test_text_is_bounded_valid_utf8_and_tags_are_removed(self):
        data=popup_packet(123,'[red]<script>\x00'+'Ä'*300,True)
        magic,version,pid,channel,duration,length,_,_=struct.unpack_from('<8I',data)
        self.assertEqual((pid,channel,duration),(123,3,6))
        self.assertEqual(len(data),320);self.assertLessEqual(length,287)
        text=data[32:32+length].decode('utf-8')
        self.assertNotIn('<',text);self.assertNotIn('[',text)
        self.assertEqual(data[32+length],0)
        self.assertEqual(struct.unpack_from('<I',popup_packet(123,'Studs',False),12)[0],3)

    def test_all_classes_share_confirmed_message_channel_with_distinct_tints(self):
        for classification,ident in CLASS_IDS.items():
            fields=struct.unpack_from('<8I',popup_packet(123,'AP Item',classification))
            self.assertEqual(fields[1],2)
            self.assertEqual(fields[3],3,'Never use the criminal-scan hint channel')
            self.assertEqual(fields[4],6 if classification=='progression' else 3)
            self.assertEqual(fields[6],ident)
        with self.assertRaises(ValueError):popup_packet(123,'Item','unknown')

    def test_useful_class_survives_reconnect_and_applied_waiting_migration(self):
        self.receipt(classification='useful');self.ready()
        self.journal.db.execute("UPDATE deliveries SET state='applied'")
        self.journal.db.execute("UPDATE item_popups SET classification='filler'")
        self.journal.db.commit()
        self.journal.queue_popup(0,dict(name='Ability: Jetpack',classification='useful'))
        self.journal.close();self.journal=Journal(Path(self.tmp.name),self.binding)
        self.assertEqual(self.journal.next_popup()['classification'],'useful')

    def test_old_popup_table_migrates_without_replaying_displayed_items(self):
        self.journal.db.execute('DROP TABLE item_popups')
        self.journal.db.execute("CREATE TABLE item_popups (server_index INTEGER PRIMARY KEY,text TEXT,progression INTEGER,state TEXT)")
        self.journal.db.execute("INSERT INTO item_popups VALUES (4,'old',1,'submitted')")
        self.journal.db.commit();self.journal.close()
        self.journal=Journal(Path(self.tmp.name),self.binding)
        row=self.journal.db.execute('SELECT classification,state FROM item_popups').fetchone()
        self.assertEqual(row,('progression','submitted'))

    async def test_receipt_displays_while_native_grant_or_save_is_pending_and_only_once(self):
        self.receipt()
        with patch('item_popups.show_item_popup',return_value=True) as show:
            await self.queue.poll(self.session,self.snapshot,self.journal,None)
            self.assertEqual(show.call_count,1)
            self.ready()
            await self.queue.poll(self.session,self.snapshot,self.journal,None)
            self.queue.next_at=0
            await self.queue.poll(self.session,self.snapshot,self.journal,None)
            self.assertEqual(show.call_count,1)
        self.assertIsNone(self.journal.next_popup())

    async def test_busy_is_retryable_but_timeout_is_not(self):
        self.receipt();self.ready()
        with patch('item_popups.show_item_popup',side_effect=NativePlayerBusy('busy')):
            await self.queue.poll(self.session,self.snapshot,self.journal,None)
        self.assertIsNotNone(self.journal.next_popup())
        with patch('item_popups.show_item_popup',side_effect=RuntimeError('timed out')):
            await self.queue.poll(self.session,self.snapshot,self.journal,None)
        self.assertIsNone(self.journal.next_popup())

    async def test_occupied_channel_defers_without_losing_notification(self):
        self.receipt();self.ready()
        with patch('item_popups.show_item_popup',return_value=False):
            await self.queue.poll(self.session,self.snapshot,self.journal,None)
        self.assertIsNotNone(self.journal.next_popup())

    async def test_disabled_and_interaction_do_not_dispatch(self):
        self.receipt();self.ready()
        with patch('item_popups.show_item_popup') as show:
            await self.queue.poll(self.session,self.snapshot,self.journal,None,False)
            await self.queue.poll(self.session,dict(actor=dict(context=dict(index=25))),self.journal,None)
            show.assert_not_called()
        self.assertFalse(allows_native_command(25,19))
        self.assertTrue(allows_native_command(157,19))
        self.assertFalse(allows_native_command(157,20),'Vehicle popups must not enable detective mutations')

    async def test_vehicle_contexts_can_display_receipts_without_changing_grant_rules(self):
        for context in (11,27,157):
            self.queue=ItemPopupQueue();self.queue.preview('filler')
            with patch('item_popups.show_item_popup',return_value=True) as show:
                await self.queue.poll(self.session,dict(actor=dict(context=dict(index=context))),self.journal,None)
                show.assert_called_once()
            self.assertTrue(allows_native_command(context,19))
            self.assertFalse(allows_native_command(context,8))
            self.assertFalse(allows_native_command(context,20))

    def test_interrupted_dispatch_and_history_do_not_replay_after_restart(self):
        self.receipt();self.ready();self.journal.popup_state(0,'dispatching')
        self.journal.close()
        self.journal=Journal(Path(self.tmp.name),self.binding)
        self.assertIsNone(self.journal.next_popup())
        self.journal.db.execute("UPDATE deliveries SET state='applied'")
        self.journal.db.execute('DELETE FROM item_popups');self.journal.db.commit()
        self.journal.queue_popup(0,dict(name='Old item',classification='progression'))
        self.assertIsNone(self.journal.next_popup())

    async def test_previews_never_create_receipts_or_grants(self):
        self.queue.preview(True)
        with patch('item_popups.show_item_popup',return_value=True) as show:
            await self.queue.poll(self.session,self.snapshot,self.journal,None)
            self.assertIn('Wurfhakenkanone',show.call_args.args[1])
        self.assertEqual(self.journal.db.execute('SELECT COUNT(*) FROM receipts').fetchone()[0],0)

    async def test_useful_and_filler_previews_pass_actual_classification(self):
        for classification in ('useful','filler'):
            self.queue.next_at=0;self.queue.preview(classification)
            with patch('item_popups.show_item_popup',return_value=True) as show:
                await self.queue.poll(self.session,self.snapshot,self.journal,None)
                self.assertEqual(show.call_args.args[2],classification)


if __name__=='__main__':unittest.main()
