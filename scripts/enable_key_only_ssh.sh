#!/usr/bin/env bash
set -euo pipefail

for user in "$@"; do
  home_dir=$(getent passwd "$user" | cut -d: -f6)
  if [[ ! -s "$home_dir/.ssh/authorized_keys" ]]; then
    echo "Refusing: $user has no nonempty authorized_keys file." >&2
    exit 2
  fi
done

config=$(mktemp)
trap 'rm -f "$config"' EXIT
printf '%s\n' \
  "PubkeyAuthentication yes" \
  "PasswordAuthentication no" \
  "KbdInteractiveAuthentication no" \
  "PermitRootLogin no" \
  "AllowGroups sudo NoLongerHamster" >"$config"
sudo install -m 0644 "$config" /etc/ssh/sshd_config.d/var2026.conf
sudo sshd -t
sudo systemctl enable --now ssh
sudo systemctl restart ssh
echo "Key-only SSH enabled. Keep the current terminal open while testing access."
