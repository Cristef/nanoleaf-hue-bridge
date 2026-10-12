"""Authenticated Nanoleaf Hue Bridge portal, version 3."""
from http.cookies import SimpleCookie
import json
import os
from pathlib import Path
import threading
from http.server import ThreadingHTTPServer
from control_panel_v2 import Handler as BaseHandler
from portal_control import Control


class Handler(BaseHandler):
    def respond(self, status, payload, content_type='application/json; charset=utf-8'):
        body = json.dumps(payload).encode() if isinstance(payload, dict) else payload
        self.send_response(status)
        for name, value in [('Content-Type', content_type), ('Content-Length', str(len(body))),
                            ('Cache-Control', 'no-store'), ('X-Content-Type-Options', 'nosniff'),
                            ('X-Frame-Options', 'DENY'), ('Referrer-Policy', 'no-referrer'),
                            ('Content-Security-Policy', "default-src 'self'; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")]:
            self.send_header(name, value)
        for name, value in getattr(self, 'extra_headers', {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)

    def authenticated(self):
        return self.server.control.auth.check(self.headers.get('Cookie'))

    def do_GET(self):
        control = self.server.control
        if not self.valid_host():
            return self.respond(403, {'error': 'Host not allowed.'})
        if self.path == '/api/session':
            return self.respond(200, {'authenticated': self.authenticated(), 'csrf': control.csrf,
                                     'setupRequired': control.auth.needs_setup()})
        if self.path.startswith('/api/') and not self.authenticated():
            return self.respond(401, {'error': 'Sign in to continue.'})
        if self.path in ('/shell.js', '/shell.css'):
            name = self.path[1:]
            mime = 'text/javascript; charset=utf-8' if name.endswith('.js') else 'text/css; charset=utf-8'
            return self.respond(200, (Path(__file__).parent/'web'/name).read_bytes(), mime)
        if self.path == '/advanced.js':
            return self.respond(200, (Path(__file__).parent/'web'/'advanced.js').read_bytes(), 'text/javascript; charset=utf-8')
        if self.path == '/portal.js':
            return self.respond(200, (Path(__file__).parent/'web'/'portal.js').read_bytes(), 'text/javascript; charset=utf-8')
        if self.path == '/api/export':
            try:
                self.extra_headers = {'Content-Disposition': 'attachment; filename="nanoleaf-hue-settings.json"'}
                return self.respond(200, control.store.read())
            except (OSError, ValueError):
                return self.respond(503, {'error': 'Settings unavailable.'})
        return super().do_GET()

    def do_POST(self):
        control = self.server.control
        if (not self.valid_host() or self.headers.get('Origin') != 'http://' + self.headers.get('Host', '')
                or self.headers.get('X-Control-Token') != control.csrf
                or self.headers.get('Content-Type', '').split(';')[0] != 'application/json'):
            return self.respond(403, {'error': 'Request not allowed. Reload the page.'})
        fresh_setup = self.path == '/api/account/setup' and not control.auth.path.exists()
        if self.path != '/api/login' and not fresh_setup and not self.authenticated():
            return self.respond(401, {'error': 'Sign in to continue.'})
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 65536:
                raise ValueError('Request is too large')
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise ValueError('Invalid request')
            if self.path == '/api/login':
                token = control.auth.login(payload, self.client_address[0])
                self.extra_headers = {'Set-Cookie': 'nhb_session=' + token + '; HttpOnly; SameSite=Strict; Path=/; Max-Age=43200'}
                return self.respond(200, {'authenticated': True})
            if self.path == '/api/account/setup':
                if payload.get('password') != payload.get('confirmation'):
                    return self.respond(400, {'error': 'Passwords do not match.'})
                try:
                    control.auth.configure(payload.get('username'), payload.get('password'))
                except ValueError as error:
                    return self.respond(400, {'error': str(error)})
                token = control.auth.login(payload, self.client_address[0])
                self.extra_headers = {'Set-Cookie': 'nhb_session=' + token + '; HttpOnly; SameSite=Strict; Path=/; Max-Age=43200'}
                return self.respond(200, {'authenticated': True})
            if self.path == '/api/logout':
                control.auth.logout(self.headers.get('Cookie'))
                self.extra_headers = {'Set-Cookie': 'nhb_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0'}
                return self.respond(200, {'authenticated': False})
            actions = {'/api/mapping': control.save, '/api/brightness': control.save_brightness,
                       '/api/tuning': control.save_tuning, '/api/profile': control.profile,
                       '/api/area': control.select_area, '/api/import/preview': control.import_preview,
                       '/api/import': control.import_settings, '/api/identify': control.identify,
                       '/api/setup/hue': control.setup_hue,
                       '/api/setup/nanoleaf': control.setup_nanoleaf,
                       '/api/advanced/channels': control.save_channels,
                       '/api/advanced/mapping': control.automatic_mapping,
                       '/api/advanced/test': control.test_colors,
                       '/api/setup/discover': control.guided_discovery,
                       '/api/setup/source': control.save_source,
                       '/api/setup/desktop': control.desktop_pairing,
                       '/api/updates/check': control.check_update,
                       '/api/updates/action': control.maintenance_action,
                       '/api/refresh': lambda _: control.refresh(),
                       '/api/switch': lambda body: control.switch(body.get('on'))}
            if self.path not in actions:
                return self.respond(404, {'error': 'Resource not found.'})
            return self.respond(200, actions[self.path](payload))
        except PermissionError:
            self.respond(401, {'error': 'Invalid login credentials.'})
        except TimeoutError:
            self.respond(429, {'error': 'Too many attempts. Try again in one minute.'})
        except FileExistsError as error:
            self.respond(409, {'error': str(error)})
        except (ValueError, TypeError, KeyError):
            self.respond(400, {'error': 'Invalid settings. Check the selected area, available panels and allowed values.'})
        except Exception:
            self.respond(503, {'error': 'Operation failed. Check device connectivity.'})


def main():
    control = Control()
    control.store.read()  # Missing/invalid settings must never open an unconfigured portal.
    threading.Thread(target=control.refresh_directory, daemon=True).start()
    server = ThreadingHTTPServer((os.environ['PANEL_BIND'], 8080), Handler)
    server.control = control
    if os.environ.get('PANEL_HTTP_PORT') == '80':
        short_server = ThreadingHTTPServer((os.environ['PANEL_BIND'], 80), Handler)
        short_server.control = control
        threading.Thread(target=short_server.serve_forever, daemon=True).start()
    print('Nanoleaf Hue Bridge portal 4.1.0 ready', flush=True)
    server.serve_forever()


if __name__ == '__main__':
    main()
