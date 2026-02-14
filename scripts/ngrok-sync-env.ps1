param(
  # Env files to update (default: repo .env + backend .env)
  [string[]]$EnvFiles = @("saas/.env", "saas/backend/.env"),
  # ngrok local API (v3+)
  [string]$NgrokApi = "http://127.0.0.1:4040/api/tunnels",
  # How long to wait for ngrok to start (seconds). Use 0 to try once.
  [int]$WaitSeconds = 120,
  # If set, keeps watching and re-applying whenever the public URL changes.
  [switch]$Watch
)

$ErrorActionPreference = "Stop"

function Get-NgrokPublicHttpsUrl([string]$api) {
  try {
    $resp = Invoke-RestMethod -UseBasicParsing -Proxy $null -Uri $api -TimeoutSec 3
  } catch {
    return $null
  }

  $tunnels = @()
  if ($resp.tunnels) { $tunnels = $resp.tunnels }
  foreach ($t in $tunnels) {
    if ($t.public_url -and $t.public_url -like "https://*") { return $t.public_url.TrimEnd("/") }
  }

  return $null
}

function Update-EnvFile([string]$path, [string]$publicUrl) {
  if (!(Test-Path $path)) { throw "Env file not found: $path" }
  $lines = Get-Content -Path $path

  function Set-Key([string[]]$src, [string]$key, [string]$value) {
    $re = "^\s*$([regex]::Escape($key))="
    $found = $false
    $out = New-Object System.Collections.Generic.List[string]
    foreach ($ln in $src) {
      if ($ln -match $re) {
        $out.Add("$key=$value")
        $found = $true
      } else {
        $out.Add($ln)
      }
    }
    if (-not $found) { $out.Add("$key=$value") }
    return ,$out.ToArray()
  }

  $updated = $lines
  $updated = Set-Key $updated "NGROK_BACKEND_URL" $publicUrl
  $updated = Set-Key $updated "NGROK_FRONTEND_URL" $publicUrl

  # Single-origin: UI + API served from the backend. Use ngrok URL as frontend URL.
  $updated = Set-Key $updated "FRONTEND_URL" $publicUrl
  $updated = Set-Key $updated "NEXT_PUBLIC_API_BASE" $publicUrl
  $updated = Set-Key $updated "BACKEND_INTERNAL_URL" $publicUrl

  # Stripe return URLs
  $updated = Set-Key $updated "STRIPE_SUCCESS_URL" "$publicUrl/app/billing"
  $updated = Set-Key $updated "STRIPE_CANCEL_URL" "$publicUrl/app/billing"

  # CORS: ensure ngrok origin is allowed if the frontend is ever served separately.
  # Keep existing list if present, but append ngrok origin if missing.
  $corsKey = "BACKEND_CORS_ORIGINS"
  $corsLine = $updated | Where-Object { $_ -match "^\s*$corsKey=" } | Select-Object -First 1
  if ($corsLine) {
    $val = $corsLine.Substring(($corsKey + "=").Length)
    if ($val -notmatch [regex]::Escape($publicUrl)) {
      # naive JSON-list append for our existing format: ["a","b"]
      $newVal = $val.Trim()
      if ($newVal.StartsWith("[")) {
        $newVal = $newVal.TrimEnd("]")
        if ($newVal.EndsWith("[")) {
          $newVal = $newVal + "`"$publicUrl`"]"
        } else {
          $newVal = $newVal + ",`"$publicUrl`"]"
        }
      } else {
        $newVal = "[`"$publicUrl`"]"
      }
      $updated = Set-Key $updated $corsKey $newVal
    }
  } else {
    $updated = Set-Key $updated $corsKey "[`"$publicUrl`"]"
  }

  Set-Content -Path $path -Value $updated -Encoding ascii
}

$last = $null
do {
  $url = $null
  if ($WaitSeconds -le 0) {
    $url = Get-NgrokPublicHttpsUrl $NgrokApi
  } else {
    $deadline = (Get-Date).AddSeconds($WaitSeconds)
    while ((Get-Date) -lt $deadline) {
      $url = Get-NgrokPublicHttpsUrl $NgrokApi
      if ($url) { break }
      Start-Sleep -Seconds 1
    }
  }

  if (-not $url) {
    throw "ngrok URL not found. Start ngrok first (it must expose port 8000), then re-run. Example: ngrok http 8000"
  }

  if ($last -ne $url) {
    foreach ($f in $EnvFiles) { Update-EnvFile $f $url }
    Write-Host "ngrok URL synced: $url"
    Write-Host ("Updated: " + ($EnvFiles -join ", "))
    $last = $url
  }

  if ($Watch) { Start-Sleep -Seconds 2 }
} while ($Watch)

