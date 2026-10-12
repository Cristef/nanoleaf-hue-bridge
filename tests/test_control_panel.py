import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
import time
import urllib.error
import urllib.request
from unittest.mock import patch

from control_panel_v2 import Control, Handler, ThreadingHTTPServer


class ControlPanelTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        path = Path(self.folder.name)
        self.environment = patch.dict(os.environ, {
            'PANEL_MAPPING': str(path/'mapping.json'), 'PANEL_RUNTIME': str(path),
            'PANEL_VIRTUAL_URL': 'http://127.0.0.1:16021', 'PANEL_HUE_IP': '192.0.2.3',
            'PANEL_HUE_AREA': 'test-area', 'HUE_CREDENTIALS': str(path/'auth.json'),
            'PANEL_CONTROL_AUTH': str(path/'control-auth.json'), 'PANEL_BIND': '127.0.0.1'})
        self.environment.start()
        self.control = Control()
        self.control.area = {'name': 'Test', 'channels': [{'id': 0, 'name': 'Test light'}]}
        (path/'latest.json').write_text(json.dumps({'panels': [{'panelId': 1, 'rgb': [10, 20, 30]}]}))

    def tearDown(self):
        self.environment.stop()
        self.folder.cleanup()

    def test_save_atomic_validation_and_stale_revision(self):
        revision = self.control.revision({})
        result = self.control.save({'mapping': {'0': [1]}, 'revision': revision})
        self.assertEqual(json.loads(self.control.mapping_path.read_text()), {'0': [1]})
        with self.assertRaises(FileExistsError):
            self.control.save({'mapping': {}, 'revision': revision})
        with self.assertRaises(ValueError):
            self.control.save({'mapping': {'0': [999]}, 'revision': result['revision']})
        self.assertEqual(self.control.mapping(), {'0': [1]})

    def test_http_rejects_foreign_origin_and_accepts_valid_mapping(self):
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        server.control = self.control
        host = f'127.0.0.1:{server.server_port}'
        self.control.allowed_hosts = {host}
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            def request(origin, token):
                return urllib.request.Request('http://' + host + '/api/mapping',
                    data=json.dumps({'mapping': {'0': [1]}, 'revision': self.control.revision({})}).encode(),
                    headers={'Content-Type': 'application/json', 'Origin': origin, 'X-Control-Token': token})
            for origin, token in [('http://foreign.example', self.control.csrf), ('http://' + host, 'wrong')]:
                with self.assertRaises(urllib.error.HTTPError) as error:
                    urllib.request.urlopen(request(origin, token), timeout=2)
                self.assertEqual(error.exception.code, 403)
            with urllib.request.urlopen(request('http://' + host, self.control.csrf), timeout=2) as response:
                self.assertEqual(response.status, 200)
                self.assertEqual(json.load(response)['mapping'], {'0': [1]})
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_brightness_atomic_validation_and_conflict(self):
        settings = {'global': 100, 'channels': {}}
        revision = self.control.revision(settings)
        saved = self.control.save_brightness({'brightness': {'global': 50, 'channels': {'0': 80}}, 'revision': revision})
        with self.assertRaises(FileExistsError):
            self.control.save_brightness({'brightness': settings, 'revision': revision})
        with self.assertRaises(ValueError):
            self.control.save_brightness({'brightness': {'global': 120, 'channels': {}}, 'revision': saved['revision']})
        self.assertEqual(self.control.brightness(), {'global': 50, 'channels': {'0': 80}})
        self.assertFalse(self.control.mapping_path.exists())

    def test_stale_diagnostics_do_not_claim_active_output(self):
        self.control.health_time = time.monotonic()
        self.control.health_cache = {'on': True, 'homeKit': {'paired': True}}
        (self.control.runtime/'hue-status.json').write_text(json.dumps({
            'time': time.time()-60, 'phase': 'streaming', 'frames': 99, 'colors': {'0': [1, 2, 3]}}))
        result = self.control.state()
        self.assertEqual(result['diagnostics']['sentColors'], {})
        self.assertEqual(result['diagnostics']['huePhase'], 'unavailable')
        self.assertIsNone(result['diagnostics']['frameAge'])
        self.assertEqual(result['version'], '2.0.0')
        self.control.health_cache['on'] = False
        self.assertEqual(self.control.state()['diagnostics']['huePhase'], 'off')

    def test_corrupt_brightness_is_not_silently_shown_as_default(self):
        self.control.brightness_path.write_text('{broken')
        with self.assertRaises(ValueError):
            self.control.brightness()


if __name__ == '__main__':
    unittest.main()

