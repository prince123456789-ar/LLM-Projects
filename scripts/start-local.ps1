param(
  [int]$BackendPort = 8000,
  [switch]$SeedDemoUsers,
  [string]$BootstrapAdminEmail = "",
  [string]$BootstrapAdminPassword = ""
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$backendDir = Join-Path $repoRoot "backend"
$py = Join-Path $backendDir ".venv\\Scripts\\python.exe"

if (!(Test-Path $py)) {
  throw "Backend venv missing. Create it with: py -3.12 -m venv saas/backend/.venv"
}

Write-Host "Starting app (API + UI) on http://127.0.0.1:$BackendPort ..."
$logDir = Join-Path $repoRoot "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$outLog = Join-Path $logDir "backend-uvicorn.out.log"
$errLog = Join-Path $logDir "backend-uvicorn.err.log"

$p = Start-Process -WorkingDirectory $backendDir -FilePath $py -PassThru -ArgumentList @(
  "-m","uvicorn","app.main:app",
  "--host","0.0.0.0",
  "--port","$BackendPort",
  "--log-level","info"
) -RedirectStandardOutput $outLog -RedirectStandardError $errLog

for ($i = 0; $i -lt 20; $i++) {
  Start-Sleep -Milliseconds 500
  if ($p.HasExited) { break }
  $listening = (netstat -ano | Select-String (":$BackendPort\\s") | Select-String "LISTENING")
  if ($listening) { break }
}

if ($p.HasExited -or -not (netstat -ano | Select-String (":$BackendPort\\s") | Select-String "LISTENING")) {
  Write-Host "Backend failed to start (no listener detected on port $BackendPort)."
  Write-Host "Last error log lines:"
  if (Test-Path $errLog) { Get-Content $errLog -Tail 120 }
  Write-Host "Last output log lines:"
  if (Test-Path $outLog) { Get-Content $outLog -Tail 120 }
  throw "Backend start failed"
}

if ($SeedDemoUsers) {
  Write-Host "Seeding demo users..."
  Start-Sleep -Seconds 2
  Push-Location $backendDir
  try {
    if ($BootstrapAdminEmail -and $BootstrapAdminPassword) {
      $env:BOOTSTRAP_ADMIN_EMAIL = $BootstrapAdminEmail
      $env:BOOTSTRAP_ADMIN_PASSWORD = $BootstrapAdminPassword
    }
    & $py "-m" "app.bootstrap"
  } finally {
    Pop-Location
  }
}

Write-Host ""
Write-Host "Open (UI): http://localhost:$BackendPort"
Write-Host "Health check: http://127.0.0.1:$BackendPort/health"
