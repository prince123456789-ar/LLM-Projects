param(
  [Parameter(Mandatory = $true)]
  [string]$RenderApiKey,
  [string]$BackendServiceName = "real-estate-ai-backend",
  [string]$WorkerServiceName = "real-estate-ai-worker",
  [string]$FrontendServiceName = "real-estate-ai-frontend",
  [string]$EnvFilePath = ".env",
  [switch]$ListOnly
)

$ErrorActionPreference = "Stop"

function Parse-EnvFile {
  param([string]$Path)

  if (-not (Test-Path $Path)) {
    throw "Env file not found: $Path"
  }

  $map = @{}
  Get-Content $Path | ForEach-Object {
    $line = $_.Trim()
    if (-not $line -or $line.StartsWith("#")) { return }
    $parts = $line -split "=", 2
    if ($parts.Count -ne 2) { return }
    $k = $parts[0].Trim()
    $v = $parts[1].Trim()
    $map[$k] = $v
  }
  return $map
}

function Get-ServiceByName {
  param(
    [string]$Name,
    [array]$Services
  )

  $service = $Services | Where-Object { $_.service.name -eq $Name } | Select-Object -First 1
  if (-not $service) { return $null }
  return $service.service
}

function Set-EnvVar {
  param(
    [string]$ServiceId,
    [string]$Key,
    [string]$Value,
    [hashtable]$Headers
  )

  if ($null -eq $Value -or $Value -eq "") { return }

  $uri = "https://api.render.com/v1/services/$ServiceId/env-vars/$Key"
  $body = @{ value = $Value } | ConvertTo-Json
  Invoke-RestMethod -Method Put -Uri $uri -Headers $Headers -ContentType "application/json" -Body $body | Out-Null
  Write-Host "Set $Key on service $ServiceId"
}

function Apply-EnvSet {
  param(
    [string]$ServiceId,
    [string[]]$Keys,
    [hashtable]$AllVars,
    [hashtable]$Headers
  )

  foreach ($k in $Keys) {
    if ($AllVars.ContainsKey($k)) {
      Set-EnvVar -ServiceId $ServiceId -Key $k -Value $AllVars[$k] -Headers $Headers
    }
  }
}

$headers = @{ Authorization = "Bearer $RenderApiKey" }
$vars = Parse-EnvFile -Path $EnvFilePath
$services = Invoke-RestMethod -Method Get -Uri "https://api.render.com/v1/services?limit=100" -Headers $headers

if ($ListOnly) {
  Write-Host "Render services found:"
  $services | ForEach-Object {
    $svc = $_.service
    Write-Host "- $($svc.name) [type=$($svc.type)] [id=$($svc.id)]"
  }
  exit 0
}

$backend = Get-ServiceByName -Name $BackendServiceName -Services $services
$worker = Get-ServiceByName -Name $WorkerServiceName -Services $services
$frontend = Get-ServiceByName -Name $FrontendServiceName -Services $services

if (-not $backend) {
  $backend = ($services | Where-Object {
      $_.service.type -eq "web_service" -and $_.service.name -match "backend|api"
    } | Select-Object -First 1).service
}
if (-not $worker) {
  $worker = ($services | Where-Object {
      $_.service.type -eq "background_worker" -or $_.service.name -match "worker"
    } | Select-Object -First 1).service
}
if (-not $frontend) {
  $frontend = ($services | Where-Object {
      $_.service.type -eq "web_service" -and $_.service.name -match "frontend|web|ui"
    } | Select-Object -First 1).service
}

if (-not $backend -or -not $worker -or -not $frontend) {
  Write-Host "Could not auto-resolve all services."
  Write-Host "Available services:"
  $services | ForEach-Object {
    $svc = $_.service
    Write-Host "- $($svc.name) [type=$($svc.type)]"
  }
  throw "Pass explicit -BackendServiceName/-WorkerServiceName/-FrontendServiceName"
}

Write-Host "Using backend: $($backend.name)"
Write-Host "Using worker: $($worker.name)"
Write-Host "Using frontend: $($frontend.name)"

$backendKeys = @(
  "ENVIRONMENT",
  "PROJECT_NAME",
  "API_V1_STR",
  "SECRET_KEY",
  "ACCESS_TOKEN_EXPIRE_MINUTES",
  "REFRESH_TOKEN_EXPIRE_DAYS",
  "JWT_ALGORITHM",
  "JWT_ISSUER",
  "JWT_AUDIENCE",
  "ZERO_TRUST_SIGNING_ALG",
  "DATABASE_URL",
  "REDIS_URL",
  "CELERY_BROKER_URL",
  "CELERY_RESULT_BACKEND",
  "BACKEND_CORS_ORIGINS",
  "ALLOWED_HOSTS",
  "WEBHOOK_SHARED_SECRET",
  "WEBHOOK_MAX_SKEW_SECONDS",
  "META_VERIFY_TOKEN",
  "META_APP_SECRET",
  "LOGIN_MAX_ATTEMPTS",
  "LOGIN_LOCK_MINUTES",
  "SMTP_HOST",
  "SMTP_PORT",
  "SMTP_USERNAME",
  "SMTP_PASSWORD",
  "SMTP_FROM_EMAIL",
  "STRIPE_SECRET_KEY",
  "STRIPE_WEBHOOK_SECRET",
  "STRIPE_PRICE_ID",
  "STRIPE_SUCCESS_URL",
  "STRIPE_CANCEL_URL"
)

$workerKeys = @(
  "ENVIRONMENT",
  "SECRET_KEY",
  "DATABASE_URL",
  "REDIS_URL",
  "CELERY_BROKER_URL",
  "CELERY_RESULT_BACKEND",
  "SMTP_HOST",
  "SMTP_PORT",
  "SMTP_USERNAME",
  "SMTP_PASSWORD",
  "SMTP_FROM_EMAIL"
)

$frontendKeys = @(
  "NEXT_PUBLIC_API_BASE"
)

Apply-EnvSet -ServiceId $backend.id -Keys $backendKeys -AllVars $vars -Headers $headers
Apply-EnvSet -ServiceId $worker.id -Keys $workerKeys -AllVars $vars -Headers $headers
Apply-EnvSet -ServiceId $frontend.id -Keys $frontendKeys -AllVars $vars -Headers $headers

Write-Host "Render env vars applied successfully."
