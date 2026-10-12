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

from config import CONFIG
from extcontrol_probe import decode_frame
from panel_mapping import channel_colors, MappingFile
from brightness import BrightnessFile, scale
from portal_settings import Store, TUNING
from color_response import ColorResponse


def publish(phase, count=0, mapping_error=None, commands=None):
    path = os.environ.get('HUE_STATUS')
    if path:
        target = Path(path); temporary = target.with_suffix('.tmp')
        temporary.write_text(json.dumps({'phase': phase, 'time': time.time(), 'frames': count,
                                         'mappingError': mapping_error,
                                         'colors': {str(ch): [r//257, g//257, b//257]
                                                    for ch, r, g, b in (commands or [])}}))
        os.chmod(temporary, 0o644)
        temporary.replace(target)


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
                    creds = await asyncio.wait_for(api.pair('nanoleaf_sync#lxc110'), remaining)
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
    store = Store(args.config) if args.config else None
    config = store.read()['active'] if store else None
    async def connect(current):
        bridge = current['bridge'] if current else args.bridge
        path = credentials_path if bridge == args.bridge else credentials_path.parent/'hue-pairings'/(bridge+'.json')
        creds = json.loads(path.read_text())
        session = EntertainmentSession(bridge, creds['username'], creds['clientkey'])
        try:
            areas = await session.get_entertainment_areas()
            area_id = current['area'] if current else args.area
            area = next((a for a in areas if a.id == area_id), None) if area_id else (areas[0] if len(areas) == 1 else None)
            if area is None or not area.channels:
                raise ValueError('Select an available entertainment area')
            return session, area, areas
        except Exception:
            await session.aclose()
            raise
    session, area, areas = await connect(config)
    publish('waiting')
    try:
        if args.command == 'areas':
            print(json.dumps([{'id': a.id, 'name': a.name, 'channels': [ch.channel_id for ch in a.channels]} for a in areas]))
            return
        ids = [ch.channel_id for ch in area.channels]
        mapping_file = MappingFile(args.mapping, ids)
        mapping = config['mapping'] if config else mapping_file.reload()
        settings_path = args.brightness or (str(Path(args.mapping).with_name('brightness.json')) if args.mapping else None)
        brightness_file = BrightnessFile(settings_path, ids)
        brightness = config['brightness'] if config else brightness_file.reload()
        response = ColorResponse()
        next_mapping_check = 0
        loop = asyncio.get_running_loop()
        stop = asyncio.Event()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, stop.set)
        state = {}; count = 0; started = False; last_frame = 0; next_status = 0
        test_active = False
        from test_patterns import commands as test_commands
        test_path = Path(os.environ.get("HUE_TEST", "/run/nanoleaf-hue/test-mode.json"))
        identify = {}
        identify_path = Path(os.environ.get('HUE_IDENTIFY', '/run/nanoleaf-hue/identify.json'))
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as receiver:
            receiver.bind(('127.0.0.1', args.listen_port)); receiver.setblocking(False)
            deadline = float('inf') if args.continuous else time.monotonic() + args.seconds
            print('Hue consumer ready; waiting for actual colors', flush=True)
            while not stop.is_set() and time.monotonic() < deadline:
                try: test = json.loads(test_path.read_text())
                except (OSError,ValueError): test = {}
                testing = test_commands(test,ids,time.time(),area.id)
                if test_active and testing is None:
                    if started: await session.stop(); started=False
                    state={};response=ColorResponse()
                test_active = testing is not None
                panels=[]
                try:
                    data, peer = await asyncio.wait_for(loop.sock_recvfrom(receiver,65535),0.05 if test_active else 0.5)
                    try: panels=decode_frame(data)
                    except ValueError: pass
                except asyncio.TimeoutError:
                    pass
                if not panels and not test_active:
                    if started and time.monotonic()-last_frame>2:
                        await session.stop();started=False;response=ColorResponse();publish('waiting',count)
                    continue
                for panel in panels:
                    state[panel['panelId']] = panel
                if time.monotonic() >= next_mapping_check:
                    if store:
                        updated = store.read(retain=True)['active']
                        if (updated['bridge'], updated['area']) != (config['bridge'], config['area']):
                            if started:
                                await session.stop()
                            await session.aclose()
                            started = False
                            session, area, areas = await connect(updated)
                            ids = [ch.channel_id for ch in area.channels]
                            response = ColorResponse()
                        config = updated
                        mapping, brightness = config['mapping'], config['brightness']
                    else:
                        mapping, brightness = mapping_file.reload(), brightness_file.reload()
                    try:
                        identify = json.loads(identify_path.read_text())
                    except (OSError, ValueError):
                        identify = {}
                    next_mapping_check = time.monotonic() + 0.5
                mapping_error = store.error if store else (mapping_file.error or brightness_file.error)
                if testing is not None and not state:
                    state[1]={'panelId':1,'rgb':[255,0,0]}
                commands = []
                for channel in ids:
                    selected = {str(channel): mapping[str(channel)]} if str(channel) in mapping else {}
                    try:
                        commands.extend(channel_colors(list(state.values()), [channel], selected))
                    except ValueError:
                        commands.extend(channel_colors(list(state.values()), [channel]))
                        mapping_error = 'Selected panel unavailable; using the general average'
                if testing is not None: commands = testing
                commands = response.process(commands, config['tuning'] if config else TUNING, brightness, time.monotonic(), config.get('channelSettings',{}) if config else None)
                if (identify.get('area') == area.id and type(identify.get('expires')) in (int, float)
                        and 0 < identify['expires'] - time.time() <= 2):
                    white = {ch: (r,g,b) for ch,r,g,b in scale([(ch,65535,65535,65535) for ch in ids], brightness)}
                    commands = [(ch, *(white[ch] if ch == identify.get('channel') else (r, g, b)))
                                for ch, r, g, b in commands]
                if not started:
                    publish('connecting', count)
                    try: await session.start(area.id, stop_others=False)
                    except Exception as error:
                        reason=str(error).lower()
                        publish('busy' if any(word in reason for word in ('active','busy','in use','streaming')) else 'connection-error',count)
                        await asyncio.sleep(1)
                        continue
                    started = True
                if stop.is_set():
                    break
                session.send([LightColorCommand(channel_id=ch, red=r, green=g, blue=b) for ch, r, g, b in commands])
                count += 1; last_frame = time.monotonic()
                if last_frame >= next_status:
                    publish('streaming', count, mapping_error, commands); next_status = last_frame + 1
            print(json.dumps({'hueFramesSent': count}), flush=True)
    finally:
        await session.aclose()
        publish('stopped')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('pair', 'areas', 'stream'))
    parser.add_argument('--bridge', default=CONFIG['hue_ip'])
    parser.add_argument('--credentials', default=os.environ.get('HUE_CREDENTIALS', '/var/lib/nanoleaf-hue-sync/hue-auth.json'))
    parser.add_argument('--area')
    parser.add_argument('--config', default=os.environ.get('HUE_CONFIG'))
    parser.add_argument('--listen-port', type=int, default=60223)
    parser.add_argument('--mapping', default=os.environ.get('HUE_MAPPING'))
    parser.add_argument('--brightness', default=os.environ.get('HUE_BRIGHTNESS'))
    parser.add_argument('--seconds', type=int, default=60)
    parser.add_argument('--continuous', action='store_true')
    args = parser.parse_args()
    if not 1 <= args.listen_port <= 65535:
        parser.error('listen port must be 1..65535')
    if not 1 <= args.seconds <= 3600:
        parser.error('duration must be 1..3600 seconds')
    os.umask(0o077)
    try:
        asyncio.run(run(args))
    except TimeoutError:
        parser.exit(1, 'Hue pairing/connection timed out; no successful connection confirmed.\n')


if __name__ == '__main__':
    main()
