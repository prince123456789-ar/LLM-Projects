param(
  [string]$BaseUrl = "http://127.0.0.1:8000"
)

$ErrorActionPreference = "Stop"

function Invoke-Json($Method, $Url, $Headers, $BodyObj) {
  $body = $null
  if ($BodyObj -ne $null) { $body = ($BodyObj | ConvertTo-Json -Depth 8) }
  try {
    $resp = Invoke-WebRequest -Method $Method -Uri $Url -Headers $Headers -ContentType "application/json" -Body $body -UseBasicParsing
    $json = $null
    try { $json = $resp.Content | ConvertFrom-Json } catch { $json = $resp.Content }
    return @{ ok = $true; status = [int]$resp.StatusCode; json = $json }
  } catch {
    $r = $_.Exception.Response
    $status = 0
    $content = ""
    if ($r -and $r.StatusCode) { $status = [int]$r.StatusCode }
    try {
      $sr = New-Object System.IO.StreamReader($r.GetResponseStream())
      $content = $sr.ReadToEnd()
    } catch {}
    $json = $null
    try { $json = $content | ConvertFrom-Json } catch { $json = @{ detail = $content } }
    return @{ ok = $false; status = $status; json = $json }
  }
}

function Invoke-Form($Url, $Headers, $Form) {
  # Use a plain hashtable so Windows PowerShell sends it as x-www-form-urlencoded.
  $body = @{}
  foreach ($k in $Form.Keys) { $body[$k] = $Form[$k] }
  try {
    $resp = Invoke-WebRequest -Method POST -Uri $Url -Headers $Headers -Body $body -ContentType "application/x-www-form-urlencoded" -UseBasicParsing
    $json = $null
    try { $json = $resp.Content | ConvertFrom-Json } catch { $json = $resp.Content }
    return @{ ok = $true; status = [int]$resp.StatusCode; json = $json }
  } catch {
    $r = $_.Exception.Response
    $status = 0
    $content = ""
    if ($r -and $r.StatusCode) { $status = [int]$r.StatusCode }
    try {
      $sr = New-Object System.IO.StreamReader($r.GetResponseStream())
      $content = $sr.ReadToEnd()
    } catch {}
    $json = $null
    try { $json = $content | ConvertFrom-Json } catch { $json = @{ detail = $content } }
    return @{ ok = $false; status = $status; json = $json }
  }
}

function Show-Result($Name, $Res) {
  $ok = $Res.ok
  $status = $Res.status
  $detail = ""
  if ($Res.json -and $Res.json.detail) { $detail = $Res.json.detail }
  $flag = "FAIL"
  if ($ok) { $flag = "OK" }
  Write-Host ("[{0}] {1} (HTTP {2}) {3}" -f $flag, $Name, $status, $detail)
}

$deviceId = ([guid]::NewGuid()).ToString()
$now = Get-Date
$email = ("smoke+" + $now.ToString("yyyyMMddHHmmss") + "@example.com")
$password = "S0lid!Passw0rd-" + $now.ToString("HHmmss") + "Aa#"

Write-Host "BaseUrl: $BaseUrl"
Write-Host "DeviceId: $deviceId"
Write-Host "Email: $email"

# Register (public signup must be enabled).
$reg = Invoke-Json "POST" "$BaseUrl/api/v1/auth/register" @{} @{
  full_name = "Smoke Test"
  email = $email
  password = $password
  role = "manager"
}
Show-Result "auth/register" $reg

# Login
$login = Invoke-Form "$BaseUrl/api/v1/auth/login" @{ "x-device-id" = $deviceId } @{
  username = $email
  password = $password
}
Show-Result "auth/login" $login
if (-not $login.ok) { throw "Login failed; cannot continue smoke test." }

$access = $login.json.access_token
$authH = @{
  "Authorization" = ("Bearer " + $access)
  "x-device-id" = $deviceId
}

# Me
$me = $null
try {
  $resp = Invoke-WebRequest -Method GET -Uri "$BaseUrl/api/v1/auth/me" -Headers $authH -UseBasicParsing
  $me = $resp.Content | ConvertFrom-Json
  Write-Host ("[OK] auth/me role=" + $me.role)
} catch {
  Write-Host "[FAIL] auth/me"
}

# Create lead
$lead = Invoke-Json "POST" "$BaseUrl/api/v1/leads" $authH @{
  full_name = "Website Lead"
  email = $email
  phone = "0000000000"
  channel = "website_chat"
  location = "Downtown"
  property_type = "apartment"
  budget = 250000
  timeline = "30 days"
}
Show-Result "leads:create" $lead

# Analytics
try {
  $resp = Invoke-WebRequest -Method GET -Uri "$BaseUrl/api/v1/analytics/dashboard" -Headers $authH -UseBasicParsing
  $json = $resp.Content | ConvertFrom-Json
  Write-Host ("[OK] analytics/dashboard total_leads=" + $json.total_leads)
} catch {
  Write-Host "[FAIL] analytics/dashboard"
}

try {
  $resp = Invoke-WebRequest -Method GET -Uri "$BaseUrl/api/v1/analytics/timeseries?days=14" -Headers $authH -UseBasicParsing
  $json = $resp.Content | ConvertFrom-Json
  Write-Host ("[OK] analytics/timeseries points=" + ($json | Measure-Object).Count)
} catch {
  Write-Host "[FAIL] analytics/timeseries"
}

# Embed key + ingest
try {
  $resp = Invoke-WebRequest -Method GET -Uri "$BaseUrl/api/v1/embed/keys/primary" -Headers $authH -UseBasicParsing
  $ek = $resp.Content | ConvertFrom-Json
  Write-Host ("[OK] embed/keys/primary masked=" + $ek.masked_key)
  $u = [System.Uri]$ek.install_script_url
  try { Add-Type -AssemblyName System.Web -ErrorAction SilentlyContinue } catch {}
  $qs = [System.Web.HttpUtility]::ParseQueryString($u.Query)
  $k = $qs.Get("key")
  if ($k) {
    $embed = Invoke-Json "POST" "$BaseUrl/api/v1/embed/leads?key=$([uri]::EscapeDataString($k))" @{ "Origin" = "https://example.com" } @{
      full_name = "Embed Lead"
      email = $email
      message = "Hello from widget"
      page_url = "https://example.com/listing/1"
      referrer = "https://example.com/"
    }
    Show-Result "embed/leads" $embed
  } else {
    Write-Host "[FAIL] embed/leads missing key"
  }
} catch {
  Write-Host "[FAIL] embed flow"
}

# Forgot password (dev response may include debug_reset_url)
$forgot = Invoke-Json "POST" "$BaseUrl/api/v1/password/forgot" @{} @{ email = $email }
Show-Result "password/forgot" $forgot
if ($forgot.ok -and $forgot.json.debug_reset_url) {
  Write-Host ("[OK] debug_reset_url=" + $forgot.json.debug_reset_url)
}

# Billing status + checkout (may fail if Stripe not configured)
try {
  $resp = Invoke-WebRequest -Method GET -Uri "$BaseUrl/api/v1/billing/status" -Headers $authH -UseBasicParsing
  $b = $resp.Content | ConvertFrom-Json
  Write-Host ("[OK] billing/status plan=" + $b.plan + " status=" + $b.status)
} catch {
  Write-Host "[FAIL] billing/status"
}

$checkout = Invoke-Json "POST" "$BaseUrl/api/v1/billing/checkout?plan=agency" $authH $null
Show-Result "billing/checkout" $checkout

Write-Host ""
Write-Host "Smoke test complete."
