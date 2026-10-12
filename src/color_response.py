"""Time-based smoothing and HSV saturation applied to Hue RGB commands."""
import colorsys
import math
from brightness import scale
from portal_settings import tuning


class ColorResponse:
    def __init__(self):
        self.previous = {}
        self.time = None

    def process(self, commands, settings, levels, now):
        settings = tuning(settings)
        adjusted = []
        for channel, r, g, b in commands:
            if max(r, g, b) / 257 < settings['blackThreshold']:
                rgb = (0, 0, 0)
            elif settings['saturation'] == 100:
                rgb = (r, g, b)
            else:
                h, s, v = colorsys.rgb_to_hsv(r / 65535, g / 65535, b / 65535)
                rgb = tuple(round(c * 65535) for c in colorsys.hsv_to_rgb(h, min(1, s * settings['saturation'] / 100), v))
            adjusted.append((channel, *rgb))
        adjusted = scale(adjusted, levels)
        dt = max(0, now - self.time) if self.time is not None else 0
        tau = settings['smoothingMs'] / 1000
        alpha = 1 - math.exp(-dt / tau) if tau else 1
        result = []
        for channel, *rgb in adjusted:
            old = self.previous.get(channel)
            if old is not None and any(rgb) and tau:
                rgb = [old[i] + alpha * (rgb[i] - old[i]) for i in range(3)]
            self.previous[channel] = rgb
            result.append((channel, *(round(c) for c in rgb)))
        self.time = now
        return result
