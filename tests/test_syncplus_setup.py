import base64
import copy
import struct
import unittest
from syncplus_setup import layout_string, updated_config


class SyncPlusSetupTests(unittest.TestCase):
    def setUp(self):
        self.layout = {'numPanels': 1, 'sideLength': 67, 'positionData': [
            {'panelId': 9, 'x': -12, 'y': 34, 'o': 60, 'shapeType': 7}]}
        self.before = {'box': {'x': 640, 'y': 360, 'z': 100}, 'vendor': 3,
            'devices': [{'deviceId': 'physical', 'layoutString': 'keep',
                'authToken': 'existing-secret', 'centroidOffset': {'x': 44}, 'enabled': False}]}

    def test_registration_preserves_other_receivers_and_is_idempotent(self):
        original = copy.deepcopy(self.before)
        first = updated_config(self.before, 'virtual', '192.168.10.93', 'test-secret', self.layout)
        self.assertEqual(self.before, original)
        self.assertEqual(first['devices'][0], original['devices'][0])
        self.assertEqual(first['box'], original['box'])
        self.assertEqual(first['vendor'], 3)
        self.assertTrue(all(type(v) is int for v in first['devices'][1]['centroidOffset'].values()))
        self.assertEqual(first['devices'][1]['centroidOffset'], {'x': 320, 'y': 180, 'z': 50})
        self.assertEqual(updated_config(first, 'virtual', '192.168.10.93', 'test-secret', self.layout), first)

    def test_existing_position_is_retained(self):
        first = updated_config(self.before, 'virtual', '192.168.10.93', 'test-secret', self.layout)
        first['devices'][1]['centroidOffset']['x'] = 19
        next_config = updated_config(first, 'virtual', '192.168.10.94', 'replacement', self.layout)
        self.assertEqual(next_config['devices'][1]['centroidOffset']['x'], 19)
        self.assertEqual(next_config['devices'][0], self.before['devices'][0])

    def test_layout_tlv_uses_signed_coordinates(self):
        raw = base64.b64decode(layout_string(self.layout))
        self.assertEqual(raw[:5], struct.pack('!BHH', 1, 2, 1))
        self.assertEqual(raw[13:], struct.pack('!HiiHB', 9, -12, 34, 60, 7))

    def test_ambiguous_or_uncalibrated_configuration_fails(self):
        for config in [{'devices': []}, {'box': {'x': 0, 'y': 2, 'z': 3}, 'devices': []},
                       {'devices': [{'deviceId': 'virtual'}, {'deviceId': 'virtual'}]}]:
            with self.assertRaises(ValueError):
                updated_config(config, 'virtual', '192.168.10.93', 'test', self.layout)


if __name__ == '__main__':
    unittest.main()
