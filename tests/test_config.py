import copy
import unittest
from config import CONFIG, validate


class ConfigTests(unittest.TestCase):
    def test_custom_addresses_and_mac_normalization(self):
        data = copy.deepcopy(CONFIG)
        data['source_mac'] = 'AA:BB:CC:DD:EE:10'
        self.assertEqual(validate(data)['source_mac'], 'aa:bb:cc:dd:ee:10')

    def test_rejects_conflicting_devices_bad_identity_interface_and_area(self):
        for key, value in [('source_ip', CONFIG['ip']), ('source_mac', CONFIG['target_mac']),
                           ('target_mac', 'ff:ff:ff:ff:ff:ff'), ('interface', 'eth0; reboot'),
                           ('identity', '00:00:00:00:00:00'), ('hue_area', 'invalid')]:
            data = copy.deepcopy(CONFIG); data[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate(data)
