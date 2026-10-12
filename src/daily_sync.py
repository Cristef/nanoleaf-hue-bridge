"""Always-running supervisor, gated by the virtual accessory's On state."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import urllib.request

from config import CONFIG

FOLDER = Path(__file__).resolve().parent
STATUS = Path('/run/nanoleaf-hue/status.json')


def enabled():
    with urllib.request.urlopen("http://" + CONFIG["ip"] + ":16021/health", timeout=2) as response:
        data = json.load(response)
        return data.get('on') is True


def stop_children(children):
    # Stop telemetry and Hue, releasing the Entertainment area.
    for child in reversed(children):
        if child.poll() is None:
            child.terminate()
    for child in reversed(children):
        try:
            child.wait(timeout=35)
        except subprocess.TimeoutExpired:
            child.kill(); child.wait(timeout=5)



def write_status(phase, error=None):
    STATUS.parent.mkdir(parents=True, exist_ok=True)
    temporary = STATUS.with_suffix('.tmp')
    temporary.write_text(json.dumps({'phase': phase, 'time': time.time(), 'error': error}))
    os.chmod(temporary, 0o644)
    temporary.replace(STATUS)


def main():
    stopped = False
    def stop(signum, frame):
        nonlocal stopped
        stopped = True
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    children = []; retry_at = 0; phase = None
    try:
        while not stopped:
            try:
                on = enabled()
            except Exception:
                on = False  # Fail closed if the virtual accessory is unavailable.
            if children and (not on or any(child.poll() is not None for child in children)):
                failed = on
                stop_children(children); children = []
                retry_at = time.monotonic() + (15 if failed else 0)
            if on and not children and time.monotonic() >= retry_at:
                hue = subprocess.Popen([sys.executable, str(FOLDER / 'hue_sync.py'),
                                        'stream', '--continuous', '--area',
                                        CONFIG["hue_area"]])
                children = [hue]
                # Socket startup; repeated On checks below gate the whole pipeline.
                time.sleep(2)
                if hue.poll() is None:
                    children.append(subprocess.Popen([sys.executable, str(FOLDER / 'direct_stats.py')]))
            current = 'waiting-for-colors' if children else ('retrying' if on else 'off')
            if children:
                try:
                    latest = json.loads(Path(os.environ['SYNC_LATEST']).read_text())
                    if time.time() - (latest.get('lastFrameTime') or 0) < 3:
                        current = 'receiving'
                        hue_state = json.loads(Path(os.environ['HUE_STATUS']).read_text())
                        if hue_state['phase'] == 'streaming' and time.time() - hue_state['time'] < 3:
                            current = 'streaming'
                except (OSError, KeyError, ValueError):
                    pass
            write_status(current)
            if current != phase:
                print('Sync state:', current, flush=True); phase = current
            time.sleep(0.5)
    finally:
        if children:
            stop_children(children)
        write_status('stopped')


if __name__ == '__main__':
    main()
