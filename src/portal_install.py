"""Provision portal settings and environment without creating login credentials."""
import os
from pathlib import Path
from portal_settings import Store, atomic_json, validate, TUNING

STATE = Path('/var/lib/nanoleaf-hue-sync')
ENV = Path('/etc/nanoleaf-hue/portal.env')

def provision(data):
    STATE.mkdir(mode=0o700, parents=True, exist_ok=True)
    config = STATE/'portal-settings.json'
    if config.exists():
        Store(config).read()
    else:
        active = {'bridge':data['hue_ip'], 'area':data['hue_area'], 'mapping':{},
                  'brightness':{'global':100, 'channels':{}}, 'tuning':dict(TUNING)}
        atomic_json(config, validate({'schema':3,'active':active,'profiles':{'Current setup':active}}))
    values = {'PANEL_BIND':data['ip'], 'PANEL_NETWORK':data['ip']+'/'+str(data.get('prefix',24)),
              'PANEL_LOCAL_NAME':data.get('portal_name','nanoleaf-hue.local'), 'PANEL_HTTP_PORT':'80',
              'PANEL_MAPPING':str(STATE/'panel-mapping.json'), 'PANEL_CONFIG':str(config),
              'PANEL_RUNTIME':'/run/nanoleaf-hue', 'PANEL_VIRTUAL_URL':'http://'+data['ip']+':16021',
              'PANEL_HUE_IP':data['hue_ip'], 'PANEL_HUE_AREA':data['hue_area'],
              'PANEL_CONTROL_AUTH':'/var/lib/nanoleaf-hue-virtual/web-control-auth.json',
              'HUE_CREDENTIALS':str(STATE/'hue-auth.json')}
    atomic_json(STATE/'source.json',{'ip':data['source_ip']})
    ENV.parent.mkdir(parents=True,exist_ok=True)
    temporary=ENV.with_suffix('.tmp')
    temporary.write_text(''.join(key+'='+value+'\n' for key,value in values.items()))
    os.chmod(temporary,0o600)
    temporary.replace(ENV)
