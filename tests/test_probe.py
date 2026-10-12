import json
import tempfile
import unittest
from pathlib import Path
from nanoleaf_probe import Device, safe_path, DEVICE_ID


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

    def test_receiver_metadata_requires_valid_auth_and_uses_caller_token(self):
        token = self.pair()
        self.device.bind_address = "192.0.2.10"
        path = f"/api/v1/{token}/effects"
        for command, field, expected in (
            ("getDeviceId", "deviceId", DEVICE_ID),
            ("getLocalIpAddress", "localIpAddress", "192.0.2.10"),
            ("getDeviceAuthToken", "authToken", token),
        ):
            body = {"write": {"command": command}}
            self.assertEqual(self.device.handle("PUT", path, body),
                             (200, {field: expected}))
            self.assertEqual(self.device.handle("PUT", "/api/v1/invalid/effects", body)[0], 401)
        self.assertEqual(self.device.handle("PUT", path, {"write": None})[0], 501)

    def test_desktop_scene_inventory_is_authenticated_and_empty(self):
        token = self.pair()
        body = {"write": {"command": "requestAll"}}
        self.assertEqual(self.device.handle("PUT", f"/api/v1/{token}/effects", body),
                         (200, {"animations": []}))
        self.assertEqual(self.device.handle("PUT", "/api/v1/invalid/effects", body)[0], 401)

    def test_desktop_plugin_inventory_is_authenticated_and_empty(self):
        token = self.pair()
        body = {"write": {"command": "requestPlugins"}}
        self.assertEqual(self.device.handle("PUT", f"/api/v1/{token}/effects", body),
                         (200, {"plugins": []}))
        self.assertEqual(self.device.handle("PUT", "/api/v1/invalid/effects", body)[0], 401)

    def test_complete_required_desktop_initialization_reports_virtual_capabilities(self):
        token = self.pair()
        root = f"/api/v1/{token}"
        self.assertEqual(self.device.handle("GET", root)[1]["firmwareVersion"], "12.4.1")
        self.assertEqual(self.device.handle("GET", root + "/firmwareUpgrade"),
                         (200, {"firmwareAvailability": False, "newFirmwareVersion": None}))
        for command, field in (
            ("requestAll", "animations"), ("requestPlugins", "plugins"),
            ("getTouchKillSwitch", "touchKillSwitchOn"),
            ("requestTouchConfig", "touchConfig"),
            ("requestBrightnessSensorConfig", "brightnessSensorConfig"),
        ):
            body = {"write": {"command": command}}
            code, data = self.device.handle("PUT", root + "/effects", body)
            self.assertEqual(code, 200)
            self.assertIn(field, data)
            self.assertEqual(self.device.handle("PUT", "/api/v1/invalid/effects", body)[0], 401)
        self.assertEqual(self.device.handle("GET", "/api/v1/invalid/firmwareUpgrade")[0], 401)
        self.assertEqual(self.device.handle("PUT", root + "/firmwareUpgrade",
                                           {"command": "triggerFirmwareUpgrade"})[0], 501)

    def test_external_control_ack_requires_running_direct_receiver(self):
        token = self.pair()
        body = {"write": {"command": "display", "animType": "extControl", "extControlVersion": "v2"}}
        path = f"/api/v1/{token}/effects"
        self.assertEqual(self.device.handle("PUT", path, body)[0], 501)
        self.device.bind_address = "192.0.2.10"
        self.device.direct_receiver = object()
        self.assertEqual(self.device.handle("PUT", path, body),
                         (200, {"streamControlIpAddr": "192.0.2.10",
                                "streamControlPort": 60222, "streamControlProtocol": "udp"}))
        body["write"]["extControlVersion"] = "v1"
        self.assertEqual(self.device.handle("PUT", path, body)[0], 501)

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
