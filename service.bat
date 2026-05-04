@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM Portable service launcher (copy folder anywhere).
REM   service.bat init   — pip + DB DDL/DML + VC++ runtime probe ^(Paddle^) + optional Paddle warm-up ^(yaml: ocr.prefetch_on_init^)
REM   service.bat start  — start API :8000 + Streamlit :8501 (no pip)
REM   service.bat stop   — stop both
REM   service.bat clear  — stop + remove DB/logs/.service state under project root only (no pip uninstall)

cd /d "%~dp0"
set "ROOT=%CD%"
set "LOGDIR=%ROOT%\logs"
set "APP_LOG=%LOGDIR%\app.log"
set "SVC_LOG_PATH=%APP_LOG%"
set "STATEDIR=%ROOT%\.service"
set "BACKEND_PID=%STATEDIR%\backend.pid"
set "FRONTEND_PID=%STATEDIR%\frontend.pid"
set "SPAWN_PS=%ROOT%\scripts\service_spawn.ps1"
set "PYTHONPATH=%ROOT%\src"

if not defined PIP_INDEX set "PIP_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple"
set "PIP_FALLBACK=https://pypi.org/simple"

if "%~1"=="" goto :usage
if /I "%~1"=="init" goto :init
if /I "%~1"=="start" goto :start
if /I "%~1"=="stop" goto :stop
if /I "%~1"=="clear" goto :clear
goto :usage

:svc_log
set "_SVC_MSG=%*"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$p=$env:SVC_LOG_PATH; $m=$env:_SVC_MSG; $line=('[{0}] [service] {1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $m); for ($i=0; $i -lt 160; $i++) { try { $fs=[System.IO.File]::Open($p,[System.IO.FileMode]::Append,[System.IO.FileAccess]::Write,[System.IO.FileShare]::ReadWrite); $sw=New-Object System.IO.StreamWriter($fs,[System.Text.UTF8Encoding]::new($false)); $sw.WriteLine($line); $sw.Flush(); $sw.Dispose(); $fs.Dispose(); exit 0 } catch { Start-Sleep -Milliseconds 25 } }; exit 1"
set "_SVC_MSG="
exit /b 0

:stop
call :ensure_dirs
call :svc_log "stop: begin"
echo Stopping services...
call :kill_by_pidfiles
call :kill_by_ports
call :svc_log "stop: done"
echo Done.
exit /b 0

:clear
call :ensure_dirs
call :svc_log "clear: begin"
echo Clear: stopping services...
call :kill_by_pidfiles
call :kill_by_ports
timeout /t 1 /nobreak >nul 2>nul
echo Clear: removing project-local runtime files ^(database, Paddle OCR model dirs under config, logs, .service — not pip packages^)...
call :resolve_python
if errorlevel 1 exit /b 1
call "!SVC_PY_EXE!" !SVC_PY_EXTRA! -m recognizer.infrastructure.local_runtime.clear_local_runtime
if errorlevel 1 (
  call :svc_log "[ERROR] clear db step failed"
  echo [ERROR] clear failed ^(database step^).
  exit /b 1
)
if exist "%LOGDIR%" del /f /q "%LOGDIR%\*.*" >nul 2>nul
if exist "%STATEDIR%" del /f /q "%STATEDIR%\*.*" >nul 2>nul
if exist "%ROOT%\test_seed.db" del /f /q "%ROOT%\test_seed.db" >nul 2>nul
call :svc_log "clear: done"
echo Clear complete. Next: service.bat init
exit /b 0

:init
call :ensure_dirs
call :svc_log "init: begin"
set "VCREDIST_MISSING=0"
call :resolve_python
if errorlevel 1 exit /b 1
call :pip_install
if errorlevel 1 exit /b 1
echo Initializing database ^(data\db\scripts^)...
call "!SVC_PY_EXE!" !SVC_PY_EXTRA! -m recognizer.infrastructure.local_runtime.initial_bootstrap
if errorlevel 1 (
  call :svc_log "[ERROR] database init failed"
  echo [ERROR] Database initialization failed.
  exit /b 1
)

call :check_vcredist_for_paddle

echo PaddleOCR warm-up ^(ocr.prefetch_on_init in settings.yaml^)...
if "!VCREDIST_MISSING!"=="1" (
  call :svc_log "[SKIP] Paddle warm-up skipped ^(VC++ runtime check failed^)"
  echo [SKIP] Paddle warm-up skipped: install Microsoft VC++ 2015-2022 x64 Redistributable first, then re-run init.
  echo         https://aka.ms/vs/17/release/vc_redist.x64.exe
) else (
  call "!SVC_PY_EXE!" !SVC_PY_EXTRA! -m recognizer.infrastructure.ocr.warm_paddle
  if errorlevel 1 (
    call :svc_log "[WARN] PaddleOCR warm-up during init failed"
    echo [WARN] Paddle warm-up failed ^(VC++ runtime / offline / network^). See logs\app.log
  )
)

call :svc_log "init: done"
echo Init complete. Run: service.bat start
exit /b 0

:start
call :ensure_dirs
call :svc_log "start: begin"
echo Stopping existing listeners...
call :kill_by_pidfiles
call :kill_by_ports
timeout /t 1 /nobreak >nul 2>nul
echo Done.

call :resolve_python
if errorlevel 1 exit /b 1

if not exist "%SPAWN_PS%" (
  echo [ERROR] Missing "%SPAWN_PS%"
  exit /b 1
)

REM 后端已默认不在启动时阻塞加载 Paddle（见 settings.yaml ocr.prefetch_on_startup）；仅轮询端口是否监听；若仍将预载开在 startup 可 set SVC_BACKEND_WAIT_SEC=300
if not defined SVC_BACKEND_WAIT_SEC set "SVC_BACKEND_WAIT_SEC=45"

call :svc_log "start: backend :8000"
echo Starting backend (8000)...
powershell -NoProfile -ExecutionPolicy Bypass -File "%SPAWN_PS%" -Root "%ROOT%" -PidFile "%BACKEND_PID%" -Mode backend -PyExe "!SVC_PY_EXE!" -PyExtra "!SVC_PY_EXTRA!"

echo Waiting for backend :8000 ^(max %SVC_BACKEND_WAIT_SEC%s^)...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$port=8000; $timeout=[int]$env:SVC_BACKEND_WAIT_SEC; $sw=[Diagnostics.Stopwatch]::StartNew(); while ($sw.Elapsed.TotalSeconds -lt $timeout) { $c=Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue; if ($c) { exit 0 }; Start-Sleep -Milliseconds 300 }; exit 1" >nul 2>nul
if errorlevel 1 (
  call :svc_log "[ERROR] backend not listening"
  echo [ERROR] Backend failed ^(8000^). See "%APP_LOG%"
  call :kill_by_pidfiles
  call :kill_by_ports
  exit /b 1
)

call :svc_log "start: frontend :8501"
echo Starting frontend (8501)...
powershell -NoProfile -ExecutionPolicy Bypass -File "%SPAWN_PS%" -Root "%ROOT%" -PidFile "%FRONTEND_PID%" -Mode frontend -PyExe "!SVC_PY_EXE!" -PyExtra "!SVC_PY_EXTRA!"

powershell -NoProfile -ExecutionPolicy Bypass -Command "$port=8501; $timeout=45; $sw=[Diagnostics.Stopwatch]::StartNew(); while ($sw.Elapsed.TotalSeconds -lt $timeout) { $c=Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue; if ($c) { exit 0 }; Start-Sleep -Milliseconds 300 }; exit 1" >nul 2>nul
if errorlevel 1 (
  call :svc_log "[ERROR] frontend not listening"
  echo [ERROR] Frontend failed ^(8501^). See "%APP_LOG%"
  call :kill_by_pidfiles
  call :kill_by_ports
  exit /b 1
)

echo.
echo Service started.
echo   Frontend: http://127.0.0.1:8501
echo   API Docs: http://127.0.0.1:8000/docs
echo   Log file: "%APP_LOG%"
echo   Stop: service.bat stop
echo.
exit /b 0

:pip_install
echo Installing python dependencies...
if "!SVC_PY_EXTRA!"=="" (
  call "!SVC_PY_EXE!" -m pip install --user -r "%ROOT%\requirements.txt" -i "%PIP_INDEX%"
) else (
  call "!SVC_PY_EXE!" !SVC_PY_EXTRA! -m pip install --user -r "%ROOT%\requirements.txt" -i "%PIP_INDEX%"
)
if errorlevel 1 (
  echo [WARN] Mirror failed, retrying PyPI...
  if "!SVC_PY_EXTRA!"=="" (
    call "!SVC_PY_EXE!" -m pip install --user -r "%ROOT%\requirements.txt" -i "%PIP_FALLBACK%"
  ) else (
    call "!SVC_PY_EXE!" !SVC_PY_EXTRA! -m pip install --user -r "%ROOT%\requirements.txt" -i "%PIP_FALLBACK%"
  )
)
if errorlevel 1 (
  echo [ERROR] pip install failed.
  exit /b 1
)
exit /b 0

:ensure_dirs
if not exist "%LOGDIR%" mkdir "%LOGDIR%" >nul 2>nul
if not exist "%STATEDIR%" mkdir "%STATEDIR%" >nul 2>nul
exit /b 0

:kill_by_pidfiles
if exist "%BACKEND_PID%" (
  for /f "usebackq delims=" %%P in ("%BACKEND_PID%") do taskkill /F /T /PID %%P >nul 2>nul
  del /q "%BACKEND_PID%" >nul 2>nul
)
if exist "%FRONTEND_PID%" (
  for /f "usebackq delims=" %%P in ("%FRONTEND_PID%") do taskkill /F /T /PID %%P >nul 2>nul
  del /q "%FRONTEND_PID%" >nul 2>nul
)
exit /b 0

:kill_by_ports
powershell -NoProfile -ExecutionPolicy Bypass -Command "foreach ($port in 8000,8501) { Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue } }" >nul 2>nul
exit /b 0

:resolve_python
set "SVC_PY_EXE="
set "SVC_PY_EXTRA="
where py >nul 2>nul
if not errorlevel 1 (
  py -3.10 -c "import sys; assert sys.version_info>=(3,10)" >nul 2>nul
  if not errorlevel 1 (
    set "SVC_PY_EXE=py"
    set "SVC_PY_EXTRA=-3.10"
    exit /b 0
  )
  py -3 -c "import sys; assert sys.version_info>=(3,10)" >nul 2>nul
  if not errorlevel 1 (
    set "SVC_PY_EXE=py"
    set "SVC_PY_EXTRA=-3"
    exit /b 0
  )
)
where python >nul 2>nul
if not errorlevel 1 (
  call python -c "import sys; assert sys.version_info>=(3,10)" >nul 2>nul
  if not errorlevel 1 (
    set "SVC_PY_EXE=python"
    set "SVC_PY_EXTRA="
    exit /b 0
  )
)
echo [ERROR] Python 3.10+ required.
exit /b 1

:check_vcredist_for_paddle
if defined SKIP_VCREDIST_CHECK (
  call :svc_log "init: SKIP_VCREDIST_CHECK set; skip VC++ runtime probe"
  exit /b 0
)
if not exist "%ROOT%\scripts\check_vcredist.ps1" (
  call :svc_log "[WARN] missing scripts\check_vcredist.ps1; skip VC++ runtime probe"
  exit /b 0
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%\scripts\check_vcredist.ps1"
if errorlevel 1 (
  set "VCREDIST_MISSING=1"
  call :svc_log "[WARN] VC++ Redistributable ^(x64^) likely missing for Paddle"
) else (
  set "VCREDIST_MISSING=0"
)
exit /b 0

:usage
echo.
echo Usage:
echo   service.bat init   pip + DB scripts + VC++ probe + Paddle warm-up ^(if ocr.prefetch_on_init=true^)
echo   service.bat start  start backend + frontend ^(run init first on a new copy^)
echo   service.bat stop   stop services
echo   service.bat clear  stop + DB + OCR model dirs ^(yaml^)/logs/.service ^(redo: init^)
echo.
echo Optional: set PIP_INDEX=https://pypi.org/simple
echo Optional: set SKIP_VCREDIST_CHECK=1 ^(skip VC++ runtime probe before Paddle warm-up; not recommended^)
echo Optional: set SVC_BACKEND_WAIT_SEC=300 ^(if ocr.prefetch_on_startup=true and startup blocks on Paddle^)
echo Upgrades:   data\db\upgrades\ ^(reserved^)
echo.
exit /b 1
