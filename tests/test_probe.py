import json
import tempfile
import unittest
from pathlib import Path
from nanoleaf_probe import Device, safe_path


class ProbeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="probe-test-", dir=Path(__file__).resolve().parent)
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "state.json"
        self.device = Device(self.path)

    def pair(self):
        self.device.open_pairing()
        code, result = self.device.handle("POST", "/api/v1/new")
        self.assertEqual(code, 200)
        return result["auth_token"]

    def test_pairing_window_auth_persistence_and_revoke(self):
        self.assertEqual(self.device.handle("POST", "/api/v1/new")[0], 403)
        self.assertEqual(self.device.handle("GET", "/api/v1/wrong")[0], 401)
        token = self.pair()
        reloaded = Device(self.path)
        self.assertEqual(reloaded.handle("GET", f"/api/v1/{token}")[1]["model"], "NL42")
        self.assertEqual(reloaded.handle("DELETE", f"/api/v1/{token}")[0], 204)
        self.assertEqual(Device(self.path).handle("GET", f"/api/v1/{token}")[0], 401)

    def test_state_validation_is_atomic(self):
        token = self.pair()
        path = f"/api/v1/{token}/state"
        status, _ = self.device.handle("PUT", path, {"brightness": {"value": 20}, "hue": {"value": 999}})
        self.assertEqual(status, 400)
        self.assertEqual(self.device.handle("GET", path)[1]["brightness"]["value"], 50)
        self.assertEqual(self.device.handle("PUT", path, {"brightness": {"value": True}})[0], 400)
        self.assertEqual(self.device.handle("PUT", path, {"on": {"value": False}, "ct": {"value": 5000}})[0], 204)
        self.assertEqual(Device(self.path).handle("GET", path)[1]["colorMode"], "ct")

    def test_unknown_sync_requests_fail_and_paths_redact_tokens(self):
        token = self.pair()
        self.assertEqual(self.device.handle("PUT", f"/api/v1/{token}/effects", {"write": {"command": "display"}})[0], 501)
        self.assertEqual(self.device.handle("GET", f"/api/v1/{token}/unknown")[0], 404)
        self.assertNotIn(token, safe_path(f"/api/v1/{token}/effects?token=secret"))
        self.assertNotIn("secret", safe_path(f"/api/v1/{token}/effects?token=secret"))

    def test_observed_public_probe_does_not_bypass_api_auth(self):
        path = "/api/v1/qkihnokomhartlnp"
        self.assertEqual(self.device.handle("GET", path),
                         (200, {"qkihnokomhartlnp": False,
                                "id": "d41d8cd98f00b204e9800998ecf8427e"}))
        self.assertEqual(safe_path(path), path)
        for method in ("POST", "PUT", "DELETE"):
            self.assertEqual(self.device.handle(method, path)[0], 401)
        self.assertEqual(self.device.handle("GET", path + "/state")[0], 401)
        self.assertEqual(self.device.handle("GET", "/api/v1/discovery")[0], 401)
        self.assertEqual(self.device.handle("GET", "/api/v1/unknown-token/state")[0], 401)


if __name__ == "__main__":
    unittest.main()
