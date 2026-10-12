import struct
import unittest
from unittest.mock import Mock
from direct_sync_receiver import DirectReceiver, decode


class DirectTests(unittest.TestCase):
    def test_corrupt_and_duplicate_frames_rejected(self):
        record = struct.pack('!HBBBBH', 1, 10, 20, 30, 0, 1)
        self.assertEqual(decode(b'\x00\x01' + record), {1: [10, 20, 30]})
        for data in (b'', b'\x00\x00', b'\x00\x02'+record,
                     b'\x00\x02'+record+record):
            with self.assertRaises(ValueError):
                decode(data)

    def test_wrong_source_and_invalid_frame_do_not_replace_last_colors(self):
        receiver = DirectReceiver('127.0.0.1', '192.0.2.1')
        self.addCleanup(receiver.socket.close)
        data = struct.pack('!HHBBBBH', 1, 1, 10, 20, 30, 0, 1)
        self.assertTrue(receiver.accept(data, ('192.0.2.1', 40000)))
        self.assertFalse(receiver.accept(data, ('192.0.2.2', 40000)))
        self.assertFalse(receiver.accept(b'bad', ('192.0.2.1', 40000)))
        self.assertEqual(receiver.status()['panels'], {1: [10, 20, 30]})
        self.assertEqual(receiver.status()['accepted'], 1)

    def test_forwarding_requires_enabled_state_and_valid_source_and_panels(self):
        enabled = Mock(return_value=False)
        receiver = DirectReceiver('127.0.0.1', '192.0.2.1', panel_ids=[1], enabled=enabled)
        self.addCleanup(receiver.socket.close)
        receiver.output = Mock()
        data = struct.pack('!HHBBBBH', 1, 1, 10, 20, 30, 0, 1)
        receiver.accept(data, ('192.0.2.1', 40000))
        receiver.output.sendto.assert_not_called()
        enabled.return_value = True
        receiver.accept(data, ('192.0.2.1', 40000))
        receiver.output.sendto.assert_called_once_with(data, ('127.0.0.1', 60223))
        receiver.accept(data, ('192.0.2.2', 40000))
        receiver.accept(struct.pack('!HHBBBBH', 1, 2, 1, 2, 3, 0, 1), ('192.0.2.1', 40000))
        self.assertEqual(receiver.forwarded, 1)
        receiver.output.sendto.side_effect = OSError('Temporary output error')
        self.assertTrue(receiver.accept(data, ('192.0.2.1', 40000)))
        self.assertEqual(receiver.status()['forwardErrors'], 1)


if __name__ == '__main__':
    unittest.main()
