# Shared GPU workstation

Clone the repository anywhere. Data, runs, and submissions stay inside it:

```text
Novel-View-Synthesis/
├── VAI_NVS_DATA/
├── runs/
└── submissions/
```

Run `scripts/setup_shared_workstation.sh USER1 USER2` from this checkout. It
creates accounts, adds the shared group, and gives that group access to this
checkout. It does not create `/srv/var2026`.

Install keys one user at a time:

```bash
scripts/setup_ssh_keys.sh USER1 /path/to/user1.pub
scripts/setup_ssh_keys.sh USER2 /path/to/user2.pub
```

Test both accounts in separate terminals. Only then run:

```bash
scripts/enable_key_only_ssh.sh USER1 USER2
```

Run Tailscale on Windows, not inside WSL. In elevated PowerShell, refresh the
forwarding rules after a WSL address change:

```powershell
.\scripts\windows\update_wsl_portproxy.ps1 -Distro Ubuntu
```

VS Code SSH configuration:

```sshconfig
Host var2026-gpu
    HostName <Windows-Tailscale-IP-or-MagicDNS-name>
    Port 2222
    User <Linux-user>
    IdentityFile ~/.ssh/id_ed25519
```

Use one named tmux session per long job. Use `just` recipes so operators run the
same explicit CLI and paths. Tailscale is the access boundary; ports are not
intended for public Internet exposure.
