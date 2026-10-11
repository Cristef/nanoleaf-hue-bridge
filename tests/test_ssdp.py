import tempfile
import unittest
from pathlib import Path
from nanoleaf_probe import Device, DEVICE_ID
from ssdp_probe import search_type, search_response, notification, NATIVE_TYPE, LEGACY_TYPE


class SSDPTests(unittest.TestCase):
    def test_only_valid_discovery_queries_get_responses(self):
        def request(target, man='"ssdp:discover"'):
            return f'M-SEARCH * HTTP/1.1\r\nST: {target}\r\nMAN: {man}\r\n\r\n'.encode()
        for target in ('ssdp:all', NATIVE_TYPE, LEGACY_TYPE):
            self.assertEqual(search_type(request(target)), target)
            data = search_response('192.0.2.2', 16021, 'virtual-uuid', target)
            self.assertTrue(data.startswith(b'HTTP/1.1 200 OK\r\n'))
            self.assertIn(b'Location: http://192.0.2.2:16021\r\n', data)
            self.assertIn(DEVICE_ID.encode(), data)
            self.assertTrue(data.endswith(b'\r\n\r\n'))
        for data in (request('unknown'), request('ssdp:all', 'invalid'),
                     b'NOTIFY * HTTP/1.1\r\nST: ssdp:all\r\n\r\n', b'x'*4097):
            self.assertIsNone(search_type(data))
        with self.assertRaises(ValueError):
            search_response('192.0.2.2', 16021, 'virtual', 'bad\r\nHeader: injected')

    def test_discovery_identity_survives_restart_and_withdraws(self):
        with tempfile.TemporaryDirectory(prefix='probe-test-', dir=Path(__file__).parent) as folder:
            path = Path(folder)/'state.json'
            device = Device(path)
            device.save()
            self.assertEqual(Device(path).ssdp_uuid, device.ssdp_uuid)
            alive = notification('192.0.2.2', 16021, device.ssdp_uuid)
            withdrawn = notification('192.0.2.2', 16021, device.ssdp_uuid, alive=False)
            self.assertIn(b'NTS: ssdp:alive', alive)
            self.assertIn(b'NTS: ssdp:byebye', withdrawn)
            self.assertIn(('USN: uuid:'+device.ssdp_uuid).encode(), withdrawn)


if __name__ == '__main__':
    unittest.main()
