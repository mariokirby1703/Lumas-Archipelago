from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge'))
from notification_messages import receipt_message,sent_message,item_classification
from client_journal import Journal


class NotificationMessageTests(unittest.TestCase):
    def test_own_and_remote_receipt_exact_text(self):
        self.assertEqual(receipt_message('Grapple Gun',2,1,{2:'Luma'}),
                         'You received Grapple Gun from Luma!')
        self.assertEqual(receipt_message('Grapple Gun',1,1,{1:'Luma'}),
                         'You found your own Grapple Gun!')

    def test_send_resolves_name_in_recipient_game(self):
        lookups=[]
        class Names:
            def lookup_in_slot(self,item,slot):lookups.append((item,slot));return 'Hookshot'
        packet=dict(type='ItemSend',receiving=2,
                    item=SimpleNamespace(item=400,location=123,player=1,flags=1))
        event=sent_message(packet,1,Names(),{2:'Zelda Player'})
        self.assertEqual(event['text'],'You sent Hookshot to Zelda Player!')
        self.assertEqual(event['classification'],'progression')
        self.assertEqual(lookups,[(400,2)])
        packet['receiving']=1
        self.assertIsNone(sent_message(packet,1,Names(),{}),'Own finds use only the receipt notification')
        packet['receiving']=2;packet['item'].player=3
        self.assertIsNone(sent_message(packet,1,Names(),{}),'Do not show other players sending items')
        self.assertIsNone(sent_message(dict(type='Hint'),1,Names(),{}))

    def test_flags_keep_remote_item_classification(self):
        self.assertEqual([item_classification(n) for n in (0,1,2,4,3,5)],
                         ['filler','progression','useful','trap','progression','progression'])

    def test_confirmed_send_persists_and_is_deduplicated_after_reconnect(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory);binding=dict(seed='messages',team=0,slot=1)
            journal=Journal(path,binding)
            event=dict(key='sent:1:123:2:400',text='You sent Hookshot to Zelda Player!',classification='progression')
            journal.queue_sent_popup(event);journal.queue_sent_popup(event)
            row=journal.next_popup();self.assertEqual(row['text'],event['text'])
            journal.popup_state(row['index'],'submitted');journal.close()
            journal=Journal(path,binding)
            journal.queue_sent_popup(event)
            self.assertIsNone(journal.next_popup())
            self.assertEqual(journal.db.execute('SELECT COUNT(*) FROM receipts').fetchone()[0],0)
            journal.close()

    def test_queued_receipt_text_updates_without_replaying_history(self):
        with tempfile.TemporaryDirectory() as directory:
            journal=Journal(Path(directory),dict(seed='messages',team=0,slot=1))
            journal.receipt(0,SimpleNamespace(item=1,location=2,player=1))
            journal.plan_delivery(0,dict(kind='ability_unlock',ability='Jetpack'))
            effect=dict(name='Jetpack',classification='progression')
            journal.queue_popup(0,effect)
            journal.record_memory_verification(0,dict(verified=True))
            journal.queue_popup(0,effect,'You found your own Jetpack!')
            self.assertEqual(journal.next_popup()['text'],'You found your own Jetpack!')
            journal.popup_state(0,'submitted')
            journal.queue_popup(0,effect,'You found your own Jetpack!')
            self.assertIsNone(journal.next_popup());journal.close()
