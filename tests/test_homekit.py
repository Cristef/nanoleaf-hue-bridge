import tempfile
import unittest
from pathlib import Path
from uuid import uuid4
from homekit_probe import ShapesDriver, ShapesLight, ShapesMDNSInfo, load_setup
from nanoleaf_probe import Device, DEVICE_ID


class HomeKitTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="hap-test-", dir=Path(__file__).resolve().parent)
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.device = Device(self.folder / "state.json")
        self.driver = self.make_driver()

    def make_driver(self):
        setup = load_setup(self.folder)
        driver = ShapesDriver(address="127.0.0.1", port=6517, mac=DEVICE_ID,
                              pincode=setup["pincode"].encode(),
                              persist_file=str(self.folder / "hap.state"))
        driver.state.setup_id = setup["setup_id"]
        driver.add_accessory(ShapesLight(driver, self.device))
        self.addCleanup(driver.loop.close)
        self.addCleanup(driver.executor.shutdown)
        return driver

    def test_metadata_unpaired_and_paired_advertisement(self):
        accessory = self.driver.accessory
        info = accessory.get_service("AccessoryInformation")
        self.assertEqual(info.get_characteristic("Model").value, "NL42")
        self.assertEqual(info.get_characteristic("Manufacturer").value, "Nanoleaf")
        adv = ShapesMDNSInfo(accessory, self.driver.state).properties
        self.assertEqual(adv[b"id"].decode(), DEVICE_ID)
        self.assertEqual(adv[b"sf"], b"1")
        self.assertEqual(adv[b"md"], b"NL42")
        self.assertEqual(adv[b"ci"], b"5")

    def test_homekit_commands_and_rest_share_persistent_state(self):
        self.driver.accessory.set_light({"On": False, "Brightness": 23, "Hue": 42.0})
        self.assertFalse(self.device.info["state"]["on"]["value"])
        self.assertEqual(Device(self.folder / "state.json").info["state"]["brightness"]["value"], 23)
        self.device.open_pairing()
        token = self.device.handle("POST", "/api/v1/new")[1]["auth_token"]
        self.assertEqual(self.device.handle("GET", f"/api/v1/{token}/state/hue/value")[1], 42)
        self.device.handle("PUT", f"/api/v1/{token}/state", {"brightness": {"value": 71}})
        # Decorated run is asynchronous; direct device state is source of truth.
        self.assertEqual(self.device.info["state"]["brightness"]["value"], 71)

    def test_homekit_pair_keys_and_setup_identity_survive_restart(self):
        client = uuid4()
        self.driver.state.add_paired_client(str(client).encode(), b"x" * 32, b"\x01")
        self.driver.persist()
        restarted = self.make_driver()
        self.assertTrue(restarted.state.paired)
        self.assertEqual(restarted.state.mac, self.driver.state.mac)
        self.assertEqual(restarted.state.pincode, self.driver.state.pincode)
        self.assertEqual(restarted.state.setup_id, self.driver.state.setup_id)
        adv = ShapesMDNSInfo(restarted.accessory, restarted.state).properties
        self.assertEqual(adv[b"sf"], b"0")
        self.assertEqual(restarted.state.public_key.public_bytes_raw(),
                         self.driver.state.public_key.public_bytes_raw())


if __name__ == "__main__":
    unittest.main()
