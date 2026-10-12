import copy
import json
from pathlib import Path
import struct
import tempfile
import time
import unittest
from unittest.mock import patch
from config import CONFIG, validate
from direct_stats import snapshot
from nanoleaf_probe import Device
from virtual_layout import default_layout, validate_layout
from hue_sync import channel_colors
import daily_sync


class DirectReleaseTests(unittest.TestCase):
    def test_fresh_direct_config_does_not_require_physical_shapes_or_macs(self):
        data=copy.deepcopy(CONFIG)
        data['mode']='direct'
        for key in ('source_mac','target_mac','target_ip'): data.pop(key,None)
        self.assertEqual(validate(data)['mode'],'direct')
        data['source_ip']=data['ip']
        with self.assertRaises(ValueError): validate(data)

    def test_internal_pairing_window_expires_and_desktop_tokens_persist(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'state.json'
            device=Device(path)
            self.assertFalse(device.handle('GET','/health')[1]['pairing']['apiPaired'])
            self.assertEqual(device.handle('POST','/api/v1/new')[0],403)
            route='/api/v1/'+device.control_token+'/pairing'
            self.assertEqual(device.handle('POST',route,{})[0],200)
            token=device.handle('POST','/api/v1/new')[1]['auth_token']
            self.assertEqual(device.handle('POST','/api/v1/'+token+'/pairing',{})[0],403)
            self.assertTrue(Device(path).handle('GET','/health')[1]['pairing']['apiPaired'])
            device.pair_until=time.monotonic()-1
            self.assertEqual(device.handle('POST','/api/v1/new')[0],403)

    def test_nine_virtual_panels_can_feed_ten_hue_channels(self):
        layout=validate_layout(default_layout())
        panels=[{'panelId':p['panelId'],'rgb':[p['panelId']*20,40,60]} for p in layout['positionData']]
        mapping={str(channel):((channel%9)+1) for channel in range(10)}
        colors=channel_colors(panels,list(range(10)),mapping)
        self.assertEqual(len(colors),10)
        self.assertEqual(colors[0][1:],colors[9][1:])
        self.assertNotEqual(colors[0][1:],colors[1][1:])

    def test_telemetry_loss_does_not_fake_fresh_frames_and_stop_never_uses_arp(self):
        self.assertIsNone(snapshot({},100)['lastFrameTime'])
        self.assertEqual(snapshot({'syncPlus':{'lastFrameAge':5}},100)['lastFrameTime'],95)
        with patch.object(daily_sync.subprocess,'run') as run:
            daily_sync.stop_children([])
            run.assert_not_called()
