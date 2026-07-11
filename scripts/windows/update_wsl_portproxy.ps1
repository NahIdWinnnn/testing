#Requires -RunAsAdministrator
param(
    [string]$Distro = "Ubuntu"
)

$ErrorActionPreference = "Stop"

$WslIp = (wsl.exe -d $Distro -- hostname -I).Trim().Split(" ")[0]
$TailscaleIp = (tailscale.exe ip -4).Trim().Split("`n")[0].Trim()

if (-not $WslIp) { throw "Could not determine the WSL IPv4 address." }
if (-not $TailscaleIp) { throw "Could not determine the Tailscale IPv4 address." }

$Mappings = @(
    @{ ListenPort = 2222; ConnectPort = 22 },
    @{ ListenPort = 8501; ConnectPort = 8501 }
)

foreach ($Mapping in $Mappings) {
    netsh interface portproxy delete v4tov4 `
        listenaddress=$TailscaleIp `
        listenport=$Mapping.ListenPort 2>$null

    netsh interface portproxy add v4tov4 `
        listenaddress=$TailscaleIp `
        listenport=$Mapping.ListenPort `
        connectaddress=$WslIp `
        connectport=$Mapping.ConnectPort
}

Get-NetFirewallRule -DisplayName "VAR2026 WSL Portproxy *" `
    -ErrorAction SilentlyContinue |
    Remove-NetFirewallRule

New-NetFirewallRule `
    -DisplayName "VAR2026 WSL Portproxy SSH" `
    -Direction Inbound -Action Allow -Protocol TCP `
    -LocalPort 2222 -LocalAddress $TailscaleIp `
    -RemoteAddress 100.64.0.0/10

New-NetFirewallRule `
    -DisplayName "VAR2026 WSL Portproxy Dashboard" `
    -Direction Inbound -Action Allow -Protocol TCP `
    -LocalPort 8501 -LocalAddress $TailscaleIp `
    -RemoteAddress 100.64.0.0/10

Write-Host "WSL address: $WslIp"
Write-Host "SSH: ssh -p 2222 <user>@$TailscaleIp"
Write-Host "Dashboard: http://${TailscaleIp}:8501"
