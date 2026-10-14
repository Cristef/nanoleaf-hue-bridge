#!/usr/bin/env python3
"""Experimental virtual Shapes API and direct Sync+ receiver."""
import argparse
import copy
import ipaddress
import json
import logging
import os
from pathlib import Path
import secrets
import signal
import socket
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
from uuid import uuid4

LOG = logging.getLogger("nanoleaf-probe")
from config import CONFIG
NAME = CONFIG["name"]
DEVICE_ID = CONFIG["identity"]
FIRMWARE = "12.4.1"  # Advertised compatibility profile, not real Nanoleaf firmware.
PUBLIC_PROBE = "qkihnokomhartlnp"
# Observed from the user's Shapes NL42/12.4.1 with this flag false.
# This is a protocol sentinel, not the virtual accessory's device identity.
PUBLIC_PROBE_EMPTY_ID = "d41d8cd98f00b204e9800998ecf8427e"


def device_info():
    return {
        "name": NAME, "serialNo": DEVICE_ID.replace(":", ""), "manufacturer": "Nanoleaf",
        "model": "NL42", "firmwareVersion": FIRMWARE, "hardwareVersion": "1.0",
        "state": {
            "on": {"value": True},
            "brightness": {"value": 50, "min": 0, "max": 100},
            "hue": {"value": 0, "min": 0, "max": 360},
            "sat": {"value": 100, "min": 0, "max": 100},
            "ct": {"value": 4000, "min": 1200, "max": 6500}, "colorMode": "hs",
        },
        "effects": {"effectsList": [], "select": "*Solid*"},
        "panelLayout": {
            "globalOrientation": {"value": 0, "min": 0, "max": 360},
            "layout": {"numPanels": 1, "sideLength": 67, "positionData": [
                {"panelId": 1, "x": 0, "y": 0, "o": 0, "shapeType": 7}
            ]},
        },
        "rhythm": {"rhythmConnected": False, "rhythmActive": False},
    }


class Device:
    def __init__(self, state_file):
        self.state_file = Path(state_file)
        self.lock = threading.RLock()
        self.tokens = set()
        self.bind_address = None
        self.direct_receiver = None
        self.info = device_info()
        self.pair_until = 0
        self.homekit = None
        self.ssdp = None
        self.ssdp_uuid = str(uuid4())
        if self.state_file.exists():
            stored = json.loads(self.state_file.read_text(encoding="utf-8"))
            self.tokens = set(stored["tokens"])
            self.info.update(stored.get("info", {}))
            self.ssdp_uuid = stored.get("ssdp_uuid", self.ssdp_uuid)

        # Private internal API authorization, never a portal login credential.
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        control_path = self.state_file.parent / 'web-control-auth.json'
        if control_path.exists():
            control_token = json.loads(control_path.read_text())['token']
        else:
            control_token = secrets.token_urlsafe(32)
            fd = os.open(control_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, 'w') as stream:
                json.dump({'token': control_token}, stream)
        # Only the virtual service and the portal's dedicated group can read this key.
        control_path.chmod(0o640)
        self.tokens.add(control_token)
        self.save()

        self.control_token = control_token

    def save(self):
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.state_file.with_suffix(".tmp")
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump({"tokens": sorted(self.tokens), "info": self.info,
                       "ssdp_uuid": self.ssdp_uuid}, stream)
        os.replace(temporary, self.state_file)

    def open_pairing(self, seconds=120):
        with self.lock:
            self.pair_until = time.monotonic() + seconds
        LOG.info("API pairing window open for %ss (virtual device only)", seconds)

    def handle(self, method, path, body=None):
        with self.lock:
            return self._handle(method, path, body)

    def _handle(self, method, path, body):
        parts = [part for part in urlsplit(path).path.split("/") if part]
        if parts == ["health"] and method == "GET":
            return 200, {"status": "ok", "name": NAME, "model": "NL42",
                         "on": self.info["state"]["on"]["value"],
                         "experimental": True, "pairing": {"open": time.monotonic() < self.pair_until, "secondsRemaining": max(0, int(self.pair_until-time.monotonic())), "apiPaired": bool(self.tokens - {self.control_token})}, "syncPlus": self.direct_receiver.status() if self.direct_receiver else "not implemented",
                         "homeKit": self.homekit.status() if self.homekit else "disabled",
                         "ssdp": self.ssdp.status() if self.ssdp else "disabled"}
        if parts[:2] != ["api", "v1"] or len(parts) < 3:
            return 404, {"error": "unsupported endpoint"}
        if parts == ["api", "v1", PUBLIC_PROBE] and method == "GET":
            return 200, {PUBLIC_PROBE: False, "id": PUBLIC_PROBE_EMPTY_ID}
        if parts == ["api", "v1", "new"] and method == "POST":
            if time.monotonic() >= self.pair_until:
                return 403, {"error": "API pairing window closed"}
            token = secrets.token_hex(16)
            self.tokens.add(token)
            self.save()
            LOG.info("Issued API token (value omitted)")
            return 200, {"auth_token": token}
        token = parts[2]
        if token not in self.tokens:
            return 401, {"error": "invalid token"}
        tail = parts[3:]
        if method == "POST" and tail == ["pairing"]:
            if token != self.control_token:
                return 403, {"error": "Internal portal authorization required"}
            self.open_pairing(120)
            return 200, {"seconds": 120, "method": "desktop-button"}
        if method == "DELETE" and not tail:
            self.tokens.remove(token)
            self.save()
            return 204, None
        if method == "GET":
            if tail == ["firmwareUpgrade"]:
                return 200, {"firmwareAvailability": False, "newFirmwareVersion": None}
            result = self.info
            for part in tail:
                if not isinstance(result, dict) or part not in result:
                    return 404, {"error": "unsupported endpoint"}
                result = result[part]
            # Scalar /value endpoints return scalars; containers return objects.
            return 200, copy.deepcopy(result)
        if method == "PUT" and tail == ["state"]:
            return self.update_state(body)
        if method == "PUT" and tail == ["effects"]:
            write = body.get("write") if isinstance(body, dict) else None
            command = write.get("command") if isinstance(write, dict) else None
            if isinstance(command, str):
                label = command if command in {
                    "getDeviceId", "getLocalIpAddress", "getDeviceAuthToken",
                    "display", "request", "requestAll", "requestPlugins",
                    "getOrchestratorScreenConfig",
                    "getTouchKillSwitch", "requestTouchConfig", "requestBrightnessSensorConfig",
                } else "unsupported"
                LOG.info("Receiver command: %s", label)
            if command == "getDeviceId":
                return 200, {"deviceId": DEVICE_ID}
            if command == "getLocalIpAddress" and self.bind_address:
                return 200, {"localIpAddress": self.bind_address}
            if command == "getDeviceAuthToken":
                # Return only the already authenticated caller's own token.
                return 200, {"authToken": token}
            if command == "requestAll":
                # No synthetic vendor animations: this receiver has no stored scenes.
                return 200, {"animations": []}
            if command == "requestPlugins":
                return 200, {"plugins": []}
            if command == "getTouchKillSwitch":
                return 200, {"touchKillSwitchOn": True}
            if command == "requestTouchConfig":
                return 200, {"touchConfig": {
                    "supportedFeatures": {"systemGestures": [], "systemActions": []},
                    "defaultSystemConfig": {"gestureActions": []},
                    "userSystemConfig": {"enabled": False, "gestureActions": [], "subscribers": []},
                    "userPanelConfigs": [],
                }}
            if command == "requestBrightnessSensorConfig":
                return 200, {"brightnessSensorConfig": {
                    "enabled": False, "brightnessSensorMode": 0,
                    "userMaxBrightness": 100, "userMinBrightness": 0,
                    "isCalibrated": False, "isCalibrating": False,
                }}
            if (command == "display" and write.get("animType") == "extControl"
                    and write.get("extControlVersion") == "v2" and self.direct_receiver):
                self.info["effects"]["select"] = "*ExtControl*"
                return 200, {"streamControlIpAddr": self.bind_address,
                             "streamControlPort": 60222, "streamControlProtocol": "udp"}
        # Unknown operations intentionally fail, so missing protocol is observable.
        return 501, {"error": "operation not implemented in discovery probe"}

    def update_state(self, body):
        """Shared, atomic state update for REST and authenticated HomeKit commands."""
        with self.lock:
            if not isinstance(body, dict) or not body:
                return 400, {"error": "expected state object"}
            updated = copy.deepcopy(self.info["state"])
            for key, item in body.items():
                if key not in ("on", "brightness", "hue", "sat", "ct"):
                    return 400, {"error": "unsupported state field"}
                if not isinstance(item, dict) or "value" not in item:
                    return 400, {"error": "expected value"}
                value = item["value"]
                current = updated[key]
                if key == "on":
                    if not isinstance(value, bool):
                        return 400, {"error": "on must be boolean"}
                elif type(value) is not int or not current["min"] <= value <= current["max"]:
                    return 400, {"error": "value outside range"}
                current["value"] = value
                if key in ("hue", "sat", "ct"):
                    updated["colorMode"] = "ct" if key == "ct" else "hs"
            self.info["state"] = updated
            self.save()
            return 204, None


def safe_path(path):
    parts = urlsplit(path).path.split("/")
    if len(parts) > 3 and parts[1:3] == ["api", "v1"] and parts[3] not in ("new", PUBLIC_PROBE):
        parts[3] = "<token>"
    return "/".join(parts)


class Handler(BaseHTTPRequestHandler):
    server_version = "NanoleafProbe/0.1"

    def log_message(self, fmt, *args):
        pass  # Default HTTP logger would expose tokens in URLs.

    def request(self):
        self.connection.settimeout(10)
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 0 or length > 65536:
                self.send_error(413)
                return
            body = json.loads(self.rfile.read(length)) if length else None
        except (ValueError, UnicodeError):
            self.send_error(400)
            return
        try:
            code, result = self.server.device.handle(self.command, self.path, body)
        except Exception:
            LOG.exception("Internal error handling %s %s", self.command, safe_path(self.path))
            code, result = 500, {"error": "internal error"}
        if urlsplit(self.path).path != "/health":
            LOG.info("HTTP client=%s %s %s -> %s", self.client_address[0],
                     self.command, safe_path(self.path), code)
        encoded = json.dumps(result).encode("utf-8") if result is not None else b""
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    do_GET = request
    do_POST = request
    do_PUT = request
    do_DELETE = request


class IPv6HTTPServer(ThreadingHTTPServer):
    address_family = socket.AF_INET6

    def server_bind(self):
        # Keep the separate IPv4 listener; never depend on platform dual-stack defaults.
        self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
        super().server_bind()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bind", default=CONFIG["ip"])
    parser.add_argument("--port", type=int, default=16021)
    parser.add_argument("--state", default="/var/lib/nanoleaf-hue-virtual/state.json")
    parser.add_argument("--homekit", action="store_true")
    parser.add_argument("--homekit-port", type=int, default=6517)
    parser.add_argument("--bind-ipv6", help="Also serve the IPv6 address advertised by Avahi; use :: in an LXC")
    parser.add_argument("--ssdp", action="store_true")
    parser.add_argument("--direct-sync-source", default=CONFIG["source_ip"], help="Enable experimental UDP receiver for this IPv4 source only")
    parser.add_argument("--direct-sync-forward", action="store_true", default=True, help="Forward validated direct frames to the local Hue consumer")
    parser.add_argument("--virtual-layout", help="JSON virtual layout, applied without resetting device identity")
    args = parser.parse_args()
    ipaddress.IPv4Address(args.bind)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    device = Device(args.state)
    device.bind_address = args.bind
    if not args.virtual_layout:
        from virtual_layout import default_layout
        device.info['panelLayout']['layout'] = default_layout()
        device.save()
    if args.virtual_layout:
        from virtual_layout import validate_layout
        layout = validate_layout(json.loads(Path(args.virtual_layout).read_text()))
        device.info['panelLayout']['layout'] = layout
        device.save()
    if args.direct_sync_forward and not args.direct_sync_source:
        raise ValueError('Direct forwarding requires a source address')
    if args.direct_sync_source:
        ipaddress.IPv4Address(args.direct_sync_source)
        from direct_sync_receiver import DirectReceiver
        device.direct_receiver = DirectReceiver(args.bind, args.direct_sync_source,
            forward=args.direct_sync_forward,
            enabled=lambda: device.info['state']['on']['value'] is True,
            panel_ids=[p['panelId'] for p in device.info['panelLayout']['layout']['positionData']])
        device.direct_receiver.start()
    server = ThreadingHTTPServer((args.bind, args.port), Handler)
    server.device = device
    servers = [server]
    if args.bind_ipv6:
        ipaddress.IPv6Address(args.bind_ipv6)
        ipv6_server = IPv6HTTPServer((args.bind_ipv6, args.port), Handler)
        ipv6_server.device = device
        servers.append(ipv6_server)
    stop = threading.Event()

    def shutdown(*_):
        stop.set()
        for listener in servers:
            threading.Thread(target=listener.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGUSR1, lambda *_: device.open_pairing())
    publisher = None
    for listener in servers:
        threading.Thread(target=listener.serve_forever, daemon=True).start()
    try:
        if args.ssdp:
            from ssdp_probe import SSDPRuntime
            with device.lock:
                device.save()  # Preserve the independent discovery UUID across restarts.
            device.ssdp = SSDPRuntime(args.bind, args.port, device.ssdp_uuid)
            device.ssdp.start()
        publisher = subprocess.Popen([
            "avahi-publish-service", "--no-fail", NAME, "_nanoleafapi._tcp", str(args.port),
            f"id={DEVICE_ID}", "md=NL42", f"srcvers={FIRMWARE}",
        ])
        if args.homekit:
            from homekit_probe import HomeKitRuntime
            device.homekit = HomeKitRuntime(device, args.bind, args.homekit_port,
                                           Path(args.state).parent)
            device.homekit.start()
        LOG.info("Experimental API listening on %s:%s; direct Sync+ receiver %s", args.bind, args.port,
                 "enabled" if device.direct_receiver else "disabled")
        if args.bind_ipv6:
            LOG.info("Experimental API also listening on [%s]:%s", args.bind_ipv6, args.port)
        while not stop.wait(1):
            if publisher.poll() is not None:
                raise RuntimeError("mDNS publisher exited; inspect Avahi service")
            if device.homekit and device.homekit.error:
                raise RuntimeError("HomeKit thread failed") from device.homekit.error
            if device.ssdp and device.ssdp.error:
                raise RuntimeError("SSDP thread failed") from device.ssdp.error
            if device.direct_receiver and not device.direct_receiver.thread.is_alive():
                raise RuntimeError("Direct Sync+ receiver stopped unexpectedly")
    finally:
        if device.direct_receiver:
            device.direct_receiver.stop()
        if device.ssdp:
            device.ssdp.stop()
        if device.homekit:
            device.homekit.stop()
        if publisher is not None and publisher.poll() is None:
            publisher.terminate()
            try:
                publisher.wait(timeout=5)
            except subprocess.TimeoutExpired:
                publisher.kill()
                publisher.wait()
        for listener in servers:
            listener.shutdown()
            listener.server_close()


if __name__ == "__main__":
    main()
