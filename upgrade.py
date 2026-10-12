"""Upgrade a public installer deployment, retaining identities and private settings."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import urllib.request

SOURCE=Path(__file__).resolve().parent
ROOT=Path('/opt/nanoleaf-hue')
UNITS=('nanoleaf-hue-virtual','nanoleaf-hue-sync','nanoleaf-hue-panel','nanoleaf-hue-maintenance','nanoleaf-hue-name')

def run(*args):
    subprocess.run(args,check=True)

def main():
    if os.geteuid()!=0: raise RuntimeError('Run as root.')
    if not Path('/etc/nanoleaf-hue/config.json').exists():
        raise RuntimeError('No supported public installer deployment found.')
    os.umask(0o077)
    backup=Path('/root/nanoleaf-hue-backups')/str(time.time_ns())
    backup.mkdir(parents=True,mode=0o700)
    shutil.copytree(ROOT,backup/'code',ignore=shutil.ignore_patterns('venv','__pycache__'))
    paths=[Path(p) for p in ['/etc/nanoleaf-hue','/var/lib/nanoleaf-hue-sync','/var/lib/nanoleaf-hue-virtual']]
    for index,path in enumerate(paths):
        if Path(path).exists(): shutil.copytree(path,backup/('state-'+str(index)))
    for unit in UNITS:
        path=Path('/etc/systemd/system')/(unit+'.service')
        if path.exists(): shutil.copy2(path,backup/(unit+'.service'))
    print('Private rollback backup:',backup,flush=True)
    try:
        run('systemctl','stop','nanoleaf-hue-sync','nanoleaf-hue-virtual')
        subprocess.run(['systemctl','stop','nanoleaf-hue-panel','nanoleaf-hue-maintenance','nanoleaf-hue-name'],check=False,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        shutil.copytree(SOURCE/'src',ROOT,dirs_exist_ok=True)
        shutil.copytree(SOURCE/'systemd',ROOT/'systemd',dirs_exist_ok=True)
        sys.path.insert(0,str(ROOT))
        from config import validate
        from portal_install import provision
        data=json.loads(Path('/etc/nanoleaf-hue/config.json').read_text())
        data['mode']='direct'
        validate(data)
        Path('/etc/nanoleaf-hue/config.json').write_text(json.dumps(data,indent=2)+'\n')
        provision(data)
        for unit in UNITS: shutil.copy2(SOURCE/'systemd'/(unit+'.service'),Path('/etc/systemd/system')/(unit+'.service'))
        run('systemctl','daemon-reload')
        run('systemctl','enable','--now',*UNITS)
        deadline=time.monotonic()+30
        while True:
            try:
                with urllib.request.urlopen('http://'+data['ip']+':8080/api/session',timeout=2) as response:
                    if response.status==200:break
            except OSError:
                if time.monotonic()>deadline:raise RuntimeError('Portal startup failed.')
                time.sleep(1)
        run('systemctl','is-active','--quiet',*UNITS)
        print('Update complete. Portal: http://'+data['ip']+':8080')
        print('Existing accounts and API tokens are preserved. HomeKit is disabled. Pair/configure the receiver in Nanoleaf Desktop on the same LAN; old physical panel mappings may need reassignment.')
    except Exception:
        subprocess.run(['systemctl','stop',*UNITS],check=False)
        shutil.copytree(backup/'code',ROOT,dirs_exist_ok=True)
        for unit in UNITS:
            saved=backup/(unit+'.service');target=Path('/etc/systemd/system')/(unit+'.service')
            if saved.exists(): shutil.copy2(saved,target)
            elif target.exists():
                subprocess.run(['systemctl','disable',unit],check=False,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                target.unlink()
        for index,path in enumerate(paths):
            saved=backup/('state-'+str(index))
            if saved.exists(): shutil.copytree(saved,path,dirs_exist_ok=True)
        run('systemctl','daemon-reload')
        run('systemctl','start','nanoleaf-hue-virtual','nanoleaf-hue-sync')
        if (backup/'nanoleaf-hue-panel.service').exists():run('systemctl','start','nanoleaf-hue-panel')
        raise RuntimeError('Update failed; previous code restored. Keep the private backup.') from None

if __name__=='__main__':
    try:main()
    except Exception as error:sys.exit(str(error))
