"""Local web control panel. Credentials never leave the container."""
import asyncio
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import threading
import time
import urllib.request

from panel_mapping import validate_mapping
from brightness import validate as validate_brightness, DEFAULT

ROOT = Path(__file__).resolve().parent


def read_json(path, default=None):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return default


class Control:
    def __init__(self):
        self.mapping_path = Path(os.environ['PANEL_MAPPING'])
        self.brightness_path = Path(os.environ.get('PANEL_BRIGHTNESS', str(self.mapping_path.with_name('brightness.json'))))
        self.runtime = Path(os.environ['PANEL_RUNTIME'])
        self.virtual = os.environ['PANEL_VIRTUAL_URL'].rstrip('/')
        self.bridge = os.environ['PANEL_HUE_IP']
        self.area_id = os.environ['PANEL_HUE_AREA']
        self.credentials = Path(os.environ['HUE_CREDENTIALS'])
        self.control_auth = Path(os.environ['PANEL_CONTROL_AUTH'])
        self.allowed_hosts = {'127.0.0.1:8080', 'localhost:8080', os.environ['PANEL_BIND'] + ':8080'}
        self.csrf = secrets.token_urlsafe(32)
        self.lock = threading.RLock()
        self.area = {'name': 'Hue area', 'channels': []}
        self.directory_error = None
        self.health_cache = {}
        self.health_time = 0

    async def load_area(self):
        from hue_entertainment import HueEntertainmentAPI
        auth = read_json(self.credentials)
        if not auth or 'username' not in auth:
            raise ValueError('Hue credentials unavailable')
        api = HueEntertainmentAPI(self.bridge, auth['username'])
        try:
            areas = await asyncio.wait_for(api.get_entertainment_areas(), 10)
            area = next((a for a in areas if a.id == self.area_id), None)
            if area is None:
                raise ValueError('Hue area unavailable')
            return {'name': area.name, 'channels': [
                {'id': c.channel_id, 'name': c.name} for c in area.channels]}
        finally:
            await api.close()

    def refresh_directory(self):
        while True:
            try:
                area = asyncio.run(self.load_area())
                with self.lock:
                    self.area = area
                    self.directory_error = None
            except Exception:
                with self.lock:
                    self.directory_error = 'Unable to refresh lights from the Hue Bridge.'
            time.sleep(60)

    def mapping(self):
        value = read_json(self.mapping_path, {})
        return validate_mapping(value)

    def revision(self, mapping):
        return hashlib.sha256(json.dumps(mapping, sort_keys=True).encode()).hexdigest()

    def brightness(self):
        if not self.brightness_path.exists():
            return validate_brightness(DEFAULT)
        return validate_brightness(read_json(self.brightness_path))

    def save_brightness(self, payload):
        with self.lock:
            current = self.brightness()
            if payload.get('revision') != self.revision(current):
                raise FileExistsError('Brightness changed in another window')
            settings = validate_brightness(payload.get('brightness'), {c['id'] for c in self.area['channels']})
            self.brightness_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.brightness_path.with_suffix('.tmp')
            with temporary.open('w') as stream:
                json.dump(settings, stream, indent=2)
                stream.write('\n')
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(temporary, 0o600)
            temporary.replace(self.brightness_path)
            return {'brightness': settings, 'revision': self.revision(settings)}

    def state(self):
        with self.lock:
            if time.monotonic() - self.health_time > 1:
                try:
                    with urllib.request.urlopen(self.virtual + '/health', timeout=1) as response:
                        self.health_cache = json.load(response)
                except (OSError, ValueError):
                    self.health_cache = {}
                self.health_time = time.monotonic()
            latest = read_json(self.runtime / 'latest.json', {})
            status = read_json(self.runtime / 'status.json', {})
            hue = read_json(self.runtime / 'hue-status.json', {})
            mapping = self.mapping()
            brightness = self.brightness()
            age = time.time() - (latest.get('lastFrameTime') or 0)
            status_age = time.time() - (status.get('time') or 0)
            homekit = self.health_cache.get('homeKit')
            homekit = homekit if isinstance(homekit, dict) else {}
            return {'version': '2.0.0', 'csrf': self.csrf, 'mapping': mapping, 'revision': self.revision(mapping),
                    'brightness': brightness, 'brightnessRevision': self.revision(brightness),
                    'diagnostics': {'virtualReachable': bool(self.health_cache),
                        'homeKitPaired': homekit.get('paired'),
                        'frameAge': round(max(0, age), 1) if latest.get('lastFrameTime') else None,
                        'relayCounters': latest.get('counts', {}),
                        'huePhase': 'off' if self.health_cache.get('on') is False else (
                            hue.get('phase', 'unavailable') if time.time() - hue.get('time', 0) < 5 else 'unavailable'),
                        'hueFrames': hue.get('frames', 0),
                        'sentColors': hue.get('colors', {}) if time.time() - hue.get('time', 0) < 5 and hue.get('phase') == 'streaming' else {}},
                    'area': self.area, 'directoryError': self.directory_error,
                    'on': self.health_cache.get('on'),
                    'phase': status.get('phase', 'unavailable') if status_age < 5 else 'unavailable',
                    'fresh': age < 3, 'panels': latest.get('panels', []),
                    'mappingError': hue.get('mappingError') if time.time() - hue.get('time', 0) < 5 else None}

    def save(self, payload):
        with self.lock:
            current = self.mapping()
            if payload.get('revision') != self.revision(current):
                raise FileExistsError('Settings changed in another window')
            latest = read_json(self.runtime / 'latest.json', {})
            known = {p['panelId'] for p in latest.get('panels', [])}
            mapping = validate_mapping(payload.get('mapping'),
                                       {c['id'] for c in self.area['channels']}, known)
            self.mapping_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.mapping_path.with_suffix('.tmp')
            with temporary.open('w') as stream:
                json.dump(mapping, stream, indent=2)
                stream.write('\n')
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(temporary, 0o600)
            temporary.replace(self.mapping_path)
            return {'mapping': mapping, 'revision': self.revision(mapping)}

    def switch(self, value):
        if type(value) is not bool:
            raise ValueError('Invalid switch state')
        auth = read_json(self.control_auth)
        if not auth or not auth.get('token'):
            raise ValueError('Virtual control unavailable')
        request = urllib.request.Request(self.virtual + '/api/v1/' + auth['token'] + '/state',
                                         data=json.dumps({'on': {'value': value}}).encode(),
                                         headers={'Content-Type': 'application/json'}, method='PUT')
        with urllib.request.urlopen(request, timeout=2) as response:
            if response.status != 204:
                raise ValueError('Virtual switch update failed')
        self.health_time = 0
        return {'on': value}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def respond(self, status, payload, content_type='application/json; charset=utf-8'):
        body = json.dumps(payload).encode() if isinstance(payload, dict) else payload
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('Content-Security-Policy', "default-src 'self'; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
        self.end_headers()
        self.wfile.write(body)

    def valid_host(self):
        return self.headers.get('Host', '') in self.server.control.allowed_hosts

    def do_GET(self):
        if not self.valid_host():
            return self.respond(403, {'error': 'Host not allowed.'})
        if self.path == '/api/state':
            try:
                return self.respond(200, self.server.control.state())
            except (OSError, ValueError):
                return self.respond(503, {'error': 'Configuration unavailable.'})
        paths = {'/': ('index.html', 'text/html; charset=utf-8'),
                 '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
                 '/style.css': ('style.css', 'text/css; charset=utf-8')}
        if self.path not in paths:
            return self.respond(404, {'error': 'Resource not found.'})
        name, content_type = paths[self.path]
        self.respond(200, (ROOT / 'web' / name).read_bytes(), content_type)

    def do_POST(self):
        control = self.server.control
        if (not self.valid_host() or self.headers.get('Origin') != 'http://' + self.headers.get('Host', '')
                or self.headers.get('X-Control-Token') != control.csrf
                or self.headers.get('Content-Type', '').split(';')[0] != 'application/json'):
            return self.respond(403, {'error': 'Request not allowed. Reload the page.'})
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 16384:
                raise ValueError('Invalid request size')
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise ValueError('Invalid body')
            if self.path == '/api/mapping':
                result = control.save(payload)
            elif self.path == '/api/brightness':
                result = control.save_brightness(payload)
            elif self.path == '/api/switch':
                result = control.switch(payload.get('on'))
            else:
                return self.respond(404, {'error': 'Resource not found.'})
            self.respond(200, result)
        except FileExistsError:
            self.respond(409, {'error': 'Settings changed in another window. Reload before saving.'})
        except (ValueError, KeyError):
            self.respond(400, {'error': 'Invalid settings. Check available lights, panels and brightness values.'})
        except OSError:
            self.respond(503, {'error': 'Operation failed. Check device connectivity.'})


def main():
    control = Control()
    threading.Thread(target=control.refresh_directory, daemon=True).start()
    server = ThreadingHTTPServer((os.environ['PANEL_BIND'], 8080), Handler)
    server.control = control
    print('Control panel ready on port 8080', flush=True)
    server.serve_forever()


if __name__ == '__main__':
    main()
