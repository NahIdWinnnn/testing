#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "Usage: $0 TEAMMATE1 TEAMMATE2" >&2
  echo "Run only after choosing real Linux usernames." >&2
  exit 2
fi

TEAMMATE1=$1
TEAMMATE2=$2
OWNER=${SUDO_USER:-${USER}}
TEAM_GROUP=NoLongerHamster
WORKSPACE=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)

sudo apt update
sudo apt install -y git git-lfs acl openssh-server tmux just build-essential
sudo groupadd -f "$TEAM_GROUP"

for teammate in "$TEAMMATE1" "$TEAMMATE2"; do
  if ! id "$teammate" >/dev/null 2>&1; then
    sudo adduser "$teammate"
  fi
  sudo usermod -aG "sudo,$TEAM_GROUP" "$teammate"
done
sudo usermod -aG "$TEAM_GROUP" "$OWNER"

sudo install -d -o "$OWNER" -g "$TEAM_GROUP" -m 2770 \
  "$WORKSPACE" \
  "$WORKSPACE/VAI_NVS_DATA" \
  "$WORKSPACE/runs" \
  "$WORKSPACE/submissions"
sudo chown -R "$OWNER:$TEAM_GROUP" "$WORKSPACE"
sudo find "$WORKSPACE" -type d -exec chmod 2770 {} +
sudo find "$WORKSPACE" -type f -exec chmod 0660 {} +
sudo setfacl -R -m "g:$TEAM_GROUP:rwx" "$WORKSPACE"
sudo setfacl -R -d -m "g:$TEAM_GROUP:rwx" "$WORKSPACE"
sudo setfacl -R -d -m o::--- "$WORKSPACE"

echo "Workspace created. Log out/in to refresh group membership."
echo "Next: run scripts/setup_ssh_keys.sh with each teammate username and public-key file."
