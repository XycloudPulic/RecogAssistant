# SPDX-License-Identifier: MIT
# Used by service.bat: start backend/frontend (no redirect to logs/app.log — avoids lock with RotatingFileHandler).

param(
    [Parameter(Mandatory)][string]$Root,
    [Parameter(Mandatory)][string]$PidFile,
    [Parameter(Mandatory)][ValidateSet('backend', 'frontend')][string]$Mode,
    [Parameter(Mandatory)][string]$PyExe,
    [string]$PyExtra = ''
)

$env:PYTHONPATH = Join-Path $Root 'src'
$env:PYTHONUNBUFFERED = '1'

$pre = @()
if ($PyExtra -and $PyExtra.Trim()) {
    $pre = @($PyExtra.Trim())
}

if ($Mode -eq 'backend') {
    $tail = @('-u', '-m', 'uvicorn', 'recognizer.interfaces.api.app:app', '--host', '127.0.0.1', '--port', '8000')
}
else {
    $app = Join-Path $Root 'src\recognizer\interfaces\web\app.py'
    $tail = @('-u', '-m', 'streamlit', 'run', $app, '--server.port', '8501', '--server.headless', 'true', '--browser.gatherUsageStats', 'false')
}

$argv = $pre + $tail

function Quote-CmdArg([string]$a) {
    if ($a -match '[\s"&|<>^]') {
        '"' + ($a -replace '"', '""') + '"'
    }
    else {
        $a
    }
}

$quotedExe = Quote-CmdArg $PyExe
$quotedArgs = ($argv | ForEach-Object { Quote-CmdArg $_ }) -join ' '
$pp = Quote-CmdArg $env:PYTHONPATH

# Do not redirect stdout/stderr to logs/app.log here: Python's RotatingFileHandler opens
# the same file and Windows returns Permission denied. App logging goes via logging.setup only.
$cmdInner = "set PYTHONPATH=$pp&& set PYTHONUNBUFFERED=1&& call $quotedExe $quotedArgs"

$p = Start-Process -FilePath cmd.exe -ArgumentList @('/c', $cmdInner) -WorkingDirectory $Root -WindowStyle Hidden -PassThru
[System.IO.File]::WriteAllText($PidFile, [string]$p.Id)
