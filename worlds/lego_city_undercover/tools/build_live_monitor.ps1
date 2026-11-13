$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '../../..')).Path
$sourceRoot = Join-Path $repoRoot 'worlds/lego_city_undercover/bridge'
$pythonPath = Join-Path $repoRoot '.venv/Scripts/python.exe'
Push-Location $repoRoot
try {
    & $pythonPath -m PyInstaller --noconfirm --clean --onefile --windowed --name LCUCheckMonitor --distpath build/lego_city_undercover --workpath build/lego_city_undercover/pyinstaller --specpath build/lego_city_undercover --add-data "$sourceRoot/collection_manifest.json;." --add-data "$sourceRoot/monitor_labels.json;." --add-data "$sourceRoot/city_pickup_sources.json;." "$sourceRoot/live_monitor.py"
    if ($LASTEXITCODE -ne 0) { throw "Monitor build failed: $LASTEXITCODE" }
} finally {
    Pop-Location
}
