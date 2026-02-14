param(
  [int]$BackendPort = 8000,
  [switch]$SeedDemoUsers
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$backendDir = Join-Path $repoRoot "backend"
$py = Join-Path $backendDir ".venv\\Scripts\\python.exe"

if (!(Test-Path $py)) {
  throw "Backend venv missing. Create it with: py -3.12 -m venv saas/backend/.venv"
}

Write-Host "Starting app (API + UI) on http://127.0.0.1:$BackendPort ..."
Start-Process -WorkingDirectory $backendDir -FilePath $py -ArgumentList @(
  "-m","uvicorn","app.main:app",
  "--host","0.0.0.0",
  "--port","$BackendPort",
  "--log-level","info"
)

if ($SeedDemoUsers) {
  Write-Host "Seeding demo users..."
  Start-Sleep -Seconds 2
  Push-Location $backendDir
  try {
    & $py "-m" "app.bootstrap"
  } finally {
    Pop-Location
  }
}

Write-Host ""
Write-Host "Open (UI): http://localhost:$BackendPort"
Write-Host "Health check: http://127.0.0.1:$BackendPort/health"
