#!/bin/bash
# Guided installation of this tagged release.
set -euo pipefail
[[ $EUID == 0 ]] || { echo 'Run as root on Debian 12.'; exit 1; }
REPOSITORY=${1:-Cristef/nanoleaf-hue-bridge}
if [[ -z $REPOSITORY ]]; then
    read -r -p 'GitHub repository (owner/repository): ' REPOSITORY < /dev/tty
fi
[[ $REPOSITORY =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]] || { echo 'Invalid repository.'; exit 1; }
apt-get update
apt-get install -y ca-certificates curl tar
WORK=$(mktemp -d)
trap 'rm -rf -- "$WORK"' EXIT
curl --fail --location --proto '=https' --tlsv1.2 "https://github.com/$REPOSITORY/archive/refs/tags/v4.2.0.tar.gz" -o "$WORK/source.tar.gz"
mkdir "$WORK/source"
tar --extract --gzip --file "$WORK/source.tar.gz" --directory "$WORK/source" --strip-components=1
bash "$WORK/source/install.sh"
