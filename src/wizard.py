"""Interactive Debian setup and maintenance. Never resets pairing identities."""
import asyncio
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import socket
import subprocess
import sys
import time
import urllib.request

from config import PATH, validate

ROOT = Path('/opt/nanoleaf-hue')
VIRTUAL = 'nanoleaf-hue-virtual'
SYNC = 'nanoleaf-hue-sync'
PANEL = 'nanoleaf-hue-panel'
AUTH = Path('/var/lib/nanoleaf-hue-sync/hue-auth.json')
SETUP = Path('/var/lib/nanoleaf-hue-virtual/homekit-setup.json')


def ask(label, default=''):
    # Buffered update mode requires seeking, which terminals do not support.
    with open('/dev/tty', 'w') as output, open('/dev/tty', 'r') as input_stream:
        output.write(label + (f' [{default}]' if default else '') + ': ')
        output.flush()
        answer = input_stream.readline()
        if not answer:
            raise KeyboardInterrupt
        return answer.strip() or default


def choose(label, options):
    if not options:
        raise ValueError('No options available: ' + label)
    print('\n' + label)
    for i, (description, value) in enumerate(options, 1):
        print(f'  {i}. {description}')
    while True:
        answer = ask('Number', '1')
        if answer.isdigit() and 1 <= int(answer) <= len(options):
            return options[int(answer)-1][1]
        print('Select a number from the list.')


def command(*args):
    subprocess.run(args, check=True)


def address(label, default=''):
    while True:
        try:
            value = str(ipaddress.IPv4Address(ask(label, default)))
            ip = ipaddress.IPv4Address(value)
            if ip.is_multicast or ip.is_unspecified or ip.is_loopback:
                raise ValueError
            return value
        except ValueError:
            print('Enter a valid device IPv4 address.')


def discover():
    try:
        result = subprocess.run(['avahi-browse', '-rtp', '_nanoleafapi._tcp'],
                                capture_output=True, text=True, timeout=10)
        devices = []
        for line in result.stdout.splitlines():
            fields = line.split(';')
            if len(fields) >= 10 and fields[0] == '=' and fields[2] == 'IPv4':
                model = re.search(r'md=(NL\d+)', fields[9])
                item = (fields[3], fields[7], model.group(1) if model else '')
                if item not in devices:
                    devices.append(item)
        return devices
    except (OSError, subprocess.TimeoutExpired):
        return []


def device(label, devices, model):
    options = [(f'{name} ({ip}, {kind})', ip) for name, ip, kind in devices if kind == model]
    options.append(('Enter IP address manually', None))
    picked = choose(label, options)
    return picked or address(label + ' - IP')


def neighbor(ip, interface):
    subprocess.run(['ping', '-c', '1', '-W', '2', ip], stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL, check=False)
    values = json.loads(subprocess.check_output(['ip', '-j', 'neigh', 'show', 'to', ip,
                                                'dev', interface]))
    detected = next((v['lladdr'] for v in values if 'lladdr' in v), '')
    while True:
        value = ask('Physical MAC address of ' + ip, detected).lower()
        if not re.fullmatch(r'(?:[0-9a-f]{2}:){5}[0-9a-f]{2}', value) or int(value[:2], 16) & 1:
            print('Enter a unicast MAC address in AA:BB:CC:DD:EE:FF format.'); continue
        if detected and value != detected.lower():
            print('The MAC address does not match the detected address. Check the device.'); continue
        return value


def save(data):
    validate(data)
    PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = PATH.with_suffix('.tmp')
    temporary.write_text(json.dumps(data, indent=2) + '\n')
    os.chmod(temporary, 0o644)
    temporary.replace(PATH)


def health(data):
    with urllib.request.urlopen('http://' + data['ip'] + ':16021/health', timeout=3) as response:
        return json.load(response)


def wait_virtual(data):
    for _ in range(30):
        try:
            if health(data).get('status') == 'ok': return
        except (OSError, ValueError): pass
        time.sleep(1)
    raise RuntimeError('Virtual receiver did not start. Inspect Diagnostics.')


def desktop_pairing(data, force=False):
    wait_virtual(data)
    if not force and health(data).get('pairing', {}).get('apiPaired'):
        print('An API client is already paired; existing tokens are preserved.')
        return
    while True:
        auth = json.loads(Path('/var/lib/nanoleaf-hue-virtual/web-control-auth.json').read_text())
        request = urllib.request.Request('http://'+data['ip']+':16021/api/v1/'+auth['token']+'/pairing',
            data=b'{}', headers={'Content-Type':'application/json'}, method='POST')
        with urllib.request.urlopen(request, timeout=3) as response:
            assert response.status == 200
        print('Pairing open for two minutes. Open Nanoleaf Desktop on the same LAN.')
        print('Add '+data['name']+' using power-button pairing. The virtual button has already been pressed.')
        print('iPhone and HomeKit pairing are not supported.')
        ask('Press Enter after pairing, or to finish pairing later in the web portal')
        if health(data).get('pairing', {}).get('apiPaired'):
            print('API pairing verified. Configure this virtual device in the 4D Sync+ settings in Desktop.')
            return
        if choose('No API pairing detected', [('Finish later in the portal', 'later'), ('Open another pairing window', 'retry')]) == 'later':
            return


async def hue(data):
    from hue_entertainment import HueEntertainmentAPI
    AUTH.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not AUTH.exists():
        ask('Press the Hue Bridge button, then press Enter')
        api = HueEntertainmentAPI(data['hue_ip'])
        try:
            credentials = await asyncio.wait_for(api.pair('nanoleaf_hue#bridge'), 120)
        finally:
            await api.close()
        fd = os.open(AUTH, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as out:
            json.dump(credentials, out)
    credentials = json.loads(AUTH.read_text())
    api = HueEntertainmentAPI(data['hue_ip'], credentials['username'])
    try:
        areas = await api.get_entertainment_areas()
    finally:
        await api.close()
    if not areas:
        print('Create an Entertainment area in the Hue app -> Settings -> Entertainment areas.')
        ask('Press Enter after creating the area')
        return await hue(data)
    data['hue_area'] = choose('Hue Entertainment area to synchronize',
                             [(f'{a.name} ({len(a.channels)} channels)', a.id) for a in areas])
    save(data)


def setup():
    if PATH.exists():
        data = validate(json.loads(PATH.read_text()))
        print('Resuming the existing configuration; pairings are preserved.')
    else:
        print('Required: a Nanoleaf 4D and Nanoleaf Desktop on the container LAN. Physical Shapes are not required.')
        print('Direct UDP receiver: no ARP changes. iPhone/HomeKit pairing is not supported.')
        if ask('Continue? [y/N]', 'n').lower() != 'y':
            return
        addresses = json.loads(subprocess.check_output(['ip', '-j', '-4', 'addr', 'show']))
        options = []
        for interface in addresses:
            for info in interface.get('addr_info', []):
                if info.get('scope') == 'global':
                    options.append((f'{interface["ifname"]}: {info["local"]}/{info["prefixlen"]}',
                                    (interface['ifname'], info['local'], info['prefixlen'])))
        interface, ip, prefix = choose('Interface connected to the Nanoleaf LAN', options)
        devices = discover()
        source = device('Nanoleaf 4D source', devices, 'NL69')
        network = ipaddress.IPv4Network(f'{ip}/{prefix}', strict=False)
        if any(ipaddress.IPv4Address(v) not in network for v in (source,)):
            raise ValueError('The 4D must be on the same LAN/interface as the container.')
        data = {'interface': interface, 'ip': ip, 'prefix': prefix, 'source_ip': source, 'mode': 'direct',
                'hue_ip': address('Hue Bridge IP address'),
                'name': ask('Virtual light name', 'Shapes Hue Bridge'),
                'identity': '02:' + ':'.join(f'{x:02x}' for x in secrets.token_bytes(5)),
                'hue_area': '00000000-0000-0000-0000-000000000000'}
        save(data)
    for unit in (VIRTUAL, SYNC, PANEL):
        shutil.copyfile(ROOT / 'systemd' / (unit + '.service'),
                        '/etc/systemd/system/' + unit + '.service')
    command('systemctl', 'daemon-reload')
    command('systemctl', 'enable', '--now', VIRTUAL)
    desktop_pairing(data)
    asyncio.run(hue(data))
    from portal_install import provision
    provision(data)
    command('systemctl', 'enable', '--now', SYNC, PANEL)
    print('\nInstallation complete. Turn on/off ' + data['name'] + ' in the web portal or Nanoleaf Desktop.')
    print('Keep the virtual device selected in 4D Sync+ in Desktop and enable Start at boot for the LXC in Proxmox.')
    print('Portal: http://' + data['ip'] + ':8080  -  create your username and password there.')
    print('Map panel colors, adjust brightness and save profiles in the portal. Maintenance menu: nanoleaf-hue')


def menu():
    while True:
        choice = choose('Nanoleaf Hue Bridge', [
            ('Status', 'status'), ('Diagnostics', 'logs'), ('Change Hue area', 'area'),
            ('Pair with Nanoleaf Desktop', 'pair'), ('Complete setup', 'setup'),
            ('Restart services', 'restart'), ('Deactivate services', 'remove'), ('Exit', 'exit')])
        if choice == 'exit': return
        if choice == 'setup': setup(); continue
        if choice == 'status':
            subprocess.run(['systemctl', '--no-pager', 'status', VIRTUAL, SYNC, PANEL], check=False)
            status = Path('/run/nanoleaf-hue/status.json')
            if status.exists(): print(status.read_text())
        elif choice == 'logs':
            command('journalctl', '-u', SYNC, '-u', VIRTUAL, '-u', PANEL, '-n', '50', '--no-pager')
        elif choice == 'pair':
            desktop_pairing(json.loads(PATH.read_text()), force=True)
        elif choice == 'area':
            data = json.loads(PATH.read_text())
            command('systemctl', 'stop', SYNC)
            asyncio.run(hue(data))
            from portal_install import provision
            from portal_settings import Store, revision
            store=Store(AUTH.parent/'portal-settings.json')
            def change(config):
                config['active']['bridge']=data['hue_ip'];config['active']['area']=data['hue_area']
                config['active']['mapping']={};config['active']['brightness']['channels']={}
                return config
            store.update(revision(store.read()),change)
            provision(data)
            command('systemctl', 'restart', PANEL)
            command('systemctl', 'start', SYNC)
        elif choice == 'restart':
            command('systemctl', 'stop', SYNC)
            command('systemctl', 'restart', VIRTUAL, PANEL)
            command('systemctl', 'start', SYNC)
        elif choice == 'remove':
            if ask('Deactivate services? [y/N]', 'n').lower() == 'y':
                command('systemctl', 'disable', '--now', PANEL, SYNC, VIRTUAL)
                print('Services deactivated; configuration and pairings are preserved.')


if __name__ == '__main__':
    if os.geteuid() != 0:
        sys.exit('Run the menu as root inside the container.')
    os.umask(0o077)
    try:
        setup() if len(sys.argv) > 1 and sys.argv[1] == 'setup' else menu()
    except (KeyboardInterrupt, EOFError):
        sys.exit('\nSetup interrupted. Resume from nanoleaf-hue -> Complete setup.')
    except Exception as error:
        # Do not echo library exceptions: a Hue pairing response may contain keys.
        sys.exit('Operation failed (' + type(error).__name__ + '). '
                 'Check IP addresses, connectivity, the Hue Bridge button, and diagnostics; resume from the menu.')
