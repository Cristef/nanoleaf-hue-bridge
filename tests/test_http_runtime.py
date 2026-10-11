"""Verify both advertised IP families reach the same authenticated API."""
from http.client import HTTPConnection
import json
from pathlib import Path
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer

from nanoleaf_probe import Device, Handler, IPv6HTTPServer


class HTTPRuntimeTests(unittest.TestCase):
    def test_ipv4_and_ipv6_share_auth_and_public_endpoint(self):
        with tempfile.TemporaryDirectory(prefix="probe-test-", dir=Path(__file__).parent) as folder:
            device = Device(Path(folder) / "state.json")
            ipv4 = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
            servers = [ipv4]
            try:
                ipv6 = IPv6HTTPServer(("::1", ipv4.server_port), Handler)
                servers.append(ipv6)
                threads = []
                for listener in servers:
                    listener.device = device
                    thread = threading.Thread(target=listener.serve_forever, daemon=True)
                    thread.start()
                    threads.append(thread)
                device.open_pairing()
                token = device.handle("POST", "/api/v1/new")[1]["auth_token"]
                for address in ("127.0.0.1", "::1"):
                    for path, status in (("/api/v1/qkihnokomhartlnp", 200),
                                         ("/api/v1/unknown-token/state", 401),
                                         (f"/api/v1/{token}/state", 200)):
                        connection = HTTPConnection(address, ipv4.server_port, timeout=3)
                        try:
                            connection.request("GET", path)
                            response = connection.getresponse()
                            self.assertEqual(response.status, status)
                            self.assertIsInstance(json.loads(response.read()), dict)
                        finally:
                            connection.close()
            finally:
                for listener in servers:
                    if hasattr(listener, "device"):
                        listener.shutdown()
                    listener.server_close()
                for thread in locals().get("threads", []):
                    thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
