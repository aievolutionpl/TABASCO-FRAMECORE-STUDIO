$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')
$env:PYTHONUTF8 = '1'
foreach ($tool in @('ffmpeg', 'ffprobe')) {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) {
        throw "Brak $tool. Zainstaluj FFmpeg: winget install --id Gyan.FFmpeg --exact. Potem otwórz ponownie terminal."
    }
}
if (-not (Test-Path '.venv\Scripts\python.exe')) {
    if (Get-Command py -ErrorAction SilentlyContinue) { py -3 -m venv .venv }
    else { python -m venv .venv }
    if ($LASTEXITCODE -ne 0) { throw 'Nie udało się utworzyć środowiska. Wymagany Python 3.11+.' }
}
$python = '.venv\Scripts\python.exe'
& $python -c 'import sys; assert sys.version_info >= (3,11), "Wymagany Python 3.11+"'
if ($LASTEXITCODE -ne 0) { throw 'Wymagany Python 3.11+.' }
& $python -m pip install -r requirements.txt pytest
if ($LASTEXITCODE -ne 0) { throw 'Instalacja zależności nie powiodła się.' }
& $python -m playwright install chromium
if ($LASTEXITCODE -ne 0) { throw 'Pobranie Chromium nie powiodło się.' }
& $python -c 'from framecore.model import project; from framecore.composition import compile_project; assert "framecore" in compile_project(project())'
if ($LASTEXITCODE -ne 0) { throw 'Sprawdzenie studia nie powiodło się.' }
Write-Host 'Studio przygotowane. Uruchom: .venv\Scripts\python.exe framecore.py editor'
