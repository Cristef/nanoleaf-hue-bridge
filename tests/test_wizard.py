import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, Mock
import wizard
import asyncio
import sys
from types import SimpleNamespace
from config import CONFIG


class WizardTests(unittest.TestCase):
    def test_prompt_uses_separate_terminal_streams(self):
        from io import StringIO
        from contextlib import nullcontext
        output = StringIO()
        input_stream = StringIO('\n')
        with patch('builtins.open', side_effect=[nullcontext(output), nullcontext(input_stream)]) as opened:
            self.assertEqual(wizard.ask('Interface', 'eth0'), 'eth0')
        self.assertEqual([call.args for call in opened.call_args_list],
                         [('/dev/tty', 'w'), ('/dev/tty', 'r')])
        self.assertEqual(output.getvalue(), 'Interface [eth0]: ')

    def test_discovery_parses_ipv4_and_deduplicates(self):
        text = '=;eth0;IPv4;TV;_nanoleafapi._tcp;local;tv.local;192.0.2.10;16021;"md=NL69"\n'
        result = Mock(stdout=text+text)
        with patch('wizard.subprocess.run', return_value=result):
            self.assertEqual(wizard.discover(), [('TV','192.0.2.10','NL69')])

    def test_selection_and_invalid_ip_prompt_retry(self):
        with patch('wizard.ask', side_effect=['9','2']):
            self.assertEqual(wizard.choose('test', [('one',1),('two',2)]), 2)
        with patch('wizard.ask', side_effect=['bad','192.0.2.10']):
            self.assertEqual(wizard.address('IP'), '192.0.2.10')

    def test_existing_api_pairing_does_not_open_new_window(self):
        with patch('wizard.wait_virtual'), patch('wizard.health', return_value={'pairing':{'apiPaired':True}}), \
                patch('wizard.ask') as ask:
            wizard.desktop_pairing({'name':'Test'})
            ask.assert_not_called()

    def test_hue_pairing_area_selection_and_credentials_reuse(self):
        calls = []
        class API:
            def __init__(self, host, key=None): calls.append(('api',host,key))
            async def pair(self, device_type):
                calls.append(('pair',device_type))
                return {'username':'synthetic-test-user','clientkey':'synthetic-test-key'}
            async def get_entertainment_areas(self):
                return [SimpleNamespace(name='Test area',id=CONFIG['hue_area'],channels=[0,1])]
            async def close(self): calls.append(('close',))
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent, prefix='test-config-') as folder:
            auth = Path(folder)/'auth.json'
            data = dict(CONFIG)
            with patch.dict(sys.modules, {'hue_entertainment':SimpleNamespace(HueEntertainmentAPI=API)}), \
                    patch('wizard.AUTH', auth), patch('wizard.ask', return_value=''), \
                    patch('wizard.choose', return_value=CONFIG['hue_area']), patch('wizard.save') as save:
                asyncio.run(wizard.hue(data))
                self.assertEqual(json.loads(auth.read_text())['username'], 'synthetic-test-user')
                save.assert_called_once_with(data)
                asyncio.run(wizard.hue(data))
                self.assertEqual(sum(x[0]=='pair' for x in calls),1)
                self.assertEqual(sum(x[0]=='close' for x in calls),3)
