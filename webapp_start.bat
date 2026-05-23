@echo off
setlocal
cd /d "%~dp0"

set PORT=%1
if "%PORT%"=="" set PORT=8088

for /f "tokens=5" %%P in ('netstat -ano -p tcp ^| findstr /R /C:":%PORT% .*LISTENING"') do (
    echo [INFO] Server already running on port %PORT% ^(PID %%P^).
    echo        http://127.0.0.1:%PORT%/
    goto :open
)

echo [START] webapp.py --port %PORT%  (hidden, log: webapp.log)
wscript.exe //nologo scripts\run_webapp_hidden.vbs %PORT%

set /a TRIES=0
:wait
set /a TRIES+=1
ping -n 2 127.0.0.1 >nul
for /f "tokens=5" %%P in ('netstat -ano -p tcp ^| findstr /R /C:":%PORT% .*LISTENING"') do goto :ready
if %TRIES% LSS 5 goto :wait
echo [WARN] Port %PORT% not listening yet. See webapp.log
goto :open

:ready
echo [READY] http://127.0.0.1:%PORT%/

:open
start "" http://127.0.0.1:%PORT%/
endlocal
