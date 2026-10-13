import hashlib,json,time,unittest
from types import SimpleNamespace
from unittest.mock import Mock
from test_portal import PortalTests
from automation_api import AutomationAPI
class AutomationTests(unittest.TestCase):
    def setUp(self):
        self.fixture=PortalTests();self.fixture.setUp();self.control=self.fixture.control;self.api=self.control.automation
    def tearDown(self):self.fixture.tearDown()
    def handler(self,token,origin=None):
        headers={'Authorization':'Bearer '+token}
        if origin:headers['Origin']=origin
        return SimpleNamespace(client_address=('10.23.46.2',1234),headers=headers)
    def test_token_hash_persistence_revocation_and_scope(self):
        created=self.api.manage({'operation':'create','label':'HA'})
        self.assertNotIn(created['token'],self.api.path.read_text())
        self.assertEqual(self.api.path.stat().st_mode & 0o077,0)
        self.api.authorize(self.handler(created['token']))
        AutomationAPI(self.control).authorize(self.handler(created['token']))
        self.assertNotIn('hash',self.api.manage({})['tokens'][0])
        self.api.manage({'operation':'revoke','id':created['id']})
        with self.assertRaises(PermissionError):self.api.authorize(self.handler(created['token']))
    def test_browser_and_public_client_rejected(self):
        token=self.api.manage({'operation':'create'})['token']
        with self.assertRaises(PermissionError):self.api.authorize(self.handler(token,'http://example.com'))
        h=self.handler(token);h.client_address=('8.8.8.8',42)
        with self.assertRaises(PermissionError):self.api.authorize(h)
    def test_authentication_throttled(self):
        for _ in range(10):
            with self.assertRaises(PermissionError):self.api.authorize(self.handler('wrong'))
        with self.assertRaises(TimeoutError):self.api.authorize(self.handler('wrong'))
    def test_commands_preserve_individual_brightness_and_reject_admin(self):
        result=self.api.command({'command':'brightness','value':72})
        self.assertEqual(result['brightness'],72)
        self.assertEqual(self.control.store.read()['active']['brightness']['channels'],{'0':65})
        for command,value in [('brightness',True),('brightness',101),('mapping',{}),('restart',True),('sync','on')]:
            with self.assertRaises(ValueError):self.api.command({'command':command,'value':value})
    def test_state_no_secrets_and_stable_id_profile_drift(self):
        first=self.api.state();second=AutomationAPI(self.control).state()
        self.assertEqual(first['id'],second['id']);self.assertEqual(first['profile'],'Current setup')
        self.assertIsNone(self.api.command({'command':'brightness','value':44})['profile'])
        self.assertNotIn('csrf',first);self.assertNotIn('bridge',first)
