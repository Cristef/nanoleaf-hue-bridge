import socket
import struct
import unittest
from syncplus_relay import stream_payload


def packet(payload, port=60222):
    eth = bytes(12) + b'\x08\x00'
    ip = struct.pack('!BBHHHBBH4s4s', 0x45, 0, 28 + len(payload), 1, 0, 64, 17, 0,
                     socket.inet_aton('192.0.2.10'), socket.inet_aton('192.0.2.11'))
    return eth + ip + struct.pack('!HHHH', 46391, port, 8 + len(payload), 0) + payload


class RelayTests(unittest.TestCase):
    def test_real_format_and_ethernet_padding(self):
        data = b'\x00\x01' + struct.pack('!HBBBBH', 57199, 10, 20, 30, 0, 1)
        self.assertEqual(stream_payload(packet(data) + bytes(20)), data)

    def test_rejects_fragment_truncated_wrong_route_and_non_stream(self):
        data = b'\x00\x01' + struct.pack('!HBBBBH', 1, 10, 20, 30, 0, 1)
        fragment = bytearray(packet(data)); fragment[20:22] = b'\x20\x00'
        wrong_route = bytearray(packet(data)); wrong_route[33] = 59
        for p in (bytes(fragment), bytes(wrong_route), packet(data)[:-1], packet(data, 1900)):
            self.assertIsNone(stream_payload(p))
        with self.assertRaises(ValueError):
            stream_payload(packet(b'\x00\x02' + data[2:]))


if __name__ == '__main__':
    unittest.main()
