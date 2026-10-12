"""Validated panel groups and hot-reloaded Hue channel mappings."""
import json
from pathlib import Path


def validate_mapping(value, channel_ids=None, panel_ids=None):
    if not isinstance(value, dict) or len(value) > 256:
        raise ValueError('Mapping must be an object')
    result = {}
    for channel, group in value.items():
        if not isinstance(channel, str) or not channel.isdecimal() or str(int(channel)) != channel:
            raise ValueError('Invalid channel identifier')
        if int(channel) > 255 or (channel_ids is not None and int(channel) not in channel_ids):
            raise ValueError('Unknown Hue channel')
        group = [group] if type(group) is int else group
        if not isinstance(group, list) or not 1 <= len(group) <= 128:
            raise ValueError('Select at least one panel, or use the general average')
        if any(type(panel) is not int or not 1 <= panel <= 65535 for panel in group):
            raise ValueError('Invalid panel identifier')
        if len(group) != len(set(group)):
            raise ValueError('Duplicate panel identifier')
        if panel_ids is not None and any(panel not in panel_ids for panel in group):
            raise ValueError('Unknown Shapes panel')
        result[channel] = sorted(group)
    return result


def channel_colors(panels, channel_ids, mapping=None):
    colors = {p['panelId']: p['rgb'] for p in panels}
    if not colors:
        raise ValueError('No colors available')
    mapping = validate_mapping(mapping or {}, set(channel_ids))
    result = []
    for channel in channel_ids:
        group = mapping.get(str(channel), list(colors))
        if any(panel not in colors for panel in group):
            raise ValueError('Mapped panel missing from current state')
        rgb = [round(sum(colors[p][i] for p in group) / len(group)) for i in range(3)]
        result.append((channel, *(value * 257 for value in rgb)))
    return result


class MappingFile:
    def __init__(self, path, channels):
        self.path = Path(path) if path else None
        self.channels = set(channels)
        self.signature = None
        self.mapping = {}
        self.error = None

    def reload(self):
        if self.path is None:
            return self.mapping
        try:
            stat = self.path.stat()
            signature = (stat.st_mtime_ns, stat.st_size)
            if signature != self.signature:
                mapping = validate_mapping(json.loads(self.path.read_text()), self.channels)
                self.mapping = mapping
                self.signature = signature
            self.error = None
        except FileNotFoundError:
            self.mapping = {}
            self.signature = None
            self.error = None
        except (OSError, ValueError):
            self.error = 'Invalid mapping file; retaining the last valid settings'
        return self.mapping
