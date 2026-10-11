"""Nanoleaf discovery only: observed NOTIFY fields and standard M-SEARCH replies."""
import logging
import socket
import threading
import time

from nanoleaf_probe import DEVICE_ID, NAME

LOG = logging.getLogger("nanoleaf-ssdp")
GROUP = "239.255.255.250"
PORT = 1900
NATIVE_TYPE = "nanoleaf:nl42"
LEGACY_TYPE = "nanoleaf_aurora:light"


def search_type(data):
    if len(data) > 4096:
        return None
    lines = data.decode("ascii", errors="replace").split("\r\n")
    if not lines or lines[0].strip().upper() != "M-SEARCH * HTTP/1.1":
        return None
    headers = {}
    for line in lines[1:]:
        if ":" in line:
            key, value = line.split(":", 1)
            headers[key.strip().lower()] = value.strip()
    if headers.get("man", "").lower() != '"ssdp:discover"':
        return None
    target = headers.get("st", "").lower()
    return target if target in ("ssdp:all", NATIVE_TYPE, LEGACY_TYPE) else None


def notification(address, api_port, identity, alive=True):
    fields = ["NOTIFY * HTTP/1.1", f"Host: {GROUP}:{PORT}",
              f"NT: {NATIVE_TYPE}", "NTS: ssdp:alive" if alive else "NTS: ssdp:byebye",
              f"USN: uuid:{identity}"]
    if alive:
        fields.extend([f"Location: http://{address}:{api_port}",
                       "Cache-Control: max-age = 60", f"nl-deviceid: {DEVICE_ID}",
                       f"nl-devicename: {NAME}"])
    return ("\r\n".join(fields) + "\r\n\r\n").encode("ascii")


def search_response(address, api_port, identity, target):
    target = NATIVE_TYPE if target == "ssdp:all" else target
    if target not in (NATIVE_TYPE, LEGACY_TYPE):
        raise ValueError("unsupported discovery target")
    fields = ["HTTP/1.1 200 OK", "Cache-Control: max-age=60", "EXT:",
              f"Location: http://{address}:{api_port}",
              "Server: Linux/1.0 UPnP/1.1 NanoleafProbe/0.2", f"ST: {target}",
              f"USN: uuid:{identity}::{target}", f"nl-deviceid: {DEVICE_ID}",
              f"nl-devicename: {NAME}"]
    return ("\r\n".join(fields) + "\r\n\r\n").encode("ascii")


class SSDPRuntime:
    def __init__(self, address, api_port, identity):
        self.address, self.api_port, self.identity = address, api_port, identity
        self.socket = None
        self.error = None
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._run, name="ssdp-probe", daemon=True)

    def start(self):
        listener = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.socket = listener
        try:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind(("", PORT))
            local = socket.inet_aton(self.address)
            listener.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP,
                                socket.inet_aton(GROUP) + local)
            listener.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, local)
            listener.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 1)
            listener.settimeout(0.5)
            self.thread.start()
        except Exception:
            listener.close()
            self.socket = None
            raise

    def _run(self):
        next_advertisement = 0
        recent = {}
        try:
            while not self.stop_event.is_set():
                now = time.monotonic()
                if now >= next_advertisement:
                    self.socket.sendto(notification(self.address, self.api_port, self.identity),
                                       (GROUP, PORT))
                    next_advertisement = now + 30
                try:
                    data, peer = self.socket.recvfrom(4097)
                except socket.timeout:
                    continue
                target = search_type(data)
                if target is None:
                    continue
                now = time.monotonic()
                key = (peer[0], target)
                if now - recent.get(key, float("-inf")) < 1:
                    continue
                recent = {k: t for k, t in recent.items() if now - t < 10}
                if len(recent) >= 256:
                    continue
                recent[key] = now
                self.socket.sendto(search_response(self.address, self.api_port,
                                                  self.identity, target), peer)
                LOG.info("SSDP discovery response client=%s target=%s", peer[0], target)
        except Exception as error:
            self.error = error
            LOG.exception("SSDP runtime failed")
        finally:
            try:
                self.socket.sendto(notification(self.address, self.api_port,
                                                self.identity, alive=False), (GROUP, PORT))
            except OSError:
                pass

    def stop(self):
        self.stop_event.set()
        if self.thread.is_alive():
            self.thread.join(timeout=2)
        if self.socket:
            self.socket.close()

    def status(self):
        return {"running": self.thread.is_alive() and not self.error, "port": PORT}
