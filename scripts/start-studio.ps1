$ErrorActionPreference = 'Stop'
$studioRoot = Split-Path $PSScriptRoot -Parent
$studioPython = Join-Path $studioRoot '.venv\Scripts\python.exe'
$studioUrl = 'http://127.0.0.1:8877/'
if (-not (Test-Path -LiteralPath $studioPython)) { throw 'Brak srodowiska Python. Uruchom scripts/install-local.ps1.' }
function Test-Studio {
    try { return (Invoke-WebRequest -Uri $studioUrl -UseBasicParsing -TimeoutSec 2).StatusCode -eq 200 } catch { return $false }
}
if (-not (Test-Studio)) {
    Start-Process -FilePath $studioPython -ArgumentList 'framecore.py','editor' -WorkingDirectory $studioRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $studioRoot 'framecore-local.log') -RedirectStandardError (Join-Path $studioRoot 'framecore-local-error.log')
    for ($attempt = 0; $attempt -lt 20; $attempt++) {
        Start-Sleep -Milliseconds 500
        if (Test-Studio) { break }
    }
}
if (-not (Test-Studio)) { throw 'Studio nie wystartowalo. Sprawdz framecore-local-error.log.' }
Start-Process $studioUrl
Write-Host "Studio dziala: $studioUrl"
