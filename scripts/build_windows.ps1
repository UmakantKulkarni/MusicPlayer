$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')
if (!(Test-Path '.venv/Scripts/python.exe')) {
    py -3.12 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Install Python 3.12 (64-bit) from python.org, then retry.' }
}
$python = '.venv/Scripts/python.exe'
& $python -m pip install -r requirements-build.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
& $python -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw 'Tests failed' }
& $python -m PyInstaller --noconfirm --clean MusicPlayer.spec
if ($LASTEXITCODE -ne 0) { throw 'Build failed' }
Write-Host 'Ready: dist/MusicPlayer.exe'
& $python scripts/package_release.py
if ($LASTEXITCODE -ne 0) { throw 'Distribution packaging failed' }
