from pathlib import Path
import sys
import json
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bridge'))
from monitor_report import event_evidence, export_report


class ReportTests(unittest.TestCase):
    def test_pickup_raw_values_and_where(self):
        a = dict(pickup_bytes=[0, 0])
        b = dict(pickup_bytes=[0, 4], pickup_address='0x100', stats={},
                 location=dict(native_tile='WI_Forest_0704', player_position=[1,2,3]))
        r = event_evidence(dict(identity='pickup:10',kind='superbrick'), a, b)
        e = r['evidence']
        self.assertEqual((e['byte_offset'],e['mask'],e['before'],e['after']), (1,4,0,4))
        self.assertEqual(e['location']['native_tile'], 'WI_Forest_0704')
        report = json.loads(export_report([r]))
        self.assertFalse(report['writes_enabled'])
        self.assertEqual(report['records'][0]['evidence']['payload_address'], '0x100')

    def test_objective_carries_both_native_records(self):
        a = dict(objectives=dict(records=[dict(name_hash=1,bit_index=2,candidate_complete=False)]))
        b = dict(objectives=dict(manager_pointer='0x200',records=[dict(name_hash=1,bit_index=2,candidate_complete=True)]))
        r = event_evidence(dict(identity='objective:1',kind='city_flag'),a,b)['evidence']
        self.assertFalse(r['before']['candidate_complete'])
        self.assertTrue(r['after']['candidate_complete'])
