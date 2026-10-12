"""Deployment settings, never device credentials or HomeKit keys."""
import ipaddress
import json
import os
from pathlib import Path
import re
import uuid

PATH = Path(os.environ.get('NH_CONFIG', '/etc/nanoleaf-hue/config.json'))


def validate(data):
    for key in ('ip', 'source_ip', 'target_ip', 'hue_ip'):
        address = ipaddress.IPv4Address(data[key])
        if address.is_multicast or address.is_unspecified or address.is_loopback:
            raise ValueError('invalid device address: ' + key)
    if len({data[k] for k in ('ip', 'source_ip', 'target_ip', 'hue_ip')}) != 4:
        raise ValueError('device addresses must be distinct')
    for key in ('identity', 'source_mac', 'target_mac'):
        value = data[key].lower()
        if not re.fullmatch(r'(?:[0-9a-f]{2}:){5}[0-9a-f]{2}', value):
            raise ValueError('invalid MAC: ' + key)
        if int(value[:2], 16) & 1 or value == '00:00:00:00:00:00':
            raise ValueError('MAC must be unicast and nonzero')
        data[key] = value
    if len({data[k] for k in ('identity', 'source_mac', 'target_mac')}) != 3:
        raise ValueError('MAC identities must be distinct')
    if not re.fullmatch(r'[a-zA-Z0-9_.:-]{1,15}', data['interface']):
        raise ValueError('invalid interface')
    if not isinstance(data['name'], str) or not 1 <= len(data['name']) <= 48 or any(ord(c) < 32 for c in data['name']):
        raise ValueError('invalid accessory name')
    if type(data.get('prefix',24)) is not int or not 1 <= data.get('prefix',24) <= 30:
        raise ValueError('invalid LAN prefix')
    uuid.UUID(data['hue_area'])
    return data


CONFIG = validate(json.loads(PATH.read_text())) if PATH.exists() else {}
