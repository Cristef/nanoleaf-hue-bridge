"""Persistent stream brightness. Invalid updates retain the last valid values."""
import json
from pathlib import Path

DEFAULT = {'global': 100, 'channels': {}}


def validate(value, channels=None):
    if not isinstance(value, dict) or set(value) != {'global', 'channels'}:
        raise ValueError('Invalid brightness settings')
    def percent(number):
        if type(number) is not int or not 0 <= number <= 100:
            raise ValueError('Brightness must be an integer from 0 to 100')
        return number
    groups = value['channels']
    if not isinstance(groups, dict) or len(groups) > 256:
        raise ValueError('Invalid brightness channels')
    result = {}
    for key, number in groups.items():
        if (not isinstance(key, str) or not key.isdecimal() or str(int(key)) != key
                or int(key) > 255 or (channels is not None and int(key) not in channels)):
            raise ValueError('Unknown brightness channel')
        result[key] = percent(number)
    return {'global': percent(value['global']), 'channels': result}


def scale(commands, settings):
    settings = validate(settings)
    return [(channel, *(round(component * settings['global'] *
            settings['channels'].get(str(channel), 100) / 10000) for component in (r, g, b)))
            for channel, r, g, b in commands]


class BrightnessFile:
    def __init__(self, path, channels):
        self.path = Path(path) if path else None
        self.channels = set(channels)
        self.settings = {'global': 100, 'channels': {}}
        self.error = None

    def reload(self):
        try:
            if self.path is not None:
                self.settings = validate(json.loads(self.path.read_text()), self.channels)
            self.error = None
        except FileNotFoundError:
            self.settings = {'global': 100, 'channels': {}}
            self.error = None
        except (OSError, ValueError):
            self.error = 'Invalid brightness file; retaining the last valid settings'
        return self.settings
