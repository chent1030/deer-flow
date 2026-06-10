param(
  [int]$LocalProxyPort = 7890,
  [int]$BridgeProxyPort = 7891,
  [string]$ConnectionName = "podman-machine-default"
)

$ErrorActionPreference = "Stop"

function Assert-Command($Name) {
  if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
    throw "Required command '$Name' was not found in PATH."
  }
}

function Assert-Administrator {
  $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
  $principal = [Security.Principal.WindowsPrincipal]::new($identity)
  if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Please run this script from an elevated Administrator PowerShell."
  }
}

function Get-PodmanConnection {
  $rows = & podman system connection list
  if ($LASTEXITCODE -ne 0) {
    throw "Failed to read Podman connections."
  }

  foreach ($row in $rows | Select-Object -Skip 1) {
    if ([string]::IsNullOrWhiteSpace($row)) {
      continue
    }

    $cols = $row -split '\s{2,}'
    if ($cols.Count -lt 5) {
      continue
    }

    if ($cols[0] -eq $ConnectionName) {
      return [pscustomobject]@{
        Name       = $cols[0]
        Uri        = $cols[1]
        Identity   = $cols[2]
        Default    = [bool]::Parse($cols[3])
        ReadWrite  = [bool]::Parse($cols[4])
      }
    }
  }

  throw "Podman connection '$ConnectionName' was not found. Run: podman system connection list"
}

function Invoke-RemoteSsh {
  param(
    [string]$User,
    [int]$Port,
    [string]$Identity,
    [string]$Command
  )

  & ssh -i $Identity -p $Port -o BatchMode=yes -o IdentitiesOnly=yes -o StrictHostKeyChecking=no "$User@127.0.0.1" $Command
  if ($LASTEXITCODE -ne 0) {
    throw "ssh command failed with exit code $LASTEXITCODE"
  }
}

Assert-Administrator
Assert-Command podman
Assert-Command ssh
Assert-Command netsh

$localProxy = Test-NetConnection 127.0.0.1 -Port $LocalProxyPort -WarningAction SilentlyContinue
if (-not $localProxy.TcpTestSucceeded) {
  throw "Local proxy 127.0.0.1:$LocalProxyPort is not reachable. Start your proxy client first."
}

$connection = Get-PodmanConnection

$identityPath = $connection.Identity
if (-not (Test-Path -LiteralPath $identityPath)) {
  $fallbackIdentityPath = Join-Path $env:USERPROFILE ".local\share\containers\podman\machine\machine"
  if (Test-Path -LiteralPath $fallbackIdentityPath) {
    Write-Host "Connection identity path is not accessible, using fallback identity path: $fallbackIdentityPath"
    $identityPath = $fallbackIdentityPath
  } else {
    throw "Podman SSH identity file was not found. Connection path: '$($connection.Identity)'. Fallback path: '$fallbackIdentityPath'. Recreate the machine with: podman machine rm -f podman-machine-default; podman machine init --now"
  }
}

$uriMatch = [regex]::Match($connection.Uri, '^ssh://([^@]+)@[^:]+:(\d+)/')
if (-not $uriMatch.Success) {
  throw "Unable to parse Podman connection URI: $($connection.Uri)"
}

$sshUser = $uriMatch.Groups[1].Value
$sshPort = [int]$uriMatch.Groups[2].Value

$remoteHostOutput = & ssh -i $identityPath -p $sshPort -o BatchMode=yes -o IdentitiesOnly=yes -o StrictHostKeyChecking=no "$sshUser@127.0.0.1" "ip route show default | awk '{print `$3; exit}'"
if ($LASTEXITCODE -ne 0) {
  throw "Failed to connect to Podman machine through SSH. Check that the machine is running and the identity file is valid: $identityPath"
}

$remoteHost = ($remoteHostOutput | Select-Object -First 1).Trim()
if (-not $remoteHost) {
  throw "Failed to detect the Windows host gateway address from the Podman machine."
}

$proxyUrl = "http://${remoteHost}:$BridgeProxyPort"

Write-Host "Detected Podman connection: $($connection.Name)"
Write-Host "Detected host gateway from machine: $remoteHost"
Write-Host "Configuring Windows portproxy: ${remoteHost}:$BridgeProxyPort -> 127.0.0.1:$LocalProxyPort"

& netsh interface portproxy delete v4tov4 listenaddress=$remoteHost listenport=$BridgeProxyPort 2>$null | Out-Null
& netsh interface portproxy add v4tov4 listenaddress=$remoteHost listenport=$BridgeProxyPort connectaddress=127.0.0.1 connectport=$LocalProxyPort | Out-Null
if ($LASTEXITCODE -ne 0) {
  throw "Failed to configure netsh portproxy."
}

$ruleName = "WSL Podman Proxy $BridgeProxyPort"
$existingRule = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue
if (-not $existingRule) {
  New-NetFirewallRule `
    -DisplayName $ruleName `
    -Direction Inbound `
    -Action Allow `
    -Protocol TCP `
    -LocalAddress $remoteHost `
    -LocalPort $BridgeProxyPort | Out-Null
}

if ($sshUser -ne "root") {
  $prepareUserConfigScript = "set -e; mkdir -p /home/$sshUser/.config/systemd/user/podman.service.d; chown -R ${sshUser}:${sshUser} /home/$sshUser/.config"
  Write-Host "Preparing rootless user config directory permissions..."
  Invoke-RemoteSsh -User "root" -Port $sshPort -Identity $identityPath -Command $prepareUserConfigScript
}

$rootlessScript = @"
set -e
mkdir -p ~/.config/systemd/user/podman.service.d
cat > ~/.config/systemd/user/podman.service.d/proxy.conf <<'EOF'
[Service]
Environment=HTTP_PROXY=$proxyUrl
Environment=HTTPS_PROXY=$proxyUrl
Environment=ALL_PROXY=$proxyUrl
Environment=NO_PROXY=localhost,127.0.0.1,::1,host.containers.internal
EOF
systemctl --user daemon-reload
systemctl --user restart podman.service 2>/dev/null || true
systemctl --user restart podman.socket 2>/dev/null || true
curl -sS -I --proxy $proxyUrl --max-time 20 https://registry-1.docker.io/v2/ | head -n 1
"@

Write-Host "Configuring Podman service proxy inside machine..."
Invoke-RemoteSsh -User $sshUser -Port $sshPort -Identity $identityPath -Command $rootlessScript

Write-Host ""
Write-Host "Podman proxy configured permanently for connection '$($connection.Name)'."
Write-Host "Proxy URL inside the machine: $proxyUrl"
Write-Host ""
Write-Host "You can now run without extra proxy parameters:"
Write-Host "  podman pull docker.io/library/postgres:16-alpine"
Write-Host "  podman pull docker.io/minio/minio:latest"
