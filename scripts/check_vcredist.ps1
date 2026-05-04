# SPDX-License-Identifier: MIT
# Exit 0: typical VS 2015-2022 x64 CRT DLLs exist under %WINDIR%\System32.
# Exit 1: likely missing — Paddle/PaddleOCR on Windows often needs VC++ Redistributable (x64).
# All messages are ASCII-only so this file stays safe under legacy Windows code pages.

$ErrorActionPreference = 'Stop'

$sys = Join-Path $env:WINDIR 'System32'
$required = @(
    'vcruntime140.dll',
    'vcruntime140_1.dll',
    'msvcp140.dll'
)
$missing = @()
foreach ($f in $required) {
    $p = Join-Path $sys $f
    if (-not (Test-Path -LiteralPath $p)) {
        $missing += $f
    }
}

if ($missing.Count -eq 0) {
    exit 0
}

Write-Host ''
Write-Host '[WARN] Microsoft Visual C++ 2015-2022 Redistributable (x64) DLLs not found under System32.'
Write-Host '       Paddle/PaddleOCR may fail to load native DLLs on Windows.'
Write-Host ("       Missing: " + ($missing -join ', '))
Write-Host ''
Write-Host 'Install: Visual C++ 2015-2022 Redistributable (x64)'
Write-Host '  Download: https://aka.ms/vs/17/release/vc_redist.x64.exe'
Write-Host '  winget:   winget install --id Microsoft.VCRedist.2015+.x64 -e'
Write-Host ''
Write-Host 'After install, run: service.bat init'
Write-Host 'Optional (not recommended): set SKIP_VCREDIST_CHECK=1'
Write-Host ''
exit 1
