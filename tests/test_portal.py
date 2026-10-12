import asyncio
import copy
import json
import os
from pathlib import Path
import socket
import struct
import tempfile
import threading
import time
from types import SimpleNamespace, ModuleType
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch
from color_response import ColorResponse
from portal_settings import Store, TUNING, atomic_json, revision, validate
from portal_auth import Auth
from portal_control import Control
from control_panel import Handler, ThreadingHTTPServer

AREA = '11111111-1111-4111-8111-111111111111'
OTHER = 'b373d690-6fcf-4fb5-9f72-cb0b31772fc3'


def configuration():
    stream = {'bridge': '10.23.45.83', 'area': AREA, 'mapping': {'0': [1]},
              'brightness': {'global': 60, 'channels': {'0': 65}}, 'tuning': dict(TUNING)}
    return {'schema': 3, 'active': stream, 'profiles': {'Current setup': copy.deepcopy(stream)}}


class ColorResponseTests(unittest.TestCase):
    def test_default_is_exact_and_zero_is_immediate(self):
        processor = ColorResponse()
        commands = [(0, 65535, 32123, 100)]
        self.assertEqual(processor.process(commands, TUNING, {'global':100,'channels':{}}, 1), commands)
        self.assertEqual(processor.process(commands, {**TUNING,'smoothingMs':1000}, {'global':0,'channels':{}}, 2), [(0,0,0,0)])

    def test_smoothing_uses_elapsed_time_and_threshold_is_immediate(self):
        processor = ColorResponse(); levels = {'global':100,'channels':{}}
        settings = {**TUNING,'smoothingMs':1000}
        processor.process([(0,0,0,0)], settings, levels, 0)
        result = processor.process([(0,65535,0,0)], settings, levels, 1)
        self.assertAlmostEqual(result[0][1]/65535, 1-2.718281828**-1, places=4)
        self.assertEqual(processor.process([(0,257,257,257)], {**settings,'blackThreshold':10}, levels, 2), [(0,0,0,0)])

    def test_desaturation_preserves_value(self):
        result = ColorResponse().process([(0,65535,0,0)], {**TUNING,'saturation':0}, {'global':100,'channels':{}}, 1)
        self.assertEqual(result, [(0,65535,65535,65535)])


class PortalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name)
        self.env = patch.dict(os.environ, {'PANEL_MAPPING':str(self.path/'mapping.json'),
            'PANEL_RUNTIME':str(self.path), 'PANEL_VIRTUAL_URL':'http://127.0.0.1:16021',
            'PANEL_HUE_IP':'10.23.45.83', 'PANEL_HUE_AREA':AREA, 'PANEL_BIND':'10.23.45.103',
            'HUE_CREDENTIALS':str(self.path/'hue-auth.json'), 'PANEL_CONTROL_AUTH':str(self.path/'virtual-auth.json'),
            'PANEL_CONFIG':str(self.path/'portal-settings.json'), 'PANEL_HOMEKIT_SETUP':str(self.path/'homekit.json')})
        self.env.start()
        atomic_json(self.path/'portal-settings.json', configuration())
        atomic_json(self.path/'latest.json', {'panels':[{'panelId':1,'rgb':[100,50,20]}]})
        self.control = Control()
        self.control.catalog = {'10.23.45.83':[{'id':AREA,'name':'TV','channels':[{'id':0,'name':'Lamp'}]},
                                                 {'id':OTHER,'name':'Other','channels':[{'id':1,'name':'Other lamp'}]}]}
        self.control.health_time=time.monotonic();self.control.health_cache={'on':False,'homeKit':{'paired':True}}

    def tearDown(self):
        self.env.stop();self.temp.cleanup()

    def payload(self, **fields):
        return {'configRevision':revision(self.control.store.read()), **fields}

    def test_profiles_are_atomic_and_area_changes_clear_channel_settings(self):
        self.control.profile(self.payload(operation='save', name='Cinema'))
        with self.assertRaises(FileExistsError):
            self.control.profile(self.payload(operation='save', name='Cinema'))
        self.control.select_area(self.payload(bridge='10.23.45.83', area=OTHER))
        value=self.control.store.read()['active']
        self.assertEqual(value['mapping'],{});self.assertEqual(value['brightness'],{'global':60,'channels':{}})
        self.control.profile(self.payload(operation='apply',name='Cinema'))
        self.assertEqual(self.control.store.read()['active'],configuration()['active'])

    def test_import_rejects_secrets_and_invalid_active_channels_without_changes(self):
        before=self.control.store.read();bad=copy.deepcopy(before);bad['credentials']={'token':'test'}
        with self.assertRaises(ValueError):self.control.import_settings(self.payload(settings=bad))
        bad=copy.deepcopy(before);bad['active']['mapping']={'9':[1]}
        with self.assertRaises(ValueError):self.control.import_settings(self.payload(settings=bad))
        self.assertEqual(self.control.store.read(),before)
        result=self.control.import_preview({'settings':before})
        self.assertEqual(result['globalBrightness'],60)
        self.control.import_settings(self.payload(settings=before))

    def test_stale_revision_and_invalid_tuning_do_not_modify_settings(self):
        expected=revision(self.control.store.read())
        self.control.save_tuning(self.payload(tuning={**TUNING,'smoothingMs':250},tuningRevision=revision(TUNING)))
        with self.assertRaises(FileExistsError):
            self.control.profile({'configRevision':expected,'operation':'save','name':'Stale'})
        before=self.control.store.read()
        with self.assertRaises(ValueError):
            self.control.save_tuning(self.payload(tuning={**TUNING,'saturation':201},tuningRevision=revision(before['active']['tuning'])))
        self.assertEqual(self.control.store.read(),before)

    def test_store_corruption_retains_last_valid_consumer_config(self):
        store=self.control.store;before=store.read();store.path.write_text('{broken')
        self.assertEqual(store.read(retain=True),before)
        self.assertIsNotNone(store.error)
        with self.assertRaises(ValueError):store.read()

    def test_login_cookie_required_for_state_export_and_mutations(self):
        self.control.auth.configure('owner','test-password')
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);server.control=self.control
        host=f'127.0.0.1:{server.server_port}';self.control.allowed_hosts={host}
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        base='http://'+host
        try:
            for route in ['/api/state','/api/export']:
                with self.assertRaises(urllib.error.HTTPError) as error:urllib.request.urlopen(base+route,timeout=2)
                self.assertEqual(error.exception.code,401)
            def post(route, payload, cookie='', origin=base):
                return urllib.request.Request(base+route,data=json.dumps(payload).encode(),
                    headers={'Content-Type':'application/json','Origin':origin,'X-Control-Token':self.control.csrf,'Cookie':cookie})
            with self.assertRaises(urllib.error.HTTPError) as error:
                urllib.request.urlopen(post('/api/setup/nanoleaf',{}),timeout=2)
            self.assertEqual(error.exception.code,401)
            with urllib.request.urlopen(post('/api/login',{'username':'owner','password':'test-password'}),timeout=10) as response:
                cookie=response.headers['Set-Cookie'].split(';')[0]
                self.assertIn('HttpOnly',response.headers['Set-Cookie'])
                self.assertIn('SameSite=Strict',response.headers['Set-Cookie'])
            with patch.object(self.control,'setup_nanoleaf',return_value={'seconds':120,'method':'desktop-button'}) as pair:
                with self.assertRaises(urllib.error.HTTPError) as error:
                    urllib.request.urlopen(post('/api/setup/nanoleaf',{},cookie,'http://foreign.example'),timeout=2)
                self.assertEqual(error.exception.code,403)
                pair.assert_not_called()
                with urllib.request.urlopen(post('/api/setup/nanoleaf',{},cookie),timeout=2) as response:
                    self.assertEqual(json.load(response)['seconds'],120)
                pair.assert_called_once()
            with urllib.request.urlopen(urllib.request.Request(base+'/api/export',headers={'Cookie':cookie}),timeout=2) as response:
                exported=json.load(response)
            self.assertEqual(set(exported),{'schema','active','profiles'})
            with self.assertRaises(urllib.error.HTTPError) as error:
                urllib.request.urlopen(post('/api/profile',self.payload(operation='save',name='Foreign'),cookie,'http://foreign.example'),timeout=2)
            self.assertEqual(error.exception.code,403)
            with urllib.request.urlopen(post('/api/logout',{},cookie),timeout=2):pass
            with self.assertRaises(urllib.error.HTTPError):urllib.request.urlopen(urllib.request.Request(base+'/api/state',headers={'Cookie':cookie}),timeout=2)
        finally:server.shutdown();server.server_close();thread.join(2)

    def test_auth_throttles_and_does_not_store_plaintext_key(self):
        key='test-password';self.control.auth.configure('owner',key)
        self.assertNotIn(key,self.control.auth.path.read_text())
        for _ in range(5):
            with self.assertRaises(PermissionError):self.control.auth.login('wrong','192.0.2.1')
        with self.assertRaises(TimeoutError):self.control.auth.login({'username':'owner','password':key},'192.0.2.1')

    def test_setup_only_accepts_bridge_on_container_lan(self):
        for value in ['8.8.8.8','127.0.0.1','10.23.45.103','10.23.46.83','10.23.45.255']:
            with self.assertRaises(ValueError):self.control.allowed_bridge(value)
        self.assertEqual(self.control.allowed_bridge('10.23.45.83'),'10.23.45.83')


class StreamSwitchTests(unittest.TestCase):
    def test_consumer_releases_old_area_before_streaming_new_channels(self):
        import hue_sync
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder);config=configuration();config['active']['brightness']={'global':100,'channels':{}}
            atomic_json(path/'settings.json',config);atomic_json(path/'auth.json',{'username':'test','clientkey':'test'})
            with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as reserve:
                reserve.bind(('127.0.0.1',0));port=reserve.getsockname()[1]
            events=[]
            module=ModuleType('hue_entertainment')
            class Session:
                def __init__(self,*args):self.area=None
                async def get_entertainment_areas(self):return [SimpleNamespace(id=AREA,channels=[SimpleNamespace(channel_id=0)]),SimpleNamespace(id=OTHER,channels=[SimpleNamespace(channel_id=1)])]
                async def start(self,area,**kwargs):self.area=area;events.append(('start',area))
                async def stop(self):events.append(('stop',self.area))
                async def aclose(self):events.append(('close',self.area))
                def send(self,commands):events.append(('send',self.area,[c['channel_id'] for c in commands]))
            module.EntertainmentSession=Session;module.HueEntertainmentAPI=object;module.LightColorCommand=lambda **kw:kw
            async def exercise():
                async def frames():
                    with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as sender:
                        for index in range(25):
                            await asyncio.sleep(.06)
                            if index==4:
                                config['active']['area']=OTHER;config['active']['mapping']={};atomic_json(path/'settings.json',config)
                            sender.sendto(struct.pack('!H',1)+struct.pack('!HBBBBH',1,100,50,20,0,0),('127.0.0.1',port))
                args=SimpleNamespace(command='stream',credentials=str(path/'auth.json'),bridge='10.23.45.83',area=AREA,
                    config=str(path/'settings.json'),mapping=None,brightness=None,continuous=False,seconds=1,listen_port=port)
                await asyncio.gather(hue_sync.run(args),frames())
            with patch.dict('sys.modules',{'hue_entertainment':module}),patch.dict(os.environ,{'HUE_STATUS':str(path/'status.json'),'HUE_IDENTIFY':str(path/'identify.json')}):
                asyncio.run(exercise())
            self.assertLess(events.index(('stop',AREA)),events.index(('start',OTHER)))
            self.assertTrue(any(e[0]=='send' and e[1]==OTHER and e[2]==[1] for e in events))


if __name__=='__main__':unittest.main()

class AccountTests(unittest.TestCase):
    def test_account_cannot_be_overwritten_and_keys_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            auth=Auth(Path(directory)/'auth.json')
            with self.assertRaises(ValueError): auth.configure('owner','1234567')
            self.assertTrue(auth.needs_setup())
            auth.configure('owner','12345678')
            self.assertFalse(auth.needs_setup())
            with self.assertRaises(PermissionError): auth.login('12345678','local')
            token=auth.login({'username':'owner','password':'12345678'},'local')
            self.assertTrue(auth.check('nhb_session='+token))
            with self.assertRaises(FileExistsError): auth.configure('other','abcdefgh')
            self.assertNotIn('12345678',auth.path.read_text())

    def test_fresh_account_setup(self):
        with tempfile.TemporaryDirectory() as directory:
            auth=Auth(Path(directory)/'auth.json')
            self.assertTrue(auth.needs_setup())
            auth.configure('owner','a-long-test-password')
            self.assertFalse(auth.needs_setup())

    def test_first_visit_http_setup_without_key(self):
        with tempfile.TemporaryDirectory() as directory:
            auth=Auth(Path(directory)/'auth.json')
            server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
            host=f'127.0.0.1:{server.server_port}'
            server.control=SimpleNamespace(auth=auth,allowed_hosts={host},csrf='test-csrf')
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            base='http://'+host
            def post(body,cookie=''):
                return urllib.request.Request(base+'/api/account/setup',data=json.dumps(body).encode(),headers={'Content-Type':'application/json','Origin':base,'X-Control-Token':'test-csrf','Cookie':cookie})
            try:
                with urllib.request.urlopen(base+'/api/session',timeout=2) as response: self.assertTrue(json.load(response)['setupRequired'])
                with self.assertRaises(urllib.error.HTTPError) as error:
                    urllib.request.urlopen(post({'username':'owner','password':'1234567','confirmation':'1234567'}),timeout=10)
                self.assertEqual(error.exception.code,400)
                with urllib.request.urlopen(post({'username':'owner','password':'12345678','confirmation':'12345678'}),timeout=10) as response:
                    cookie=response.headers['Set-Cookie'].split(';')[0]
                self.assertTrue(auth.check(cookie))
                with self.assertRaises(urllib.error.HTTPError) as error:
                    urllib.request.urlopen(post({'username':'other','password':'abcdefgh','confirmation':'abcdefgh'},cookie),timeout=10)
                self.assertEqual(error.exception.code,409)
            finally:server.shutdown();server.server_close();thread.join(2)
