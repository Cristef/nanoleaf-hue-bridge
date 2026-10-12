#!/bin/bash
set -euo pipefail
export LC_ALL=C.UTF-8
if [[ $EUID != 0 ]]; then echo 'Run this installer as root on the new Debian 12 system.'; exit 1; fi
source /etc/os-release
if [[ ${ID:-} != debian || ${VERSION_ID:-} != 12 ]]; then
    echo 'This installer supports Debian 12 with systemd.'; exit 1
fi
if [[ ! -d /run/systemd/system ]]; then echo 'The system must be running systemd.'; exit 1; fi
SOURCE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
if [[ ! -f $SOURCE/src/wizard.py ]]; then echo 'Extract the entire repository first.'; exit 1; fi
if [[ -d /opt/nanoleaf-probe || -d /opt/nanoleaf-sync ]]; then
    echo 'A previous installation was detected. Use a new Debian 12 system; the existing installation will not be overwritten.'; exit 1
fi
if [[ -f /etc/nanoleaf-hue/config.json ]]; then
    echo 'An installation already exists. Open the menu with: nanoleaf-hue'; exit 0
fi
echo 'Preparing Debian 12: OS updates and dependencies. Router configuration will remain unchanged.'
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold upgrade -y
apt-get install -y python3 python3-venv ca-certificates avahi-daemon avahi-utils iproute2 iputils-ping
install -d -m 0755 /opt/nanoleaf-hue /etc/nanoleaf-hue
cp -a "$SOURCE/src/." /opt/nanoleaf-hue/
cp -a "$SOURCE/systemd" /opt/nanoleaf-hue/
python3 -m venv /opt/nanoleaf-hue/venv
/opt/nanoleaf-hue/venv/bin/pip install --disable-pip-version-check -r "$SOURCE/requirements.txt"
if ! id nanoleaf-hue >/dev/null 2>&1; then
    useradd --system --user-group --no-create-home --shell /usr/sbin/nologin nanoleaf-hue
fi
cat > /usr/local/bin/nanoleaf-hue <<'EOF'
#!/bin/sh
exec /opt/nanoleaf-hue/venv/bin/python /opt/nanoleaf-hue/wizard.py "$@"
EOF
chmod 0755 /usr/local/bin/nanoleaf-hue
systemctl enable --now avahi-daemon
/opt/nanoleaf-hue/venv/bin/python /opt/nanoleaf-hue/wizard.py setup
if [[ -f /var/run/reboot-required ]]; then
    echo 'OS updates require a reboot. The services are enabled at boot.'
    read -r -p 'Reboot the system now? [y/N] ' answer < /dev/tty
    if [[ ${answer,,} == y ]]; then systemctl reboot; fi
fi
