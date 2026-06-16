<#
.SYNOPSIS
  Stop DeerFlow background processes started by start-prod-windows.ps1.
#>

[CmdletBinding()]
param([switch]$Quiet)

$ErrorActionPreference = "Continue"

$scriptDir = Split-Path -Parent $PSCommandPath
$repoRoot = (Resolve-Path (Join-Path $scriptDir "..")).Path
$logsDir = Join-Path $repoRoot "logs"

function Stop-PortProcess($Port) {
  $lines = netstat -ano -p tcp 2>$null | Select-String -Pattern "LISTENING\s+\d+$" | ForEach-Object { $_.Line }
  foreach ($line in $lines) {
    $columns = $line -split "\s+" | Where-Object { $_ }
    if ($columns.Count -lt 5) {
      continue
    }

    $localAddress = $columns[1]
    $processIdText = $columns[-1]
    if ($localAddress -notmatch "[:.]$Port$") {
      continue
    }

    $processId = 0
    if (-not [int]::TryParse($processIdText, [ref]$processId)) {
      continue
    }
    if ($processId -eq $PID) {
      continue
    }

    try {
      Stop-Process -Id $processId -Force -ErrorAction Stop
      if (-not $Quiet) { Write-Host "Stopped process $processId on port $Port" }
    } catch {
      taskkill /PID $processId /T /F 2>$null | Out-Null
      if (-not $Quiet) { Write-Host "Requested taskkill for process $processId on port $Port" }
    }
  }
}

$services = @("nginx", "admin", "frontend", "gateway", "langgraph")
foreach ($service in $services) {
  $pidFile = Join-Path $logsDir "$service.pid"
  if (Test-Path $pidFile) {
    $pidText = (Get-Content $pidFile -Raw).Trim()
    $processId = 0
    if ([int]::TryParse($pidText, [ref]$processId)) {
      try {
        Stop-Process -Id $processId -Force -ErrorAction Stop
        if (-not $Quiet) { Write-Host "Stopped $service process $processId" }
      } catch {}
    }
    Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
  }
}

# Best-effort cleanup for child processes started by the service launchers.
$patterns = @(
  "langgraph dev",
  "start_langgraph.py",
  "start_gateway.py",
  "uvicorn app.gateway.app:app",
  "next start",
  "vite preview",
  "nginx.*nginx.local.conf"
)

$processes = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue
if ($processes) {
  foreach ($pattern in $patterns) {
    $regex = [regex]$pattern
    $matches = $processes | Where-Object { $_.CommandLine -and $regex.IsMatch($_.CommandLine) }
    foreach ($proc in $matches) {
      try {
        Stop-Process -Id $proc.ProcessId -Force -ErrorAction Stop
        if (-not $Quiet) { Write-Host "Stopped process $($proc.ProcessId): $pattern" }
      } catch {}
    }
  }
}

foreach ($port in @(2024, 8001, 3000, 3002, 2026)) {
  Stop-PortProcess $port
}

if (-not $Quiet) {
  Write-Host "DeerFlow services stopped."
}
