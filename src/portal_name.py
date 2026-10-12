"""Publish only the configured LAN alias; preserve Nanoleaf device identity."""
import subprocess
from config import CONFIG
if __name__=='__main__':
    subprocess.run(['/usr/bin/avahi-publish-address','-R','--no-fail',CONFIG.get('portal_name','nanoleaf-hue.local'),CONFIG['ip']],check=True)
