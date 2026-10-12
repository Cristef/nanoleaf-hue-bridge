"""Atomic, credential-free settings for the version 3 portal and Hue consumer."""
import copy
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import threading
import uuid
from brightness import validate as brightness
from panel_mapping import validate_mapping

TUNING = {'smoothingMs': 0, 'saturation': 100, 'blackThreshold': 0}


def private_ip(value):
    if not isinstance(value, str):
        raise ValueError('Invalid IPv4 address')
    address = ipaddress.IPv4Address(value)
    if not address.is_private or address.is_loopback or address.is_link_local or address.is_multicast or address.is_unspecified:
        raise ValueError('Use a private LAN IPv4 address')
    return str(address)


def tuning(value):
    if not isinstance(value, dict) or set(value) != set(TUNING):
        raise ValueError('Invalid color response settings')
    for key, limit in [('smoothingMs', 2000), ('saturation', 200), ('blackThreshold', 255)]:
        if type(value[key]) is not int or not 0 <= value[key] <= limit:
            raise ValueError('Color response outside allowed range')
    return dict(value)


def active(value):
    if not isinstance(value, dict) or (set(value) - {'channelSettings'}) != {'bridge', 'area', 'mapping', 'brightness', 'tuning'}:
        raise ValueError('Invalid stream settings')
    if not isinstance(value['area'], str):
        raise ValueError('Invalid area identifier')
    area = str(uuid.UUID(value['area']))
    result = {'bridge': private_ip(value['bridge']), 'area': area,
            'mapping': validate_mapping(value['mapping']), 'brightness': brightness(value['brightness']),
            'tuning': tuning(value['tuning'])}
    if 'channelSettings' in value:
        from advanced_portal import channel_settings
        result['channelSettings'] = channel_settings(value['channelSettings'])
    return result


def profile_name(value):
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= 40 or any(ord(c) < 32 for c in value):
        raise ValueError('Use a profile name of 1 to 40 characters')
    return value.strip()


def validate(value):
    if not isinstance(value, dict) or set(value) != {'schema', 'active', 'profiles'} or value['schema'] != 3:
        raise ValueError('Unsupported settings file; expected schema 3')
    if not isinstance(value['profiles'], dict) or len(value['profiles']) > 32:
        raise ValueError('At most 32 profiles are allowed')
    profiles = {}
    for name, settings in value['profiles'].items():
        normalized = profile_name(name)
        if normalized in profiles:
            raise ValueError('Duplicate profile name')
        profiles[normalized] = active(settings)
    result = {'schema': 3, 'active': active(value['active']), 'profiles': profiles}
    if len(json.dumps(result).encode()) > 65536:
        raise ValueError('Settings exceed 64 KiB')
    return result


def revision(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    with temporary.open('w', encoding='utf-8') as out:
        json.dump(value, out, indent=2)
        out.write('\n')
        out.flush()
        os.fsync(out.fileno())
    os.chmod(temporary, 0o600)
    temporary.replace(path)


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.lock = threading.RLock()
        self.last = None
        self.error = None

    def read(self, retain=False):
        with self.lock:
            try:
                value = validate(json.loads(self.path.read_text(encoding='utf-8')))
                self.last = value
                self.error = None
            except (OSError, ValueError, TypeError, KeyError):
                self.error = 'Invalid portal settings; keeping the last valid configuration'
                if not retain or self.last is None:
                    raise ValueError(self.error) from None
            return copy.deepcopy(self.last)

    def update(self, expected, transform):
        with self.lock:
            value = self.read()
            if expected != revision(value):
                raise FileExistsError('Settings changed in another window. Reload before saving.')
            transform(value)
            value = validate(value)
            atomic_json(self.path, value)
            self.last = value
            return copy.deepcopy(value)
