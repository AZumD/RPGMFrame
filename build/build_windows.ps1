# Build RPGMFrame desktop GUI for Windows x64.
# Run from the repository root after creating a venv.
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

$py = Join-Path (Get-Location) ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
  $py = "python"
}

& $py -m pip install -e ".[gui,build]"

& $py -m PyInstaller `
  --noconfirm `
  --clean `
  --windowed `
  --name "RPGMFrame" `
  --paths "." `
  --hidden-import customtkinter `
  --hidden-import tkinterdnd2 `
  --collect-all customtkinter `
  --collect-all tkinterdnd2 `
  "app\main.py"

$release = "dist\windows\RPGMFrame"
New-Item -ItemType Directory -Force -Path $release | Out-Null
if (Test-Path "dist\RPGMFrame") {
  Copy-Item -Recurse -Force "dist\RPGMFrame\*" $release
}

$readme = @"
RPGMFrame (Windows GUI)
=======================

1. Run RPGMFrame.exe
2. Drop an RPG Maker MV/MZ folder or ZIP
3. Click Convert
4. Copy the generated *-linux-aarch64.tar.gz to your Steam Frame
5. Unpack it and run launch.sh

The converter downloads and caches an official Linux ARM64 NW.js runtime.
Native Windows conversion still needs broad real-game validation; WSL/Linux is
the currently proven development path.
"@
Set-Content -Path (Join-Path $release "README.txt") -Value $readme -Encoding UTF8

$zip = "dist\RPGMFrame-windows-x64.zip"
if (Test-Path $zip) { Remove-Item $zip -Force }
Compress-Archive -Path $release -DestinationPath $zip -CompressionLevel Optimal

Write-Host "Built: $release\RPGMFrame.exe"
Write-Host "Zip:   $zip"
