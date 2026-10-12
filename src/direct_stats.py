"""Publish direct receiver telemetry in the portal's existing frame format."""
import json
import os
from pathlib import Path
import signal
import time
import urllib.request
from config import CONFIG


def snapshot(health, now):
    stream = health.get('syncPlus')
    stream = stream if isinstance(stream, dict) else {}
    age = stream.get('lastFrameAge')
    valid_age = type(age) in (int, float) and 0 <= age < 86400
    return {'time': now, 'source': 'direct',
            'counts': {'forwarded': stream.get('forwarded', 0),
                       'decoded': stream.get('accepted', 0), 'invalid': stream.get('invalid', 0)},
            'lastFrameTime': now-age if valid_age else None,
            'panels': [{'panelId': int(k), 'rgb': v} for k,v in stream.get('panels', {}).items()]}


def main():
    stopped = False
    def stop(*_):
        nonlocal stopped
        stopped = True
    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    target = Path(os.environ['SYNC_LATEST'])
    while not stopped:
        try:
            with urllib.request.urlopen('http://'+CONFIG['ip']+':16021/health', timeout=1) as response:
                health = json.load(response)
            value = snapshot(health, time.time())
        except (OSError, ValueError, KeyError, TypeError):
            value = snapshot({}, time.time())
        temporary = target.with_suffix('.tmp')
        temporary.write_text(json.dumps(value))
        os.chmod(temporary, 0o644)
        temporary.replace(target)
        time.sleep(0.25)


if __name__ == '__main__':
    main()
