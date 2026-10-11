"""Passive diagnostic for documented extControl v2; not a Sync+ implementation.

Source: Nanoleaf Light Panels Open API, External Control section.
Frame: big-endian uint16 count, then count records of !HBBBBH.
Never sends commands to physical lights or claims discovery/pairing support.
"""
from config import CONFIG
import argparse
import json
import socket
import struct
import time


def decode_frame(data):
    if len(data) < 2:
        raise ValueError('missing panel count')
    count = struct.unpack_from('!H', data)[0]
    if not 1 <= count <= 1024 or len(data) != 2 + count * 8:
        raise ValueError('invalid count or frame length')
    panels = []
    seen = set()
    for offset in range(2, len(data), 8):
        panel, red, green, blue, white, transition = struct.unpack_from('!HBBBBH', data, offset)
        if panel in seen:
            raise ValueError('duplicate panel ID')
        seen.add(panel)
        panels.append({'panelId': panel, 'rgb': [red, green, blue],
                       'white': white, 'transition100ms': transition})
    return panels


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bind', default=CONFIG["ip"])
    parser.add_argument('--source', default=CONFIG["source_ip"])
    parser.add_argument('--seconds', type=int, default=60)
    args = parser.parse_args()
    counts = {'accepted': 0, 'invalid': 0, 'otherSource': 0}
    last = None
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as server:
        server.bind((args.bind, 60222))
        server.settimeout(0.5)
        print('Passive IPv4 extControl v2 diagnostic listening on port 60222', flush=True)
        deadline = time.monotonic() + args.seconds
        while time.monotonic() < deadline:
            try:
                data, peer = server.recvfrom(65535)
            except socket.timeout:
                continue
            if peer[0] != args.source:
                counts['otherSource'] += 1
                continue
            try:
                last = decode_frame(data)
                counts['accepted'] += 1
            except ValueError:
                counts['invalid'] += 1
        print(json.dumps({'counts': counts, 'lastFrame': last}), flush=True)


if __name__ == '__main__':
    main()
