"""Publish the portal's automation API through DNS-SD; advertise no credentials."""
import json,os,subprocess,uuid
from pathlib import Path

def service_arguments(address,port,identity):
    import ipaddress
    address=str(ipaddress.IPv4Address(address));identity=str(uuid.UUID(identity))
    if type(port) is not int or not 1<=port<=65535:raise ValueError('Invalid portal port')
    return ['/usr/bin/avahi-publish-service','--no-fail','Nanoleaf Hue Bridge '+identity[:8],
        '_nanoleaf-hue._tcp',str(port),'id='+identity,'api=1']

if __name__=='__main__':
    data=json.loads(Path(os.environ['PANEL_MAPPING']).with_name('automation-access.json').read_text())
    subprocess.run(service_arguments(os.environ['PANEL_BIND'],8080,data['id']),check=True)
