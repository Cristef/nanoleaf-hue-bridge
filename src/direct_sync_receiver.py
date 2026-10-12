"""Receive validated direct Sync+ frames and optionally forward them to Hue."""
import socket
import struct
import threading
import time


def decode(data):
    if len(data) < 2:
        raise ValueError('Missing count')
    count = struct.unpack_from('!H', data)[0]
    if not 1 <= count <= 1024 or len(data) != 2 + count * 8:
        raise ValueError('Invalid frame length')
    panels = {}
    for offset in range(2, len(data), 8):
        panel, red, green, blue, white, transition = struct.unpack_from('!HBBBBH', data, offset)
        if panel in panels:
            raise ValueError('Duplicate panel')
        panels[panel] = [red, green, blue]
    return panels


class DirectReceiver:
    def __init__(self, bind, source, forward=False, enabled=lambda: True, panel_ids=None):
        self.bind = bind
        self.source = source
        self.forward = forward
        self.enabled = enabled
        self.panel_ids = set(panel_ids) if panel_ids else None
        self.forwarded = 0
        self.forward_errors = 0
        self.output = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) if forward else None
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind((bind, 60222))
        self.socket.settimeout(0.5)
        self.stopped = threading.Event()
        self.lock = threading.Lock()
        self.accepted = self.invalid = self.other_source = 0
        self.last = None
        self.panels = {}
        self.thread = threading.Thread(target=self.run, daemon=True)

    def accept(self, data, peer):
        with self.lock:
            if peer[0] != self.source:
                self.other_source += 1
                return False
            try:
                panels = decode(data)
            except ValueError:
                self.invalid += 1
                return False
            if self.panel_ids is not None and not set(panels).issubset(self.panel_ids):
                self.invalid += 1
                return False
            self.accepted += 1
            self.last = time.monotonic()
            self.panels = panels
            if self.output and self.enabled():
                try:
                    self.output.sendto(data, ('127.0.0.1', 60223))
                    self.forwarded += 1
                except OSError:
                    self.forward_errors += 1
            return True

    def run(self):
        while not self.stopped.is_set():
            try:
                data, peer = self.socket.recvfrom(65535)
            except socket.timeout:
                continue
            self.accept(data, peer)

    def status(self):
        with self.lock:
            return {'mode': 'direct' if self.forward else 'direct-receiver-experiment', 'port': 60222,
                    'accepted': self.accepted, 'invalid': self.invalid,
                    'forwarded': self.forwarded,
                    'forwardErrors': self.forward_errors,
                    'otherSource': self.other_source,
                    'lastFrameAge': None if self.last is None else round(time.monotonic()-self.last, 2),
                    'panels': dict(self.panels), 'hueForwarding': self.forward}

    def start(self):
        self.thread.start()

    def stop(self):
        self.stopped.set()
        self.thread.join(timeout=2)
        self.socket.close()
        if self.output:
            self.output.close()
