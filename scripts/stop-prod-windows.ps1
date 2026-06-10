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

$processes = Get-CimInstance Win32_Process
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

if (-not $Quiet) {
  Write-Host "DeerFlow services stopped."
}
