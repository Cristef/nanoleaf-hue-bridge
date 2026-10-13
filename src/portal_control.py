"""Profile, area, import and guided pairing operations for the authenticated portal."""
import asyncio
import copy
import ipaddress
import json
import os
from pathlib import Path
import threading
import time
import uuid
from control_panel_v2 import Control as BaseControl, read_json
from portal_settings import Store, active, atomic_json, profile_name, revision, tuning, validate, private_ip
from brightness import validate as validate_brightness
from panel_mapping import validate_mapping
from portal_auth import Auth


from advanced_portal import AdvancedControl

class Control(AdvancedControl, BaseControl):
    def __init__(self):
        super().__init__()
        self.store = Store(os.environ.get('PANEL_CONFIG', str(self.mapping_path.with_name('portal-settings.json'))))
        self.auth = Auth(self.mapping_path.with_name('portal-access.json'))
        from automation_api import AutomationAPI
        self.automation = AutomationAPI(self)
        self.catalog = {}
        self.job = {'phase': 'idle'}
        self.job_lock = threading.Lock()

    def allowed_bridge(self, value):
        value = private_ip(value)
        network = ipaddress.IPv4Network(os.environ.get('PANEL_NETWORK',os.environ['PANEL_BIND'] + '/24'), strict=False)
        if ipaddress.IPv4Address(value) not in network or value in (str(network.network_address), str(network.broadcast_address), os.environ['PANEL_BIND']):
            raise ValueError('Use the Hue Bridge IP on this LAN')
        return value

    def credential_path(self, bridge):
        if bridge == os.environ['PANEL_HUE_IP']:
            return self.credentials
        return self.mapping_path.parent/'hue-pairings'/(self.allowed_bridge(bridge) + '.json')

    async def fetch_areas(self, bridge):
        from hue_entertainment import HueEntertainmentAPI
        credentials = read_json(self.credential_path(bridge))
        if not credentials or not credentials.get('username'):
            raise ValueError('Pair this Hue Bridge first')
        api = HueEntertainmentAPI(bridge, credentials['username'])
        try:
            areas = await asyncio.wait_for(api.get_entertainment_areas(), 10)
            result = [{'id': a.id, 'name': a.name, 'channels': [
                {'id': c.channel_id, 'name': c.name, 'position': dict(zip(('x','y','z'),c.position))} for c in a.channels]} for a in areas]
            with self.lock:
                self.catalog[bridge] = result
            return result
        finally:
            await api.close()

    def refresh(self):
        bridge = self.store.read()['active']['bridge']
        areas = asyncio.run(self.fetch_areas(bridge))
        self.directory_error = None
        return {'areas': areas, 'bridge': bridge}

    def refresh_directory(self):
        while True:
            try:
                self.refresh()
            except Exception:
                self.directory_error = 'Unable to refresh lights. Check the Hue Bridge connection.'
            time.sleep(60)

    def mapping(self):
        return self.store.read()['active']['mapping']

    def brightness(self):
        return self.store.read()['active']['brightness']

    def state(self):
        with self.lock:
            config = self.store.read()
            stream = config['active']
            areas = self.catalog.get(stream['bridge'], [])
            self.area = next((a for a in areas if a['id'] == stream['area']),
                             {'id': stream['area'], 'name': 'Hue area unavailable', 'channels': []})
            result = super().state()
            result['panels'] = result.get('panels') or []
            if result['phase'] == 'waiting-for-colors':
                result['diagnostics']['huePhase'] = 'waiting'
            result.update({'version': '4.2.0', 'configRevision': revision(config), 'activeSettings': stream,
                           'tuningRevision': revision(stream['tuning']),
                           'profiles': [{'name': name, 'bridge': value['bridge'], 'area': value['area']}
                                        for name, value in config['profiles'].items()],
                           'areas': areas, 'bridge': stream['bridge'], 'setupJob': copy.deepcopy(self.job)})
            return self.advanced_state(result)

    def channels_for(self, stream):
        self.allowed_bridge(stream['bridge'])
        areas = self.catalog.get(stream['bridge'])
        if areas is None:
            areas = asyncio.run(self.fetch_areas(stream['bridge']))
        area = next((a for a in areas if a['id'] == stream['area']), None)
        if area is None or not area['channels']:
            raise ValueError('Select an available Hue Entertainment area')
        return {c['id'] for c in area['channels']}

    def validate_available(self, stream):
        stream = active(stream)
        channels = self.channels_for(stream)
        latest = read_json(self.runtime/'latest.json', {})
        panels = {p['panelId'] for p in latest.get('panels') or []}
        # Existing groups remain valid when the stream is off and its snapshot is absent.
        for group in self.store.read()['active']['mapping'].values():
            panels.update(group)
        validate_mapping(stream['mapping'], channels, panels)
        validate_brightness(stream['brightness'], channels)
        if set(stream.get('channelSettings',{})) - {str(c) for c in channels}: raise ValueError('Unknown channel settings')
        return stream

    def change(self, payload, transform):
        with self.lock:
            config = self.store.update(payload.get('configRevision'), transform)
            return {'configRevision': revision(config), 'activeSettings': config['active']}

    def save(self, payload):
        def modify(config):
            if payload.get('revision') != self.revision(config['active']['mapping']):
                raise FileExistsError('Mappings changed in another window. Reload before saving.')
            value = copy.deepcopy(config['active'])
            value['mapping'] = payload.get('mapping')
            config['active'] = self.validate_available(value)
        result = self.change(payload, modify)
        result.update({'mapping': result['activeSettings']['mapping'], 'revision': self.revision(result['activeSettings']['mapping'])})
        return result

    def save_brightness(self, payload):
        def modify(config):
            if payload.get('revision') != self.revision(config['active']['brightness']):
                raise FileExistsError('Brightness changed in another window. Reload before saving.')
            value = copy.deepcopy(config['active'])
            value['brightness'] = payload.get('brightness')
            config['active'] = self.validate_available(value)
        result = self.change(payload, modify)
        result.update({'brightness': result['activeSettings']['brightness'], 'revision': self.revision(result['activeSettings']['brightness'])})
        return result

    def save_tuning(self, payload):
        def modify(config):
            if payload.get('tuningRevision') != revision(config['active']['tuning']):
                raise FileExistsError('Color response changed in another window. Reload before saving.')
            config['active']['tuning'] = tuning(payload.get('tuning'))
        return self.change(payload, modify)

    def profile(self, payload):
        name = profile_name(payload.get('name'))
        operation = payload.get('operation')
        def modify(config):
            if operation == 'save':
                if name not in config['profiles'] and len(config['profiles']) >= 32:
                    raise ValueError('At most 32 profiles are allowed')
                if name in config['profiles'] and payload.get('overwrite') is not True:
                    raise FileExistsError('Profile already exists. Select replace to overwrite it.')
                config['profiles'][name] = copy.deepcopy(config['active'])
            elif operation == 'apply':
                config['active'] = self.validate_available(config['profiles'][name])
            elif operation == 'delete':
                del config['profiles'][name]
            else:
                raise ValueError('Invalid profile operation')
        return self.change(payload, modify)

    def select_area(self, payload):
        def modify(config):
            bridge = self.allowed_bridge(payload.get('bridge'))
            area = str(uuid.UUID(payload.get('area')))
            if bridge == config['active']['bridge'] and area == config['active']['area']:
                return
            value = copy.deepcopy(config['active'])
            value.update(bridge=bridge, area=area, mapping={},
                         brightness={'global': value['brightness']['global'], 'channels': {}})
            value.pop('channelSettings',None)
            config['active'] = self.validate_available(value)
        return self.change(payload, modify)

    def import_preview(self, payload):
        config = validate(payload.get('settings'))
        self.validate_available(config['active'])
        return {'area': config['active']['area'], 'bridge': config['active']['bridge'],
                'profiles': list(config['profiles']), 'lights': len(config['active']['mapping']),
                'globalBrightness': config['active']['brightness']['global']}

    def import_settings(self, payload):
        incoming = validate(payload.get('settings'))
        self.validate_available(incoming['active'])
        def modify(config):
            config.clear()
            config.update(incoming)
        return self.change(payload, modify)

    def identify(self, payload):
        state = self.state()
        channel = payload.get('channel')
        if type(channel) is not int or channel not in {c['id'] for c in self.area['channels']} or state['phase'] != 'streaming':
            raise ValueError('Identify is available for current lights while streaming')
        atomic_json(self.runtime/'identify.json', {'channel': channel, 'expires': time.time()+2, 'area': state['activeSettings']['area']})
        return {'status': 'identifying'}

    def setup_nanoleaf(self, payload):
        auth = read_json(self.control_auth)
        if not auth or not auth.get('token'):
            raise ValueError('Virtual pairing control unavailable')
        import urllib.request
        request = urllib.request.Request(self.virtual+'/api/v1/'+auth['token']+'/pairing', data=b'{}', headers={'Content-Type':'application/json'}, method='POST')
        with urllib.request.urlopen(request, timeout=3) as response:
            return json.load(response)


    def setup_hue(self, payload):
        bridge = self.allowed_bridge(payload.get('bridge'))
        with self.job_lock:
            if self.job.get('phase') in ('pairing', 'connecting'):
                raise ValueError('A Hue connection is already in progress')
            self.job = {'phase': 'connecting', 'bridge': bridge}
            threading.Thread(target=self.pair_job, args=(bridge,), daemon=True).start()
        return {'status': 'started'}

    def pair_job(self, bridge):
        async def connect():
            path = self.credential_path(bridge)
            if not path.exists():
                from hue_entertainment import HueEntertainmentAPI
                self.job = {'phase': 'pairing', 'bridge': bridge}
                api = HueEntertainmentAPI(bridge)
                try:
                    credentials = await asyncio.wait_for(api.pair('nanoleaf_hue_bridge#portal'), 180)
                    atomic_json(path, credentials)
                finally:
                    await api.close()
            return await self.fetch_areas(bridge)
        try:
            areas = asyncio.run(connect())
            self.job = {'phase': 'ready', 'bridge': bridge, 'areas': areas}
        except Exception:
            self.job = {'phase': 'error', 'bridge': bridge,
                        'message': 'Connection failed. Check the IP and press the Hue Bridge button during pairing.'}
