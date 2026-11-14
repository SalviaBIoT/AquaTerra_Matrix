<#
.SYNOPSIS
Crea accesos directos de AquaTerra Matrix en Escritorio y Menu Inicio (sin consola negra).

.PARAMETER IncluirModoWeb
Crea tambien un acceso directo adicional para abrir AquaTerra Matrix en el navegador (--web).

.PARAMETER RegistrarAutoInicioWeb
Registra el servidor local (--web sin abrir navegador) en el inicio de sesion de Windows
para que la PWA instalada en Brave/Edge responda siempre en http://127.0.0.1:8765.
#>
param(
    [switch]$IncluirModoWeb,
    [switch]$RegistrarAutoInicioWeb
)

$ErrorActionPreference = "Stop"

$Raiz = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$PythonW = Join-Path $Raiz ".venv\Scripts\pythonw.exe"
$Icono = Join-Path $Raiz "aquaterra\ui\assets\aquaterra.ico"

if (-not (Test-Path $PythonW)) {
    throw "No se encontro pythonw.exe en '$PythonW'. Verifica el entorno virtual .venv."
}

if (-not (Test-Path $Icono)) {
    Write-Host "Generando iconos oficiales de AquaTerra Matrix..." -ForegroundColor Cyan
    $Python = Join-Path $Raiz ".venv\Scripts\python.exe"
    & $Python (Join-Path $Raiz "scripts\generar_iconos.py")
}

$WshShell = New-Object -ComObject WScript.Shell

function New-AquaTerraShortcut {
    param(
        [string]$RutaLnk,
        [string]$Argumentos,
        [string]$Descripcion,
        [string]$Hotkey = ""
    )
    $dir = Split-Path -Parent $RutaLnk
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
    $sc = $WshShell.CreateShortcut($RutaLnk)
    $sc.TargetPath = $PythonW
    $sc.Arguments = $Argumentos
    $sc.WorkingDirectory = $Raiz
    $sc.IconLocation = "$Icono, 0"
    $sc.Description = $Descripcion
    $sc.WindowStyle = 1
    if ($Hotkey) {
        $sc.Hotkey = $Hotkey
    }
    $sc.Save()
    Write-Host "OK Acceso directo creado: $RutaLnk" -ForegroundColor Green
}

$Escritorio = [Environment]::GetFolderPath("Desktop")
$MenuInicio = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs"

# 1. Acceso directo nativo principal (PyWebView, sin consola negra, atajo Ctrl+Alt+A)
New-AquaTerraShortcut `
    -RutaLnk (Join-Path $Escritorio "AquaTerra Matrix.lnk") `
    -Argumentos "-m aquaterra" `
    -Descripcion "AquaTerra Matrix v6.0 · Telemetria Bio-Fisica y Control Hidraulico" `
    -Hotkey "Ctrl+Alt+A"

New-AquaTerraShortcut `
    -RutaLnk (Join-Path $MenuInicio "AquaTerra Matrix.lnk") `
    -Argumentos "-m aquaterra" `
    -Descripcion "AquaTerra Matrix v6.0 · Telemetria Bio-Fisica y Control Hidraulico"

if ($IncluirModoWeb) {
    New-AquaTerraShortcut `
        -RutaLnk (Join-Path $Escritorio "AquaTerra Matrix (Web).lnk") `
        -Argumentos "-m aquaterra --web" `
        -Descripcion "AquaTerra Matrix v6.0 · Modo Navegador / PWA (127.0.0.1:8765)"
}

if ($RegistrarAutoInicioWeb) {
    $StartupDir = [Environment]::GetFolderPath("Startup")
    New-AquaTerraShortcut `
        -RutaLnk (Join-Path $StartupDir "AquaTerra Matrix API.lnk") `
        -Argumentos "-m uvicorn aquaterra.api.app:crear_app --factory --host 127.0.0.1 --port 8765" `
        -Descripcion "Servidor local silencioso para PWA AquaTerra Matrix"
}
