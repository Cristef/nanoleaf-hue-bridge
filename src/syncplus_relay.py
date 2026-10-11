"""Scoped experimental relay of configured 4D -> Shapes IPv4 traffic.

Forwards original traffic first, copies validated RGB frames to loopback UDP60223.
Restores ARP on normal exit, SIGINT, SIGTERM and exceptions. Not crash/power-loss
safe for an entire host outage. The systemd unit adds crash recovery and restore.
"""
import argparse
import json
import os
from pathlib import Path
import signal
import socket
import struct
import subprocess
import time

from extcontrol_probe import decode_frame

from config import CONFIG
DEVICES = {CONFIG["source_ip"]: CONFIG["source_mac"],
           CONFIG["target_ip"]: CONFIG["target_mac"]}


def mac(value):
    return bytes.fromhex(value.replace(':', ''))


def arp_reply(local, target_ip, sender_ip, sender_mac):
    target = mac(DEVICES[target_ip])
    return target + local + b'\x08\x06' + struct.pack(
        '!HHBBH6s4s6s4s', 1, 0x0800, 6, 4, 2, sender_mac,
        socket.inet_aton(sender_ip), target, socket.inet_aton(target_ip))


def stream_payload(packet):
    """Accept only complete, unfragmented native 4D->Shapes UDP60222 frames."""
    if len(packet) < 42 or packet[12:14] != b'\x08\x00':
        return None
    if packet[14] >> 4 != 4 or packet[23] != 17:
        return None
    ihl = (packet[14] & 15) * 4
    total = struct.unpack_from('!H', packet, 16)[0]
    fragments = struct.unpack_from('!H', packet, 20)[0]
    if ihl < 20 or total < ihl + 8 or len(packet) < 14 + total or fragments & 0x3fff:
        return None
    if packet[26:34] != socket.inet_aton(CONFIG["source_ip"]) + socket.inet_aton(CONFIG["target_ip"]):
        return None
    offset = 14 + ihl
    _, port, length = struct.unpack_from('!HHH', packet, offset)
    if port != 60222 or length < 8 or length != total - ihl:
        return None
    payload = packet[offset + 8:offset + length]
    decode_frame(payload)
    return payload


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seconds', type=int, default=60)
    parser.add_argument('--continuous', action='store_true')
    parser.add_argument('--restore', action='store_true')
    parser.add_argument('--latest', default=os.environ.get('SYNC_LATEST', '/run/nanoleaf-hue/latest.json'))
    args = parser.parse_args()
    if args.restore:
        local = mac(Path("/sys/class/net/" + CONFIG["interface"] + "/address").read_text().strip())
        with socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(3)) as raw:
            raw.bind((CONFIG["interface"], 0))
            for _ in range(3):
                for recipient in DEVICES:
                    sender = next(ip for ip in DEVICES if ip != recipient)
                    raw.send(arp_reply(local, recipient, sender, mac(DEVICES[sender])))
                time.sleep(0.2)
        print('Original ARP associations restored', flush=True)
        return
    if not 1 <= args.seconds <= 3600:
        parser.error('duration must be 1..3600 seconds')
    os.umask(0o077)
    for ip, expected in DEVICES.items():
        subprocess.run(['ping', '-c', '1', '-W', '1', ip], stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, check=False)
        neighbors = json.loads(subprocess.check_output(['ip', '-j', 'neigh', 'show',
                                                       'to', ip, 'dev', CONFIG["interface"]]))
        if not any(n.get('lladdr', '').lower() == expected for n in neighbors):
            raise RuntimeError('device MAC verification failed; refusing ARP changes')
    local = mac(Path("/sys/class/net/" + CONFIG["interface"] + "/address").read_text().strip())
    stopped = False

    def stop(signum, frame):
        nonlocal stopped
        stopped = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    counts = {'forwarded': 0, 'decoded': 0, 'invalid': 0}
    latest = None
    last_frame_time = None
    target = Path(args.latest)
    target.parent.mkdir(parents=True, exist_ok=True)
    with socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(3)) as raw, \
            socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as copy:
        raw.bind((CONFIG["interface"], 0))
        raw.settimeout(0.05)
        deadline = float('inf') if args.continuous else time.monotonic() + args.seconds
        next_arp = next_status = 0
        try:
            print('Scoped relay started; native traffic preserved;',
                  'continuous' if args.continuous else f'duration {args.seconds}s', flush=True)
            while not stopped and time.monotonic() < deadline:
                now = time.monotonic()
                if now >= next_arp:
                    for recipient in DEVICES:
                        sender = next(ip for ip in DEVICES if ip != recipient)
                        raw.send(arp_reply(local, recipient, sender, local))
                    next_arp = now + 2
                if now >= next_status:
                    temporary = target.with_suffix('.tmp')
                    temporary.write_text(json.dumps({'time': time.time(), 'counts': counts,
                                                      'lastFrameTime': last_frame_time,
                                                      'panels': latest}), encoding='utf-8')
                    temporary.replace(target)
                    next_status = now + 1
                try:
                    packet, address = raw.recvfrom(65535)
                except socket.timeout:
                    continue
                if address[2] == socket.PACKET_OUTGOING or len(packet) < 34:
                    continue
                if packet[:6] != local or packet[12:14] != b'\x08\x00':
                    continue
                src = socket.inet_ntoa(packet[26:30]); dst = socket.inet_ntoa(packet[30:34])
                if src == dst or src not in DEVICES or dst not in DEVICES:
                    continue
                if packet[6:12] != mac(DEVICES[src]):
                    continue
                raw.send(mac(DEVICES[dst]) + local + packet[12:])
                counts['forwarded'] += 1
                try:
                    payload = stream_payload(packet)
                except ValueError:
                    counts['invalid'] += 1
                    continue
                if payload is not None:
                    latest = decode_frame(payload)
                    last_frame_time = time.time()
                    counts['decoded'] += 1
                    copy.sendto(payload, ('127.0.0.1', 60223))
        finally:
            for _ in range(3):
                for recipient in DEVICES:
                    sender = next(ip for ip in DEVICES if ip != recipient)
                    raw.send(arp_reply(local, recipient, sender, mac(DEVICES[sender])))
                time.sleep(0.2)
            print(json.dumps({'arpRestored': True, 'counts': counts}), flush=True)


if __name__ == '__main__':
    main()
