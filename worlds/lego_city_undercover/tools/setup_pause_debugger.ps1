$ErrorActionPreference = 'Stop'
$lcuRepo = (Resolve-Path (Join-Path $PSScriptRoot '../../..')).Path
$lcuDebugRoot = Join-Path $lcuRepo 'build/lego_city_undercover/debugger'
New-Item -ItemType Directory -Path $lcuDebugRoot -Force | Out-Null
function Get-LcuVerifiedArchive($Name, $Url, $Digest, $Destination) {
    $lcuArchive = Join-Path $lcuDebugRoot $Name
    if (!(Test-Path -LiteralPath $lcuArchive)) {
        Invoke-WebRequest -Uri $Url -OutFile $lcuArchive
    }
    if ((Get-FileHash -LiteralPath $lcuArchive -Algorithm SHA256).Hash -ne $Digest) {
        throw "Release digest mismatch: $Name"
    }
    Expand-Archive -LiteralPath $lcuArchive -DestinationPath $Destination -Force
}
Get-LcuVerifiedArchive 'snapshot_2026-05-27_12-11.zip' 'https://github.com/x64dbg/x64dbg/releases/download/2026.05.27/snapshot_2026-05-27_12-11.zip' 'd41966dfc5b435a372798245300ca0ab7bb8e48bdbf48512c6fb20fcca427697' (Join-Path $lcuDebugRoot 'x64dbg')
Get-LcuVerifiedArchive 'release64-0.8.1.zip' 'https://github.com/dariushoule/x64dbg-automate/releases/download/v0.8.1-ghost_fungus/release64-0.8.1-ghost_fungus.zip' '942cd81d2dd02141deacb848846b8a8a26b5f4de1731142a4df6f44581b0597b' (Join-Path $lcuDebugRoot 'plugin')
$lcuPlugins = Join-Path $lcuDebugRoot 'x64dbg/release/x64/plugins'
New-Item -ItemType Directory -Path $lcuPlugins -Force | Out-Null
Copy-Item -Path (Join-Path $lcuDebugRoot 'plugin/Release/*') -Destination $lcuPlugins
$lcuPython = Join-Path $lcuDebugRoot 'python/Scripts/python.exe'
if (!(Test-Path -LiteralPath $lcuPython)) {
    & (Join-Path $lcuRepo '.venv/Scripts/python.exe') -m venv (Join-Path $lcuDebugRoot 'python')
    if ($LASTEXITCODE -ne 0) { throw 'Debugger venv creation failed' }
}
& $lcuPython -m pip install x64dbg-automate==0.9.2
if ($LASTEXITCODE -ne 0) { throw 'Automation client installation failed' }
Write-Output "Ready: $(Join-Path $lcuDebugRoot 'x64dbg/release/x64/x64dbg.exe')"
