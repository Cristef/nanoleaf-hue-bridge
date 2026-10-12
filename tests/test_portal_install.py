import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import portal_install
from portal_settings import atomic_json

class PortalInstallTests(unittest.TestCase):
    def test_first_install_generates_settings_but_no_account_or_key(self):
        with tempfile.TemporaryDirectory() as folder:
            state=Path(folder)/'state';env=Path(folder)/'portal.env'
            data={'ip':'10.23.45.20','prefix':25,'hue_ip':'10.23.45.30','hue_area':'11111111-1111-4111-8111-111111111111'}
            with patch.object(portal_install,'STATE',state),patch.object(portal_install,'ENV',env):
                portal_install.provision(data)
                settings=json.loads((state/'portal-settings.json').read_text())
                self.assertEqual(settings['active']['brightness']['global'],100)
                self.assertIn('Current setup',settings['profiles'])
                self.assertFalse((state/'portal-access.json').exists())
                self.assertFalse((state/'portal-access-key.txt').exists())
                self.assertIn('PANEL_NETWORK=10.23.45.20/25',env.read_text())
                self.assertEqual(env.stat().st_mode&0o777,0o600)
                settings['active']['brightness']['global']=37
                atomic_json(state/'portal-settings.json',settings)
                (state/'portal-access.json').write_text('existing account')
                portal_install.provision(data)
                self.assertEqual(json.loads((state/'portal-settings.json').read_text()),settings)
                self.assertEqual((state/'portal-access.json').read_text(),'existing account')
