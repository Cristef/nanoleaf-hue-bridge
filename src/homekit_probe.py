"""HomeKit pairing experiment, backed by HAP-python 5.0.0."""
import asyncio
import copy
import json
import logging
import os
from pathlib import Path
import threading

from pyhap.accessory import Accessory
from pyhap.accessory_driver import AccessoryDriver, AccessoryMDNSServiceInfo
from pyhap.const import CATEGORY_LIGHTBULB
from pyhap import util

from nanoleaf_probe import DEVICE_ID, FIRMWARE, NAME

LOG = logging.getLogger("nanoleaf-homekit")
CHAR_FIELDS = {"On": "on", "Brightness": "brightness", "Hue": "hue", "Saturation": "sat"}


def load_setup(folder):
    """Keep setup code and setup ID stable; HAP-python persists keys separately."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "homekit-setup.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    setup = {"pincode": util.generate_pincode().decode("ascii"),
             "setup_id": util.generate_setup_id()}
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(setup, stream)
    return setup


class ShapesLight(Accessory):
    category = CATEGORY_LIGHTBULB

    def __init__(self, driver, device):
        super().__init__(driver, NAME, aid=1)
        self.device = device
        self.set_info_service(manufacturer="Nanoleaf", model="NL42",
                              serial_number=DEVICE_ID.replace(":", ""), firmware_revision=FIRMWARE)
        self.get_service("AccessoryInformation").configure_char(
            "Identify", setter_callback=self.identify_virtual)
        light = self.add_preload_service("Lightbulb", chars=["Brightness", "Hue", "Saturation"])
        self.set_primary_service(light)
        self.chars = {}
        with device.lock:
            for char_name, field in CHAR_FIELDS.items():
                self.chars[field] = light.configure_char(
                    char_name, value=device.info["state"][field]["value"])
        light.setter_callback = self.set_light

    def identify_virtual(self, value):
        if value:
            LOG.info("HomeKit Identify received; opening virtual OpenAPI window")
            self.device.open_pairing()

    def set_light(self, values):
        body = {}
        for char_name, value in values.items():
            if char_name in CHAR_FIELDS:
                body[CHAR_FIELDS[char_name]] = {
                    "value": value if char_name == "On" else int(round(value))}
        if body:
            code, _ = self.device.update_state(body)
            if code != 204:
                raise ValueError("HomeKit state update outside supported range")
            LOG.info("HomeKit state updated: %s", ", ".join(body))

    @Accessory.run_at_interval(1)
    def run(self):
        with self.device.lock:
            state = copy.deepcopy(self.device.info["state"])
        for field, char in self.chars.items():
            char.set_value(state[field]["value"])

    def setup_message(self):
        # Pairing code is written only to the private setup file, never the journal.
        LOG.info("HomeKit ready for pairing; read homekit-setup.json locally for the code")


class ShapesMDNSInfo(AccessoryMDNSServiceInfo):
    def _get_advert_data(self):
        data = super()._get_advert_data()
        data["md"] = "NL42"
        return data


class ShapesDriver(AccessoryDriver):
    def get_accessories(self, include_value=True):
        LOG.info("HomeKit accessory database requested")
        return super().get_accessories(include_value=include_value)

    def get_characteristics(self, char_ids):
        LOG.info("HomeKit characteristic read: %s", ", ".join(char_ids))
        return super().get_characteristics(char_ids)

    def set_characteristics(self, chars_query, client_addr):
        # Never log values: vendor characteristics can carry pairing credentials.
        summary = [{"aid": item.get("aid"), "iid": item.get("iid"),
                    "fields": sorted(item)}
                   for item in chars_query.get("characteristics", [])]
        LOG.info("HomeKit characteristic write client=%s: %s", client_addr[0], summary)
        return super().set_characteristics(chars_query, client_addr)

    async def async_start(self):
        await super().async_start()
        # HAP-python advertises the display name as md; use observed Shapes model.
        await self.advertiser.async_unregister_service(self.mdns_service_info)
        self.mdns_service_info = ShapesMDNSInfo(self.accessory, self.state, self.zeroconf_server)
        await self.advertiser.async_register_service(self.mdns_service_info, cooperating_responders=True)

    @util.callback
    def async_update_advertisement(self):
        self.mdns_service_info = ShapesMDNSInfo(self.accessory, self.state, self.zeroconf_server)
        util.async_create_background_task(self.advertiser.async_update_service(self.mdns_service_info))


class HomeKitRuntime:
    def __init__(self, device, address, port, folder):
        self.device, self.address, self.port = device, address, port
        self.folder = Path(folder)
        self.driver = None
        self.error = None
        self.ready = threading.Event()
        self.thread = threading.Thread(target=self._run, name="homekit-probe", daemon=True)

    def start(self):
        self.thread.start()
        if not self.ready.wait(30):
            raise RuntimeError("HomeKit startup timed out")
        if self.error:
            raise RuntimeError("HomeKit startup failed") from self.error

    def _run(self):
        started = False
        try:
            setup = load_setup(self.folder)
            self.driver = ShapesDriver(
                address=self.address, listen_address=self.address, advertised_address=self.address,
                interface_choice=[self.address], port=self.port, mac=DEVICE_ID,
                pincode=setup["pincode"].encode("ascii"),
                persist_file=str(self.folder / "homekit.state"))
            asyncio.set_event_loop(self.driver.loop)
            self.driver.state.setup_id = setup["setup_id"]
            self.driver.add_accessory(ShapesLight(self.driver, self.device))
            self.driver.loop.run_until_complete(self.driver.async_start())
            started = True
            self.ready.set()
            LOG.info("HomeKit listening on %s:%s paired=%s", self.address, self.port,
                     self.driver.state.paired)
            self.driver.loop.run_forever()
        except Exception as error:
            self.error = error
            LOG.exception("HomeKit runtime failed")
        finally:
            self.ready.set()
            if self.driver:
                if started and not self.driver.stop_event.is_set():
                    self.driver.loop.run_until_complete(self.driver.async_stop())
                elif not started and self.driver.advertiser:
                    self.driver.loop.run_until_complete(self.driver.advertiser.async_close())
                    if self.driver.http_server.server:
                        self.driver.http_server.async_stop()
                # Zeroconf's multicast broadcast tasks can outlive unregister/close.
                pending = asyncio.all_tasks(self.driver.loop)
                for task in pending:
                    task.cancel()
                if pending:
                    self.driver.loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                if self.driver.executor:
                    self.driver.executor.shutdown(wait=False)
                self.driver.loop.close()

    def stop(self):
        if self.driver and self.driver.loop.is_running():
            self.driver.stop()
        self.thread.join(timeout=10)

    def status(self):
        return {"running": self.ready.is_set() and self.thread.is_alive() and not self.error,
                "paired": bool(self.driver and self.driver.state.paired), "port": self.port}
