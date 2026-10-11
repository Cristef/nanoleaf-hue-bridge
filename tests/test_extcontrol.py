import struct
import unittest
from extcontrol_probe import decode_frame


class ExtControlTests(unittest.TestCase):
    def test_big_endian_multi_panel_frame(self):
        data = struct.pack('!H', 2) + struct.pack('!HBBBBH', 57199, 255, 7, 19, 0, 258)
        data += struct.pack('!HBBBBH', 1, 0, 255, 0, 0, 1)
        frame = decode_frame(data)
        self.assertEqual(frame[0], {'panelId': 57199, 'rgb': [255, 7, 19],
                                    'white': 0, 'transition100ms': 258})
        self.assertEqual(frame[1]['panelId'], 1)

    def test_rejects_truncated_extra_and_duplicate_records(self):
        record = struct.pack('!HBBBBH', 1, 2, 3, 4, 0, 0)
        for data in (b'', b'\x00', b'\x00\x00', b'\x00\x01'+record[:-1],
                     b'\x00\x01'+record+b'\x00', b'\x00\x02'+record+record):
            with self.subTest(data=data), self.assertRaises(ValueError):
                decode_frame(data)


if __name__ == '__main__':
    unittest.main()
