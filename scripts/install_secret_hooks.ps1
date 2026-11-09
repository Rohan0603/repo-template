# Install repository-local fail-closed Gitleaks pre-push hook (Windows PowerShell).
$ErrorActionPreference = 'Stop'
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw 'Git is required' }
if (-not (Get-Command gitleaks -ErrorAction SilentlyContinue)) {
  throw 'Gitleaks is required. Install it first: https://github.com/gitleaks/gitleaks'
}
$root = & git rev-parse --show-toplevel
if ($LASTEXITCODE -ne 0 -or -not $root) { throw 'Run this from inside a Git repository' }
if (-not (Test-Path (Join-Path $root '.githooks/pre-push'))) { throw 'This repository has no .githooks/pre-push script' }
& git config --local core.hooksPath .githooks
if ($LASTEXITCODE -ne 0) { throw 'Failed to configure local Git hooks path' }
$current = & git config --local --get core.hooksPath
if ($current -ne '.githooks') { throw "Git hooks path did not persist: $current" }
Write-Host 'Enabled fail-closed Gitleaks pre-push hook for this clone.'
Write-Host 'Note: Git hooks are local per clone; protected GitHub Actions checks add server-side review gating.'
