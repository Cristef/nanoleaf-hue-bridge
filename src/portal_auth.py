"""Local username/password login with hashed credentials, expiring cookies and throttling."""
import hashlib
import hmac
from http.cookies import SimpleCookie, CookieError
import json
from pathlib import Path
import secrets
import threading
import time
from portal_settings import atomic_json


class Auth:
    def __init__(self, path):
        self.path = Path(path)
        self.sessions = {}
        self.failures = {}
        self.lock = threading.RLock()

    @staticmethod
    def digest(secret, salt):
        return hashlib.pbkdf2_hmac('sha256', secret.encode(), bytes.fromhex(salt), 600000).hex()

    def login(self, secret, address):
        with self.lock:
            now = time.monotonic()
            self.failures = {k: v for k, v in self.failures.items() if now - v['time'] < 60}
            failures = self.failures.get(address, {'count': 0, 'time': now})
            if failures['count'] >= 5 or len(self.failures) >= 256:
                raise TimeoutError('Too many attempts. Try again in one minute.')
            record = json.loads(self.path.read_text()) if self.path.exists() else {}
            username = None
            if isinstance(secret, dict):
                username, secret = secret.get('username'), secret.get('password')
            valid = 'username' in record and isinstance(secret, str) and len(secret) <= 256 and hmac.compare_digest(
                self.digest(secret, record['salt']), record['hash'])
            if 'username' in record:
                valid = valid and isinstance(username, str) and hmac.compare_digest(username, record['username'])
            if not valid:
                failures['count'] += 1
                self.failures[address] = failures
                raise PermissionError('Invalid login credentials')
            self.failures.pop(address, None)
            token = secrets.token_urlsafe(32)
            self.sessions = {k: v for k, v in self.sessions.items() if v > time.monotonic()}
            if len(self.sessions) >= 128:
                self.sessions.pop(next(iter(self.sessions)))
            self.sessions[hashlib.sha256(token.encode()).hexdigest()] = time.monotonic() + 43200
            return token

    def needs_setup(self):
        return not self.path.exists() or 'username' not in json.loads(self.path.read_text())

    def configure(self, username, password):
        with self.lock:
            if not self.needs_setup():
                raise FileExistsError('Login is already configured.')
            if not isinstance(username, str) or not 1 <= len(username) <= 64 or not all(c.isascii() and (c.isalnum() or c in '._-') for c in username):
                raise ValueError('Use 1–64 letters, numbers, dots, underscores or hyphens for the username.')
            if not isinstance(password, str) or not 8 <= len(password) <= 256:
                raise ValueError('Use a password between 8 and 256 characters.')
            salt = secrets.token_hex(16)
            atomic_json(self.path, {'username': username, 'salt': salt, 'hash': self.digest(password, salt)})
            self.sessions.clear()
            self.failures.clear()

    def session_key(self, header):
        try:
            if len(header or '') > 4096:
                return None
            cookie = SimpleCookie()
            cookie.load(header or '')
            token = cookie['nhb_session'].value
            return hashlib.sha256(token.encode()).hexdigest()
        except (KeyError, ValueError, CookieError):
            return None

    def check(self, header):
        with self.lock:
            return self.sessions.get(self.session_key(header), 0) > time.monotonic()

    def logout(self, header):
        with self.lock:
            self.sessions.pop(self.session_key(header), None)
