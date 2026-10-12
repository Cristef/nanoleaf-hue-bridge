#!/bin/bash
set -euo pipefail
SOURCE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
[[ $EUID == 0 ]] || { echo 'Run as root in the installed container.'; exit 1; }
[[ -x /opt/nanoleaf-hue/venv/bin/python ]] || { echo 'No supported installation found. Use install.sh for a fresh Debian 12 container.'; exit 1; }
exec /opt/nanoleaf-hue/venv/bin/python "$SOURCE/upgrade.py"
