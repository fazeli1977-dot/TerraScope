# TerraScope One-Click Launcher (PowerShell)
Set-Location "C:\Projects\TerraScope"
Write-Host "==============================================================" -ForegroundColor Cyan
Write-Host "   TerraScope | ???????? ????????? ????? ?? ????????? ?????" -ForegroundColor Cyan
Write-Host "   Starting High-Speed Local Observatory on http://localhost:3000" -ForegroundColor Green
Write-Host "==============================================================" -ForegroundColor Cyan
Start-Process "http://localhost:3000"
node "C:\Projects\TerraScope\server.js"
