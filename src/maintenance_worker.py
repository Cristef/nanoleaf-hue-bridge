"""Apply only locally staged, checksum-verified maintenance bundles; retain private state."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import time
import urllib.request
from portal_settings import atomic_json

ROOT=Path('/opt/nanoleaf-hue');STATE=Path('/var/lib/nanoleaf-hue-sync');RUNTIME=Path('/run/nanoleaf-hue')
FILES={'tv_mapping.py','portal_discovery.py','web/onboarding.js','web/onboarding.css','automation_api.py','web/integration.js','advanced_portal.py','test_patterns.py','portal_control.py','portal_settings.py','control_panel.py','control_panel_v2.py','daily_sync.py','hue_sync.py','color_response.py','brightness.py','panel_mapping.py','portal_auth.py','extcontrol_probe.py','direct_stats.py','web/index.html','web/style.css','web/app.js','web/portal.js','web/advanced.js','web/shell.js','web/shell.css'}
def status(phase,message):atomic_json(RUNTIME/'maintenance-status.json',{'phase':phase,'message':message,'time':time.time()})
def run(*args):subprocess.run(args,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=60)
def validate_bundle(archive,manifest):
    if hashlib.sha256(archive.read_bytes()).hexdigest()!=manifest['sha256']:raise ValueError('Checksum mismatch')
    with tarfile.open(archive) as tar:
        members=tar.getmembers()
        if not members or len(members)>len(FILES):raise ValueError('Invalid bundle')
        if any(not m.isfile() or m.name not in FILES or m.size>1000000 for m in members):raise ValueError('Unexpected file')
        if len({m.name for m in members})!=len(members):raise ValueError('Duplicate file')
        return {m.name:tar.extractfile(m).read() for m in members}
def restore(backup):
    for name in FILES:
        src=backup/'code'/name
        if src.exists():shutil.copy2(src,ROOT/name)
        elif (ROOT/name).exists():(ROOT/name).unlink()
    settings=backup/'portal-settings.json'
    if settings.exists():shutil.copy2(settings,STATE/'portal-settings.json')
def restart():
    run('systemctl','restart','nanoleaf-hue-sync','nanoleaf-hue-panel')
    time.sleep(3)
    run('systemctl','is-active','--quiet','nanoleaf-hue-virtual','nanoleaf-hue-sync','nanoleaf-hue-panel')
    with urllib.request.urlopen('http://'+json.loads(Path('/etc/nanoleaf-hue/config.json').read_text())['ip']+':8080/api/session',timeout=3) as response:
        if response.status!=200:raise RuntimeError('Portal check failed')
def apply_update():
    manifest=json.loads((STATE/'updates/candidate.json').read_text())
    files=validate_bundle(STATE/'updates/candidate.tar.gz',manifest)
    backup=STATE/'backups'/str(time.time_ns());backup.mkdir(parents=True,mode=0o700)
    status('backing-up','Creating private code/settings backup.')
    shutil.copytree(ROOT,backup/'code',ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copy2(STATE/'portal-settings.json',backup/'portal-settings.json')
    try:
        status('installing','Installing verified local bundle. Services will restart.')
        run('systemctl','stop','nanoleaf-hue-sync','nanoleaf-hue-panel')
        for name,data in files.items():
            target=ROOT/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data);target.chmod(0o644)
        run('/opt/nanoleaf-hue/venv/bin/python','-m','compileall','-q',str(ROOT))
        restart();atomic_json(STATE/'updates/last-backup.json',{'path':str(backup)})
        (STATE/'updates/candidate.json').unlink()
        status('complete','Update complete. Reload the portal. Private backup is available.')
    except Exception:
        restore(backup);restart();status('recovered','Update failed; previous code and settings restored.')
def rollback():
    data=json.loads((STATE/'updates/last-backup.json').read_text());backup=Path(data['path'])
    if backup.parent.resolve()!=(STATE/'backups').resolve() or not backup.is_dir():raise ValueError('Invalid backup')
    status('rolling-back','Restoring last update backup.')
    run('systemctl','stop','nanoleaf-hue-sync','nanoleaf-hue-panel');restore(backup);restart();status('recovered','Backup restored. Reload the portal.')
def source_update():
    from config import validate
    config_path=Path('/etc/nanoleaf-hue/config.json');old=config_path.read_bytes()
    data=json.loads(old);data['source_ip']=json.loads((STATE/'source.json').read_text())['ip'];validate(data)
    import ipaddress
    if ipaddress.ip_address(data['source_ip']) not in ipaddress.ip_network(data['ip']+'/'+str(data.get('prefix',24)),strict=False):raise ValueError('Source must share LAN')
    try:
        atomic_json(config_path,data);run('systemctl','restart','nanoleaf-hue-virtual');time.sleep(2);run('systemctl','is-active','--quiet','nanoleaf-hue-virtual')
        atomic_json(STATE/'source-applied.json',{'ip':data['source_ip']});status('complete','4D source updated. Register the virtual receiver in Desktop Sync+.')
    except Exception:
        config_path.write_bytes(old);atomic_json(STATE/'source.json',{'ip':json.loads(old)['source_ip']});run('systemctl','restart','nanoleaf-hue-virtual');raise

def main():
    os.umask(0o077)
    request=RUNTIME/'maintenance-request.json'
    while True:
        if request.exists():
            try:
                data=json.loads(request.read_text());request.unlink()
                if not 0<=time.time()-data['time']<=60:raise ValueError('Expired request')
                if data['action']=='update':apply_update()
                elif data['action']=='rollback':rollback()
                elif data['action']=='source':source_update()
                else:raise ValueError('Invalid request')
            except Exception:status('error','Maintenance failed. Check diagnostics; no successful update confirmed.')
        time.sleep(.5)
if __name__=='__main__':main()
