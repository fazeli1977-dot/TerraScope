# TerraScope Desktop Setup Script (PowerShell)
# Builds a clean, self-contained project at $HOME\Desktop\TerraScope_Engine
$ErrorActionPreference = "Stop"

$src = "C:\Projects\TerraScope"
$dest = Join-Path $HOME "Desktop\TerraScope_Engine"

Write-Host "======================================================" -ForegroundColor Cyan
Write-Host " TerraScope Desktop Engine Setup" -ForegroundColor Cyan
Write-Host " Source: $src" -ForegroundColor Gray
Write-Host " Target: $dest" -ForegroundColor Gray
Write-Host "======================================================" -ForegroundColor Cyan

if (Test-Path $dest) {
    Write-Host "Removing existing target folder..." -ForegroundColor Yellow
    Remove-Item -LiteralPath $dest -Recurse -Force
}
New-Item -ItemType Directory -Path $dest | Out-Null

# Core files
$coreFiles = @(
    "server.js",
    "package.json",
    "package-lock.json",
    "requirements.txt",
    "README.md",
    ".gitignore"
)
foreach ($f in $coreFiles) {
    $p = Join-Path $src $f
    if (Test-Path $p) { Copy-Item -LiteralPath $p -Destination $dest }
}

# Core directories
$coreDirs = @("data", "frontend", "scripts", "src", "reports", "public")
foreach ($d in $coreDirs) {
    $p = Join-Path $src $d
    if (Test-Path $p) {
        Copy-Item -LiteralPath $p -Destination $dest -Recurse
    }
}

# Python venv and node modules (self-contained runtime)
Write-Host "Copying Python virtual environment (.venv)..." -ForegroundColor Yellow
Copy-Item -LiteralPath (Join-Path $src ".venv") -Destination (Join-Path $dest ".venv") -Recurse

Write-Host "Copying Node modules..." -ForegroundColor Yellow
Copy-Item -LiteralPath (Join-Path $src "node_modules") -Destination (Join-Path $dest "node_modules") -Recurse

# Create launcher
$launcher = @"
# TerraScope One-Click Launcher (PowerShell)
`$root = Split-Path -Parent `$MyInvocation.MyCommand.Path
Set-Location `$root
Write-Host "==============================================================" -ForegroundColor Cyan
Write-Host "   TerraScope | Iran Ramsar Wetlands Observatory" -ForegroundColor Cyan
Write-Host "   Starting on http://localhost:3000" -ForegroundColor Green
Write-Host "==============================================================" -ForegroundColor Cyan
Start-Process "http://localhost:3000"
node "`$root\server.js"
"@
Set-Content -LiteralPath (Join-Path $dest "Start-TerraScope.ps1") -Value $launcher -Encoding UTF8

# Remove stray outputs / caches that might have been copied
Get-ChildItem -Path $dest -Recurse -Filter "*.pyc" -ErrorAction SilentlyContinue | Remove-Item -Force
if (Test-Path (Join-Path $dest "src\\engine\\__pycache__")) { Remove-Item (Join-Path $dest "src\\engine\\__pycache__") -Recurse -Force }

Write-Host ""
Write-Host "Setup complete!" -ForegroundColor Green
Write-Host "Launch: $dest\Start-TerraScope.ps1" -ForegroundColor Green
