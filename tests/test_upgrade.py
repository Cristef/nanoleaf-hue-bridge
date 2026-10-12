import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace
import portal_install

spec=importlib.util.spec_from_file_location('release_upgrade',Path(__file__).resolve().parents[1]/'upgrade.py')
upgrade=importlib.util.module_from_spec(spec);spec.loader.exec_module(upgrade)

class UpgradeTests(unittest.TestCase):
    def exercise(self,fail=False):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);installed=base/'opt/nanoleaf-hue';installed.mkdir(parents=True)
            (installed/'old.py').write_text('old code')
            (installed/'venv').mkdir();(installed/'venv/keep').write_text('environment')
            original_path=Path
            def mapped(value):
                value=str(value)
                return base/value.lstrip('/') if value.startswith(('/etc/','/root/','/var/')) else original_path(value)
            config=mapped('/etc/nanoleaf-hue/config.json');config.parent.mkdir(parents=True)
            sample=json.loads((upgrade.SOURCE/'config.example.json').read_text())
            sample.update(ip='10.23.45.20',hue_ip='10.23.45.30')
            config.write_text(json.dumps(sample))
            state=mapped('/var/lib/nanoleaf-hue-sync');state.mkdir(parents=True)
            (state/'hue-auth.json').write_text('synthetic private credentials')
            (state/'portal-access.json').write_text('synthetic existing account')
            virtual=mapped('/var/lib/nanoleaf-hue-virtual');virtual.mkdir(parents=True)
            (virtual/'homekit.state').write_text('synthetic paired identity')
            units=mapped('/etc/systemd/system');units.mkdir(parents=True)
            for unit in upgrade.UNITS[:2]:(units/(unit+'.service')).write_text('previous unit')
            failed=False
            def run(*args):
                nonlocal failed
                if fail and args[:2]==('systemctl','enable') and not failed:
                    failed=True;raise RuntimeError('synthetic startup failure')
            response=SimpleNamespace(status=200)
            from contextlib import nullcontext
            with patch.object(upgrade,'ROOT',installed),patch.object(upgrade,'Path',side_effect=mapped),patch.object(upgrade,'run',side_effect=run),patch.object(upgrade.subprocess,'run'),patch.object(upgrade.os,'geteuid',return_value=0),patch.object(upgrade.urllib.request,'urlopen',return_value=nullcontext(response)),patch.object(portal_install,'STATE',state),patch.object(portal_install,'ENV',config.parent/'portal.env'):
                if fail:
                    with self.assertRaises(RuntimeError):upgrade.main()
                else:upgrade.main()
            self.assertEqual((state/'hue-auth.json').read_text(),'synthetic private credentials')
            self.assertEqual((state/'portal-access.json').read_text(),'synthetic existing account')
            self.assertEqual((virtual/'homekit.state').read_text(),'synthetic paired identity')
            self.assertEqual((installed/'venv/keep').read_text(),'environment')
            backups=list(mapped('/root/nanoleaf-hue-backups').iterdir())
            self.assertEqual(len(backups),1)
            self.assertFalse((backups[0]/'code/venv').exists())
            if fail:self.assertEqual((units/'nanoleaf-hue-sync.service').read_text(),'previous unit')
            else:self.assertTrue((installed/'control_panel.py').exists())

    def test_update_preserves_pairings_accounts_and_environment(self):self.exercise()
    def test_failed_startup_restores_previous_units(self):self.exercise(True)
