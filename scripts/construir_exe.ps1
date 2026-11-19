<#
.SYNOPSIS
Empaqueta SalviaBIoT como ejecutable standalone de Windows (.exe) mediante PyInstaller.
#>
$ErrorActionPreference = "Stop"

$Raiz = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $Raiz

$Python = Join-Path $Raiz ".venv\Scripts\python.exe"
$Icono = Join-Path $Raiz "aquaterra\ui\assets\salviabiot.ico"
$FrontendDir = Join-Path $Raiz "frontend"

# 1. Asegurar iconos y build fresco de frontend/dist
& $Python (Join-Path $Raiz "scripts\generar_iconos.py")

Push-Location $FrontendDir
try {
    if (Test-Path "C:\Program Files\nodejs") {
        $env:Path = "C:\Program Files\nodejs;" + $env:Path
    }
    npm.cmd run build
} finally {
    Pop-Location
}

# 2. Verificar PyInstaller en .venv
& $Python -c "import PyInstaller" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Instalando PyInstaller en .venv..." -ForegroundColor Yellow
    & $Python -m pip install pyinstaller
}

# 3. Construir paquete --onedir (arranque rapido y compatible con SQLite WAL en carpeta local)
& $Python -m PyInstaller `
    --noconfirm `
    --clean `
    --onedir `
    --noconsole `
    --name "SalviaBIoT" `
    --icon "$Icono" `
    --add-data "frontend/dist;frontend/dist" `
    --add-data "aquaterra/ui/assets;aquaterra/ui/assets" `
    --collect-all "webview" `
    --collect-all "uvicorn" `
    --collect-all "fastapi" `
    main.py

Write-Host ""
Write-Host "Build finalizado: $Raiz\dist\SalviaBIoT\SalviaBIoT.exe" -ForegroundColor Green
