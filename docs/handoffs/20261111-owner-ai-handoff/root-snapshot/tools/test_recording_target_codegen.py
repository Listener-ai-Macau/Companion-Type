"""Retiring optional speed goals must not strand the packaged OTA contract."""
import copy
import json
import unittest
from pathlib import Path
from render_product_backlog import render_recording_targets, performance_contract_sha


class RecordingTargetGeneration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads((Path(__file__).resolve().parents[1] / 'docs/product_backlog.json').read_bytes())

    def test_current_frozen_contract_without_peak_goals_generates(self):
        q = self.data['quality_targets']
        self.assertEqual(q['frozen_contract']['sha256'], performance_contract_sha(q))
        text = render_recording_targets(self.data)
        self.assertIn(q['frozen_contract']['version'], text)
        # Owner's current OTA contract is60KiB/s. The retired100 goal must
        # not return when we keep this pure historical codegen utility.
        self.assertIn('OTA_PAYLOAD_DELIVERY_KIB_S: f64 = 60.0;', text)
        self.assertIn('OTA_PAYLOAD_DELIVERY_STRICT: bool = true;', text)
        self.assertIn('PAYLOAD_STRETCH_KIB_S: Option<f64> = None;', text)
        self.assertIn('PAYLOAD_EXPLORE_KIB_S: Option<f64> = None;', text)

    def test_explicit_optional_values_are_preserved_not_invented(self):
        d = copy.deepcopy(self.data)
        values = next(t for t in d['quality_targets']['items'] if t['id'] == 'QM11')['values']
        values.update(payload_stretch_kib_s=110, payload_explore_kib_s=120)
        text = render_recording_targets(d)
        self.assertIn('PAYLOAD_STRETCH_KIB_S: Option<f64> = Some(110.0);', text)
        self.assertIn('PAYLOAD_EXPLORE_KIB_S: Option<f64> = Some(120.0);', text)
        values['payload_explore_kib_s'] = 90
        with self.assertRaises(AssertionError):
            render_recording_targets(d)


if __name__ == '__main__':
    unittest.main()
