<#
.SYNOPSIS
  Start DeerFlow services on Windows in the background for production use.

.DESCRIPTION
  Starts LangGraph, Gateway, Frontend (Next.js production), and nginx as
  background PowerShell processes. Also starts the admin panel. Logs and PID
  files are written under ./logs.

  Run from any directory inside the repository:
    powershell -ExecutionPolicy Bypass -File .\scripts\start-prod-windows.ps1

  Stop services with:
    powershell -ExecutionPolicy Bypass -File .\scripts\stop-prod-windows.ps1
#>

[CmdletBinding()]
param(
  [switch]$SkipFrontendBuild,
  [Nullable[bool]]$AllowBlocking = $null,
  [string]$LangGraphLogLevel = $env:LANGGRAPH_LOG_LEVEL,
  [int]$LangGraphJobsPerWorker = 10,
  [Nullable[bool]]$LangGraphIsolatedLoops = $null,
  [int]$StartupTimeoutSeconds = 300
)

$ErrorActionPreference = "Stop"

function Get-RepoRoot {
  $scriptDir = Split-Path -Parent $PSCommandPath
  return (Resolve-Path (Join-Path $scriptDir "..")).Path
}

function Assert-Command($Name) {
  if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
    throw "Required command '$Name' was not found in PATH."
  }
}

function Ensure-Config($RepoRoot) {
  $configPath = if ($env:DEER_FLOW_CONFIG_PATH) { $env:DEER_FLOW_CONFIG_PATH } else { Join-Path $RepoRoot "config.yaml" }
  if (-not (Test-Path $configPath)) {
    throw "Config file not found: $configPath. Create it first, e.g. make config."
  }
}

function Ensure-FrontendEnv($RepoRoot) {
  $envPath = Join-Path $RepoRoot "frontend\.env.production.local"
  if (-not (Test-Path $envPath)) {
    throw "Frontend production env file not found: $envPath. Create it with BETTER_AUTH_SECRET and NEXT_PUBLIC_LANGGRAPH_BASE_URL."
  }

  $content = Get-Content -Path $envPath -Raw
  if ($content -notmatch "(?m)^\s*BETTER_AUTH_SECRET\s*=\s*\S+") {
    throw "BETTER_AUTH_SECRET is required in $envPath."
  }
  if ($content -notmatch "(?m)^\s*NEXT_PUBLIC_LANGGRAPH_BASE_URL\s*=\s*/api/langgraph\s*$") {
    throw "NEXT_PUBLIC_LANGGRAPH_BASE_URL=/api/langgraph is required in $envPath for production. Do not use /api/langgraph-compat in production because long-running agent jobs can block Gateway APIs."
  }
}

function Wait-Port($Port, $Name, $TimeoutSeconds, $Process, $LogPath) {
  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  while ((Get-Date) -lt $deadline) {
    if ($null -ne $Process -and $Process.HasExited) {
      throw "$Name exited before listening on port $Port. Check log: $LogPath"
    }

    try {
      $client = [System.Net.Sockets.TcpClient]::new()
      $async = $client.BeginConnect("127.0.0.1", $Port, $null, $null)
      if ($async.AsyncWaitHandle.WaitOne(1000, $false)) {
        $client.EndConnect($async)
        $client.Close()
        Write-Host "OK $Name started on port $Port"
        return
      }
      $client.Close()
    } catch {
      Start-Sleep -Milliseconds 500
    }
  }
  throw "$Name did not listen on port $Port within $TimeoutSeconds seconds. Check log: $LogPath"
}

function Start-DeerFlowProcess($Name, $WorkingDirectory, $Command, $LogPath, $PidPath) {
  if (Test-Path $LogPath) {
    Remove-Item $LogPath -Force
  }

  $escapedWorkDir = $WorkingDirectory.Replace("'", "''")
  $escapedLog = $LogPath.Replace("'", "''")
  $wrappedCommand = "Set-Location '$escapedWorkDir'; $Command *> '$escapedLog'"
  $process = Start-Process -FilePath "powershell.exe" `
    -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", $wrappedCommand) `
    -WindowStyle Hidden `
    -PassThru

  Set-Content -Path $PidPath -Value $process.Id -Encoding ASCII
  Write-Host "Started $Name as process $($process.Id)"
  return $process
}

$repoRoot = Get-RepoRoot
Set-Location $repoRoot

$logsDir = Join-Path $repoRoot "logs"
New-Item -ItemType Directory -Force -Path $logsDir | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $repoRoot "temp\client_body_temp") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $repoRoot "temp\proxy_temp") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $repoRoot "temp\fastcgi_temp") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $repoRoot "temp\uwsgi_temp") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $repoRoot "temp\scgi_temp") | Out-Null

Assert-Command uv
Assert-Command pnpm
Assert-Command nginx
Ensure-Config $repoRoot
Ensure-FrontendEnv $repoRoot

if ([string]::IsNullOrWhiteSpace($LangGraphLogLevel)) {
  $LangGraphLogLevel = "info"
}

if ($null -eq $AllowBlocking) {
  $AllowBlocking = $env:LANGGRAPH_ALLOW_BLOCKING -eq "1" -or $env:LANGGRAPH_ALLOW_BLOCKING -eq "true"
}

if ($null -eq $LangGraphIsolatedLoops) {
  $LangGraphIsolatedLoops = if ($env:BG_JOB_ISOLATED_LOOPS) {
    $env:BG_JOB_ISOLATED_LOOPS -eq "1" -or $env:BG_JOB_ISOLATED_LOOPS -eq "true"
  } else {
    $true
  }
}

Write-Host "Stopping existing DeerFlow processes if any..."
& (Join-Path $repoRoot "scripts\stop-prod-windows.ps1") -Quiet -ErrorAction SilentlyContinue

if (-not $SkipFrontendBuild) {
  Write-Host "Building frontend..."
  Push-Location (Join-Path $repoRoot "frontend")
  try {
    pnpm build
  } finally {
    Pop-Location
  }

  Write-Host "Building admin..."
  Push-Location (Join-Path $repoRoot "admin")
  try {
    pnpm build
  } finally {
    Pop-Location
  }
}

$langgraphArgs = @(
  "uv run python start_langgraph.py --no-browser --no-reload",
  "--n-jobs-per-worker $LangGraphJobsPerWorker",
  "--host 0.0.0.0",
  "--server-log-level $LangGraphLogLevel"
)
$allowBlockingValue = if ($AllowBlocking) { "true" } else { "false" }
$isolatedLoopsValue = if ($LangGraphIsolatedLoops) { "true" } else { "false" }
if ($AllowBlocking) {
  $langgraphArgs += "--allow-blocking"
}
$langgraphCmd = "`$env:NO_COLOR='1'; `$env:PYTHONPATH='.'; `$env:LANGGRAPH_ALLOW_BLOCKING='$allowBlockingValue'; `$env:BG_JOB_ISOLATED_LOOPS='$isolatedLoopsValue'; " + ($langgraphArgs -join " ")
$gatewayCmd = "`$env:PYTHONPATH='.'; uv run python start_gateway.py"
$frontendCmd = "pnpm start"
$adminCmd = "pnpm preview --host 0.0.0.0 --port 3002"
$nginxConf = Join-Path $repoRoot "docker\nginx\nginx.local.conf"
$nginxCmd = "nginx -g 'daemon off;' -c '$nginxConf' -p '$repoRoot'"

$langgraphLog = Join-Path $logsDir "langgraph.log"
$langgraphProcess = Start-DeerFlowProcess "langgraph" (Join-Path $repoRoot "backend") $langgraphCmd $langgraphLog (Join-Path $logsDir "langgraph.pid")
Wait-Port 2024 "LangGraph" $StartupTimeoutSeconds $langgraphProcess $langgraphLog

$gatewayLog = Join-Path $logsDir "gateway.log"
$gatewayProcess = Start-DeerFlowProcess "gateway" (Join-Path $repoRoot "backend") $gatewayCmd $gatewayLog (Join-Path $logsDir "gateway.pid")
Wait-Port 8001 "Gateway" $StartupTimeoutSeconds $gatewayProcess $gatewayLog

$frontendLog = Join-Path $logsDir "frontend.log"
$frontendProcess = Start-DeerFlowProcess "frontend" (Join-Path $repoRoot "frontend") $frontendCmd $frontendLog (Join-Path $logsDir "frontend.pid")
Wait-Port 3000 "Frontend" $StartupTimeoutSeconds $frontendProcess $frontendLog

$adminLog = Join-Path $logsDir "admin.log"
$adminProcess = Start-DeerFlowProcess "admin" (Join-Path $repoRoot "admin") $adminCmd $adminLog (Join-Path $logsDir "admin.pid")
Wait-Port 3002 "Admin" $StartupTimeoutSeconds $adminProcess $adminLog

$nginxLog = Join-Path $logsDir "nginx.log"
$nginxProcess = Start-DeerFlowProcess "nginx" $repoRoot $nginxCmd $nginxLog (Join-Path $logsDir "nginx.pid")
Wait-Port 2026 "nginx" $StartupTimeoutSeconds $nginxProcess $nginxLog

Write-Host ""
Write-Host "DeerFlow production services are running in background."
Write-Host "URL:  http://localhost:2026"
Write-Host "LAN:  http://<WindowsHostIP>:2026"
Write-Host "Logs: $logsDir"
Write-Host "Stop: powershell -ExecutionPolicy Bypass -File .\scripts\stop-prod-windows.ps1"
