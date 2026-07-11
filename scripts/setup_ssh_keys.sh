#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "Usage: $0 LINUX_USER PUBLIC_KEY_FILE" >&2
  exit 2
fi

LINUX_USER=$1
PUBLIC_KEY_FILE=$2
id "$LINUX_USER" >/dev/null
ssh-keygen -l -f "$PUBLIC_KEY_FILE" >/dev/null

HOME_DIR=$(getent passwd "$LINUX_USER" | cut -d: -f6)
sudo install -d -m 0700 -o "$LINUX_USER" -g "$LINUX_USER" "$HOME_DIR/.ssh"
sudo install -m 0600 -o "$LINUX_USER" -g "$LINUX_USER" \
  "$PUBLIC_KEY_FILE" "$HOME_DIR/.ssh/authorized_keys"

echo "Installed authorized_keys for $LINUX_USER."
echo "Test this key in a second terminal before disabling password authentication."
