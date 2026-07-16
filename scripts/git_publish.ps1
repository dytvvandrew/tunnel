param(
  [Parameter(Mandatory = $true)]
  [string]$RemoteUrl,
  [string]$Branch = "main",
  [string]$Message = "Prepare tunnel platform migration package",
  [string]$GitUserName = "",
  [string]$GitUserEmail = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Push-Location (Split-Path -Parent $PSScriptRoot)
try {
  if (!(Test-Path ".git")) {
    git init
  }
  if ($GitUserName) {
    git config user.name $GitUserName
  }
  if ($GitUserEmail) {
    git config user.email $GitUserEmail
  }
  if (!(git config user.name)) {
    git config user.name "Tunnel Platform"
  }
  if (!(git config user.email)) {
    git config user.email "tunnel-platform@example.local"
  }
  git branch -M $Branch
  git add .
  $changes = git status --short
  if ($changes) {
    git commit -m $Message
  } else {
    Write-Host "No local changes to commit."
  }
  if ((git remote) -notcontains "origin") {
    git remote add origin $RemoteUrl
  } else {
    git remote set-url origin $RemoteUrl
  }
  git push -u origin $Branch
}
finally {
  Pop-Location
}
