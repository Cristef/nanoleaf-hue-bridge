"""Register only this virtual receiver in the 4D's native Sync+ configuration."""
import base64
import copy
import json
import os
from pathlib import Path
import struct
import time
import urllib.error
import urllib.request

STATE = Path('/var/lib/nanoleaf-hue-sync')


def api(ip, path, body=None, method=None):
    request = urllib.request.Request('http://' + ip + ':16021/' + path,
        data=None if body is None else json.dumps(body).encode(),
        headers={'Content-Type': 'application/json'}, method=method)
    with urllib.request.urlopen(request, timeout=15) as response:
        data = response.read()
        return json.loads(data) if data else None


def layout_string(layout):
    panels = layout['positionData']
    if not panels or len(panels) != layout['numPanels']:
        raise ValueError('Invalid virtual panel layout')
    records = b''.join(struct.pack('!HiiHB', p['panelId'], p['x'], p['y'], p['o'], p['shapeType']) for p in panels)
    fields = [struct.pack('!H', len(panels)), struct.pack('!H', layout['sideLength']), records]
    return base64.b64encode(b''.join(struct.pack('!BH', i, len(value)) + value
        for i, value in enumerate(fields, 1))).decode()


def updated_config(before, identity, ip, token, layout):
    if not isinstance(before, dict) or not isinstance(before.get('devices'), list):
        raise ValueError('Unsupported source configuration')
    result = copy.deepcopy(before)
    matches = [d for d in result['devices'] if d.get('deviceId') == identity]
    if len(matches) > 1:
        raise ValueError('Duplicate receiver identity')
    if matches:
        receiver = matches[0]
    else:
        box = before.get('box')
        if not isinstance(box, dict) or any(type(box.get(a)) not in (int, float) or box[a] <= 0 for a in ('x', 'y', 'z')):
            raise ValueError('Source screen dimensions are missing; calibrate the 4D in the Nanoleaf app first')
        receiver = {'deviceId': identity, 'deviceType': 1, 'modelNumber': 'NL42',
            'centroidOffset': {a: round(box[a] / 2) for a in ('x', 'y', 'z')}, 'orientation': 0}
        result['devices'].append(receiver)
    receiver.update(ipAddress=ip, authToken=token, layoutString=layout_string(layout), enabled=True)
    return result


def source_token(data, prompt):
    from portal_settings import atomic_json
    path = STATE / '4d-api-auth.json'
    if path.exists():
        saved = json.loads(path.read_text())
        if saved.get('ip') == data['source_ip']:
            try:
                info = api(data['source_ip'], 'api/v1/' + saved['token'])
                if info.get('model') == 'NL69' and info.get('serialNo') == saved['serial']:
                    return saved['token']
            except urllib.error.HTTPError as error:
                if error.code not in (401, 403):
                    raise
    prompt()
    for _ in range(300):
        try:
            token = api(data['source_ip'], 'api/v1/new', {}, 'POST')['auth_token']
            info = api(data['source_ip'], 'api/v1/' + token)
            if info.get('model') != 'NL69':
                raise ValueError('Selected source is not a Nanoleaf 4D')
            atomic_json(path, {'ip': data['source_ip'], 'serial': info['serialNo'], 'token': token})
            return token
        except urllib.error.HTTPError as error:
            if error.code not in (401, 403):
                raise
        time.sleep(1)
    raise TimeoutError('4D API pairing timed out')


def register(data, prompt):
    from portal_settings import atomic_json
    STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    token = source_token(data, prompt)
    root = 'api/v1/' + token
    def command(name, **params):
        return api(data['source_ip'], root + '/effects', {'write': {'command': name, **params}}, 'PUT')
    before = command('getOrchestratorScreenConfig')
    virtual_state = json.loads(Path('/var/lib/nanoleaf-hue-virtual/state.json').read_text())
    control = json.loads(Path('/var/lib/nanoleaf-hue-virtual/web-control-auth.json').read_text())['token']
    tokens = [t for t in virtual_state['tokens'] if t != control]
    if not tokens:
        raise ValueError('Complete Desktop pairing before registering Sync+')
    virtual_token = tokens[0]
    info = api(data['ip'], 'api/v1/' + virtual_token)
    if info['serialNo'].lower() != data['identity'].replace(':', '').lower():
        raise ValueError('Virtual identity mismatch')
    after = updated_config(before, data['identity'].upper(), data['ip'], virtual_token, info['panelLayout']['layout'])
    backup = STATE / 'syncplus-backups' / (str(time.time_ns()) + '.json')
    atomic_json(backup, before)
    # Detect another writer before changing the controller.
    if command('getOrchestratorScreenConfig') != before:
        raise RuntimeError('Sync+ changed during setup; retry')
    command('setOrchestratorScreenConfig', screenConfig=after)
    verified = command('getOrchestratorScreenConfig')
    if verified != after:
        # Never overwrite a third-party change as part of an automatic rollback.
        if verified == before:
            raise RuntimeError('4D did not retain the registration')
        raise RuntimeError('Registration verification failed; private backup retained for recovery')
    return {'panels': info['panelLayout']['layout']['numPanels'], 'backup': str(backup)}


if __name__ == '__main__':
    os.umask(0o077)
    try:
        data = json.loads(Path('/etc/nanoleaf-hue/config.json').read_text())
        result = register(data, lambda: print('Hold the physical 4D power button for five seconds now. Waiting for API pairing...', flush=True))
        print('Virtual receiver registered in Sync+; other receivers and screen dimensions preserved.', flush=True)
        print('Virtual panels:', result['panels'], flush=True)
    except Exception as error:
        print('Sync+ registration failed (' + type(error).__name__ + ((' HTTP ' + str(error.code)) if isinstance(error, urllib.error.HTTPError) else '') + '). No credentials are printed.', flush=True)
        raise SystemExit(1)
