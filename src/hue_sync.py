"""Hue Entertainment consumer for copied Nanoleaf extControl v2 frames.

Credentials stay in a private file. No REST RGB updates. Default mapping is mean
RGB across known panels; optional JSON maps Hue channel IDs to Nanoleaf panel IDs.
"""
import argparse
import asyncio
import json
import os
from pathlib import Path
import signal
import socket
import time

from extcontrol_probe import decode_frame
from config import CONFIG


def publish(phase, count=0):
    path = os.environ.get('HUE_STATUS')
    if path:
        target = Path(path); temporary = target.with_suffix('.tmp')
        temporary.write_text(json.dumps({'phase': phase, 'time': time.time(), 'frames': count}))
        os.chmod(temporary, 0o644)
        temporary.replace(target)


def channel_colors(panels, channel_ids, mapping=None):
    colors = {p['panelId']: p['rgb'] for p in panels}
    if not colors:
        raise ValueError('no colors available')
    average = [round(sum(rgb[i] for rgb in colors.values()) / len(colors)) for i in range(3)]
    mapping = mapping or {}
    result = []
    for channel in channel_ids:
        panel = mapping.get(str(channel))
        if panel is not None and panel not in colors:
            raise ValueError('mapped panel missing from current state')
        rgb = average if panel is None else colors[panel]
        result.append((channel, *(value * 257 for value in rgb)))
    return result


async def run(args):
    from hue_entertainment import EntertainmentSession, HueEntertainmentAPI, LightColorCommand
    credentials_path = Path(args.credentials)
    if args.command == 'pair':
        if credentials_path.exists():
            print('Credentials already exist; retaining current pairing', flush=True)
            return
        api = HueEntertainmentAPI(args.bridge)
        try:
            deadline = time.monotonic() + 180
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError('bridge button not pressed within pairing window')
                try:
                    creds = await asyncio.wait_for(api.pair('nanoleaf_hue#bridge'), remaining)
                    break
                except TimeoutError:
                    if time.monotonic() >= deadline:
                        raise
            credentials_path.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(credentials_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, 'w') as out:
                json.dump(creds, out)
            print('Hue pairing completed; credentials saved privately', flush=True)
        finally:
            await api.close()
        return
    creds = json.loads(credentials_path.read_text())
    session = EntertainmentSession(args.bridge, creds['username'], creds['clientkey'])
    publish('waiting')
    try:
        areas = await session.get_entertainment_areas()
        if args.command == 'areas':
            print(json.dumps([{'id': a.id, 'name': a.name,
                               'channels': [ch.channel_id for ch in a.channels]} for a in areas]))
            return
        area = next((a for a in areas if a.id == args.area), None) if args.area else (
            areas[0] if len(areas) == 1 else None)
        if area is None:
            raise ValueError('select one existing entertainment area with --area; use areas command')
        mapping = json.loads(Path(args.mapping).read_text()) if args.mapping else {}
        ids = [ch.channel_id for ch in area.channels]
        if not ids or set(mapping) - {str(ch) for ch in ids}:
            raise ValueError('invalid or empty channel mapping')
        loop = asyncio.get_running_loop()
        stop = asyncio.Event()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, stop.set)
        state = {}; count = 0; started = False; last_frame = 0; next_status = 0
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as receiver:
            receiver.bind(('127.0.0.1', 60223)); receiver.setblocking(False)
            deadline = float('inf') if args.continuous else time.monotonic() + args.seconds
            print('Hue consumer ready on loopback UDP60223; waiting for actual colors', flush=True)
            while not stop.is_set() and time.monotonic() < deadline:
                try:
                    data, peer = await asyncio.wait_for(loop.sock_recvfrom(receiver, 65535), 0.5)
                except asyncio.TimeoutError:
                    if started and time.monotonic() - last_frame > 2:
                        await session.stop(); started = False
                        publish('waiting', count)
                    continue
                try:
                    panels = decode_frame(data)
                except ValueError:
                    continue
                for panel in panels:
                    state[panel['panelId']] = panel
                commands = channel_colors(list(state.values()), ids, mapping)
                if not started:
                    publish('connecting', count)
                    await session.start(area.id, stop_others=False)
                    started = True
                if stop.is_set():
                    break
                session.send([LightColorCommand(channel_id=ch, red=r, green=g, blue=b)
                              for ch, r, g, b in commands])
                count += 1; last_frame = time.monotonic()
                if last_frame >= next_status:
                    publish('streaming', count); next_status = last_frame + 1
            print(json.dumps({'hueFramesSent': count}), flush=True)
    finally:
        await session.aclose()
        publish('stopped')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('pair', 'areas', 'stream'))
    parser.add_argument('--bridge', default=CONFIG["hue_ip"])
    parser.add_argument('--credentials', default=os.environ.get('HUE_CREDENTIALS', '/var/lib/nanoleaf-hue-sync/hue-auth.json'))
    parser.add_argument('--area')
    parser.add_argument('--mapping')
    parser.add_argument('--seconds', type=int, default=60)
    parser.add_argument('--continuous', action='store_true')
    args = parser.parse_args()
    if not 1 <= args.seconds <= 3600:
        parser.error('duration must be 1..3600 seconds')
    os.umask(0o077)
    try:
        asyncio.run(run(args))
    except TimeoutError:
        parser.exit(1, 'Hue pairing/connection timed out; no successful connection confirmed.\n')


if __name__ == '__main__':
    main()
