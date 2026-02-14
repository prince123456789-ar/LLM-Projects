param(
  # Env files to update (default: repo .env + backend .env)
  [string[]]$EnvFiles = @(".env", "backend/.env"),
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

  # Google OAuth redirect URL (must match Google Console "Authorized redirect URIs")
  $updated = Set-Key $updated "GOOGLE_OAUTH_REDIRECT_URI" "$publicUrl/api/v1/auth/google/callback"

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

function Read-EnvMap([string]$path) {
  $map = @{}
  if (!(Test-Path $path)) { return $map }
  foreach ($ln in (Get-Content -Path $path)) {
    $t = $ln.Trim()
    if (-not $t) { continue }
    if ($t.StartsWith("#")) { continue }
    if ($t -notmatch "^[A-Za-z_][A-Za-z0-9_]*=") { continue }
    $idx = $t.IndexOf("=")
    if ($idx -lt 1) { continue }
    $k = $t.Substring(0, $idx)
    $v = $t.Substring($idx + 1)
    $map[$k] = $v
  }
  return $map
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
    # Ensure backend/.env isn't missing values that exist in repo .env (Google/Stripe/SMTP, etc).
    if ($EnvFiles.Count -ge 2) {
      $a = $EnvFiles[0]
      $b = $EnvFiles[1]
      if ((Test-Path $a) -and (Test-Path $b)) {
        function Set-Key-Only([string[]]$src, [string]$key, [string]$value) {
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

        $ma = Read-EnvMap $a
        $mb = Read-EnvMap $b

        $keys = New-Object System.Collections.Generic.HashSet[string]
        foreach ($k in $ma.Keys) { [void]$keys.Add($k) }
        foreach ($k in $mb.Keys) { [void]$keys.Add($k) }

        foreach ($k in $keys) {
          $va = ""
          $vb = ""
          if ($ma.ContainsKey($k)) { $va = [string]$ma[$k] }
          if ($mb.ContainsKey($k)) { $vb = [string]$mb[$k] }

          $aEmpty = (-not $va) -or ($va.Trim() -eq "")
          $bEmpty = (-not $vb) -or ($vb.Trim() -eq "")

          if ($bEmpty -and -not $aEmpty) {
            # Fill backend/.env from repo .env.
            $lines = Get-Content -Path $b
            $updated = Set-Key-Only $lines $k $va
            Set-Content -Path $b -Value $updated -Encoding ascii
          }

          if ($aEmpty -and -not $bEmpty) {
            # Fill repo .env from backend/.env (useful if user edited backend/.env directly).
            $lines = Get-Content -Path $a
            $updated = Set-Key-Only $lines $k $vb
            Set-Content -Path $a -Value $updated -Encoding ascii
          }
        }
      }
    }
    Write-Host "ngrok URL synced: $url"
    Write-Host ("Updated: " + ($EnvFiles -join ", "))
    $last = $url
  }

  if ($Watch) { Start-Sleep -Seconds 2 }
} while ($Watch)
