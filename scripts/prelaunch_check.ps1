$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host ""
Write-Host "=== Micro Storefront Pre-launch Check ===" -ForegroundColor Cyan
Write-Host ""

Write-Host "1. Starting backend container..." -ForegroundColor Yellow
docker compose up -d backend

Write-Host ""
Write-Host "2. Backend compile check..." -ForegroundColor Yellow
docker compose exec -T backend python -m compileall -q app alembic

Write-Host ""
Write-Host "3. Alembic current revision..." -ForegroundColor Yellow
docker compose exec -T backend alembic current

Write-Host ""
Write-Host "4. Backend healthcheck..." -ForegroundColor Yellow
$health = curl.exe --max-time 15 -fsS http://localhost:8000/health
Write-Host $health

if ($health -notmatch '"status"\s*:\s*"ok"' -or $health -notmatch '"database"\s*:\s*"ok"') {
  throw "Healthcheck did not return status ok and database ok."
}

Write-Host ""
Write-Host "5. Dashboard build..." -ForegroundColor Yellow
Push-Location "dashboard-web"
npm run build
Pop-Location

Write-Host ""
Write-Host "6. Storefront build..." -ForegroundColor Yellow
Push-Location "storefront-web"
npm run build
Pop-Location

Write-Host ""
Write-Host "7. Secret scan..." -ForegroundColor Yellow

$secretHits = Get-ChildItem -Recurse -File |
Where-Object {
  $_.FullName -notmatch "\\node_modules\\" -and
  $_.FullName -notmatch "\\.next\\" -and
  $_.FullName -notmatch "\\dist\\" -and
  $_.FullName -notmatch "\\build\\" -and
  $_.FullName -notmatch "\\__pycache__\\" -and
  $_.FullName -notmatch "\\backend\\.venv\\" -and
  $_.FullName -notmatch "\\backend\\static\\uploads\\" -and
  $_.FullName -notmatch "\\_local_backups\\" -and
  $_.FullName -notmatch "\\scripts\\prelaunch_check\.ps1$" -and
  $_.Name -notmatch "\.env$|\.env\.local$|\.bak|backup"
} |
Select-String -Pattern "sk_live_[A-Za-z0-9]+|sk_test_[A-Za-z0-9]+|pk_live_[A-Za-z0-9]+|pk_test_[A-Za-z0-9]+|password123"

if ($secretHits) {
  $secretHits | Select-Object Path, LineNumber, Line
  throw "Secret scan found possible leaked secrets."
}

Write-Host ""
Write-Host "8. Git status..." -ForegroundColor Yellow
git status --short

Write-Host ""
Write-Host "=== Pre-launch check passed ===" -ForegroundColor Green