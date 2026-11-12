# Instala NeuroDAC sin uv, solo con Python y pip. Pensado para una computadora
# prestada en una demostracion.
#
# Uso, desde la raiz del repositorio:
#
#   powershell -ExecutionPolicy Bypass -File tools\instalar_sin_uv.ps1
#
# Sin internet en la computadora prestada:
#   1. En una maquina con internet:
#        powershell -ExecutionPolicy Bypass -File tools\instalar_sin_uv.ps1 -DescargarPaquetes
#      Deja las ruedas en paquetes\ (unos 106 MB). Usa -VersionDestino 3.13 si la
#      computadora prestada tiene Python 3.13; las ruedas son de version exacta.
#   2. Copia la carpeta NeuroDAC completa, con paquetes\, a la computadora prestada.
#   3. Ahi:
#        powershell -ExecutionPolicy Bypass -File tools\instalar_sin_uv.ps1 -SinInternet
#
# Despues, para arrancar: doble clic en iniciar_neurodac.bat
#
# Instala NeuroDAC en modo editable a proposito: content.py ubica content\
# relativo al codigo fuente, y una instalacion normal lo copiaria a
# site-packages, donde la aplicacion ya no encontraria su contenido.

[CmdletBinding()]
param(
    [switch]$SinInternet,
    [switch]$DescargarPaquetes,
    [string]$Python = '',
    [string]$VersionDestino = '3.12',
    [string]$Plataforma = 'win_amd64'
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

# Sonda de codificacion. Este script va en UTF-8 con BOM; sin el BOM,
# PowerShell 5.1 lo lee como ANSI y la enie se parte en dos caracteres.
$sonda = 'ñ'
if ($sonda.Length -ne 1) {
    throw 'El script perdio su BOM y se leyo como ANSI. Vuelve a descargarlo sin abrirlo en un editor.'
}

function Stop-Instalacion([string]$Mensaje) {
    Write-Host ''
    Write-Host $Mensaje -ForegroundColor Red
    exit 1
}

function Write-Paso([string]$Mensaje) {
    Write-Host ''
    Write-Host "-> $Mensaje" -ForegroundColor Cyan
}

# Corre un programa externo y lo juzga por su codigo de salida. Con la
# preferencia en Stop, Windows PowerShell 5.1 convierte en excepcion cualquier
# linea que el programa escriba en su salida de error, y pip escribe avisos ahi
# de rutina: el instalador moriria por un aviso.
#
# La salida va a la consola con Out-Host: una funcion de PowerShell devuelve
# todo lo que sus comandos escriben, y sin esto el codigo de salida llegaria
# mezclado con las lineas de pip y cualquier aviso se leeria como falla.
function Invoke-Externo([string]$Exe, [string[]]$Argumentos) {
    $previa = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        & $Exe @Argumentos | Out-Host
        return $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previa
    }
}

# Version de un Python como entero (312 para 3.12), o 0 si no sirve.
function Get-VersionPython([string]$Exe, [string[]]$Prefijo) {
    $previa = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $codigo = 'import sys; print(sys.version_info[0] * 100 + sys.version_info[1])'
        $salida = & $Exe @Prefijo -c $codigo 2>$null
        if ($LASTEXITCODE -ne 0) { return 0 }
        return [int]("$salida".Trim())
    }
    catch {
        return 0
    }
    finally {
        $ErrorActionPreference = $previa
    }
}

$esWindows = [System.Environment]::OSVersion.Platform -eq 'Win32NT'
$raiz = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).ProviderPath
$pyproject = Join-Path $raiz 'pyproject.toml'
if (-not (Test-Path -LiteralPath $pyproject) -or
    -not (Select-String -LiteralPath $pyproject -Pattern '^\s*name\s*=\s*"neurodac"' -Quiet)) {
    Stop-Instalacion "No encuentro el pyproject.toml de NeuroDAC en $raiz."
}
$requisitos = Join-Path $raiz 'requirements-demo.txt'
if (-not (Test-Path -LiteralPath $requisitos)) {
    Stop-Instalacion "Falta requirements-demo.txt en $raiz."
}
$paquetes = Join-Path $raiz 'paquetes'

# --------------------------------------------------------------- Python
Write-Paso 'Buscando Python 3.12 o posterior'
$candidatos = @()
if ($Python) {
    $candidatos += , @($Python, @())
}
else {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        foreach ($v in @('-3.12', '-3.13', '-3.14', '-3')) { $candidatos += , @('py', @($v)) }
    }
    foreach ($nombre in @('python', 'python3')) {
        if (Get-Command $nombre -ErrorAction SilentlyContinue) { $candidatos += , @($nombre, @()) }
    }
}
$py = $null
$pyPrefijo = @()
$version = 0
foreach ($c in $candidatos) {
    $v = Get-VersionPython $c[0] $c[1]
    if ($v -ge 312) {
        $py = $c[0]
        $pyPrefijo = $c[1]
        $version = $v
        break
    }
}
if (-not $py) {
    Stop-Instalacion ("No encontre Python 3.12 o posterior. Instalalo desde python.org " +
        "o con: winget install Python.Python.3.12  y vuelve a correr este script.")
}
$versionTexto = '{0}.{1}' -f [math]::Floor($version / 100), ($version % 100)
Write-Host "   Python $versionTexto  ($py $($pyPrefijo -join ' '))"

# ------------------------------------------------ descargar paquetes
if ($DescargarPaquetes) {
    Write-Paso "Descargando paquetes para Python $VersionDestino en $Plataforma"
    New-Item -ItemType Directory -Force -Path $paquetes | Out-Null
    # La carpeta se ignora a si misma: son ~106 MB que no deben entrar al
    # repositorio, y el .gitignore de la plantilla no se toca.
    Set-Content -LiteralPath (Join-Path $paquetes '.gitignore') -Value '*' -Encoding ascii
    # hatchling construye NeuroDAC, y en modo editable pide ademas `editables`
    # durante la construccion: con internet llega solo, sin internet no.
    $argumentos = @('-m', 'pip', 'download', '-r', $requisitos, 'hatchling', 'editables', '-d', $paquetes,
        '--only-binary=:all:')
    if ($Plataforma -ne 'actual') {
        $argumentos += @('--platform', $Plataforma, '--python-version', $VersionDestino, '--implementation', 'cp')
        $destino = $VersionDestino
    }
    else {
        $destino = $versionTexto
    }
    if ((Invoke-Externo $py ($pyPrefijo + $argumentos)) -ne 0) {
        Stop-Instalacion 'La descarga fallo. Revisa la conexion y vuelve a intentar.'
    }
    Set-Content -LiteralPath (Join-Path $paquetes 'VERSION.txt') -Value $destino -Encoding ascii
    $n = @(Get-ChildItem -LiteralPath $paquetes -Filter '*.whl').Count
    Write-Host ''
    Write-Host "Listo: $n paquetes para Python $destino en paquetes\" -ForegroundColor Green
    Write-Host 'Copia la carpeta NeuroDAC completa, con paquetes\, y en la otra computadora corre:'
    Write-Host '  powershell -ExecutionPolicy Bypass -File tools\instalar_sin_uv.ps1 -SinInternet'
    exit 0
}

# ------------------------------------------------------- instalar
$fuente = @()
if ($SinInternet) {
    $marca = Join-Path $paquetes 'VERSION.txt'
    if (-not (Test-Path -LiteralPath $marca)) {
        Stop-Instalacion ("No encuentro paquetes\. Primero corre este script con -DescargarPaquetes " +
            'en una maquina con internet y copia la carpeta.')
    }
    $esperada = (Get-Content -LiteralPath $marca -Raw).Trim()
    # Las ruedas compiladas son de version exacta: numpy para 3.12 no sirve en 3.13.
    if ($esperada -ne $versionTexto) {
        Stop-Instalacion ("Los paquetes son para Python $esperada y esta computadora tiene $versionTexto. " +
            "Descargalos de nuevo con -VersionDestino $versionTexto, o instala Python $esperada.")
    }
    $fuente = @('--no-index', '--find-links', $paquetes)
}

$venv = Join-Path $raiz '.venv'
if ($esWindows) { $vpy = Join-Path $venv 'Scripts\python.exe' } else { $vpy = Join-Path $venv 'bin/python' }

Write-Paso 'Entorno virtual .venv'
if (-not (Test-Path -LiteralPath $vpy)) {
    if ((Invoke-Externo $py ($pyPrefijo + @('-m', 'venv', $venv))) -ne 0) {
        Stop-Instalacion 'No se pudo crear el entorno virtual.'
    }
    Write-Host '   creado'
}
else {
    Write-Host '   ya existia; se reutiliza'
}

Write-Paso 'Instalando dependencias (requirements-demo.txt)'
if ((Invoke-Externo $vpy (@('-m', 'pip', 'install', '--disable-pip-version-check', '-r', $requisitos) + $fuente)) -ne 0) {
    Stop-Instalacion 'Fallo la instalacion de dependencias. El mensaje de pip de arriba dice cual.'
}

Write-Paso 'Instalando NeuroDAC en modo editable'
if ((Invoke-Externo $vpy (@('-m', 'pip', 'install', '--disable-pip-version-check', '--no-deps', '-e', $raiz) + $fuente)) -ne 0) {
    Stop-Instalacion 'Fallo la instalacion de NeuroDAC.'
}

Write-Paso 'Verificando'
$prueba = 'import dash, mne, serial; from neurodac import content; content.content(); print("   todo importa y el contenido carga")'
if ((Invoke-Externo $vpy @('-c', $prueba)) -ne 0) {
    Stop-Instalacion 'La verificacion fallo: la instalacion quedo incompleta.'
}

Write-Host ''
Write-Host 'Listo.' -ForegroundColor Green
Write-Host '  Para arrancar: doble clic en iniciar_neurodac.bat'
Write-Host "  o:             $vpy interfaz.py"
$demo = Join-Path $raiz 'data\processed\demo_eeg.csv'
if (-not (Test-Path -LiteralPath $demo)) {
    Write-Host ''
    Write-Host 'Falta el registro de demostracion para la pagina de Grafica:' -ForegroundColor Yellow
    Write-Host "  $vpy tools\preparar_datos.py"
}
