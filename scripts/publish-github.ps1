param(
  [Parameter(Mandatory = $true)]
  [string]$RepoName,
  [ValidateSet("public", "private")]
  [string]$Visibility = "public"
)

$ErrorActionPreference = "Stop"
$gh = "C:\Program Files\GitHub CLI\gh.exe"

if (-not (Test-Path $gh)) {
  throw "GitHub CLI not found at $gh"
}

# Ensure authenticated
& $gh auth status | Out-Null

# Rename branch to main for modern default
$branch = (git rev-parse --abbrev-ref HEAD).Trim()
if ($branch -ne "main") {
  git branch -M main
}

# Create repo, set origin, and push
& $gh repo create $RepoName --source . --$Visibility --remote origin --push

Write-Host "Published to GitHub repo: $RepoName"
