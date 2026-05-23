@echo off
setlocal

set PORT=%1
if "%PORT%"=="" set PORT=8088

set FOUND=0
for /f "tokens=5" %%P in ('netstat -ano -p tcp ^| findstr /R /C:":%PORT% .*LISTENING"') do (
    echo [STOP] PID %%P  port %PORT%
    taskkill /F /PID %%P >nul 2>&1
    set FOUND=1
)
if "%FOUND%"=="0" echo [INFO] No server listening on port %PORT%.
endlocal
