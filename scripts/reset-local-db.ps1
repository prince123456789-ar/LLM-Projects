param(
  [string]$DbPath = "saas/backend/local_dev.db"
)

$ErrorActionPreference = "Stop"

if (Test-Path $DbPath) {
  Remove-Item -Force $DbPath
  Write-Host "Deleted: $DbPath"
} else {
  Write-Host "No DB file found at: $DbPath"
}

Write-Host "Next: restart backend to recreate tables."

