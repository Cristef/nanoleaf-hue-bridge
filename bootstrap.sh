#!/bin/bash
# Entry point for the future one-command GitHub installation.
set -euo pipefail
[[ $EUID == 0 ]] || { echo 'Run as root in the Debian 12 LXC container.'; exit 1; }
REPOSITORY=${1:-}
if [[ -z $REPOSITORY ]]; then
    read -r -p 'GitHub repository (owner/repository): ' REPOSITORY < /dev/tty
fi
[[ $REPOSITORY =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]] || { echo 'Invalid repository.'; exit 1; }
apt-get update
apt-get install -y ca-certificates curl tar
WORK=$(mktemp -d)
trap 'rm -rf -- "$WORK"' EXIT
curl --fail --location --proto '=https' --tlsv1.2 "https://github.com/$REPOSITORY/archive/refs/heads/main.tar.gz" -o "$WORK/source.tar.gz"
mkdir "$WORK/source"
tar --extract --gzip --file "$WORK/source.tar.gz" --directory "$WORK/source" --strip-components=1
bash "$WORK/source/install.sh"
