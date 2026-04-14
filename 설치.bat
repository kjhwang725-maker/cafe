@echo off
setlocal
cd /d "%~dp0"

echo === one-time setup: pip deps + Playwright Chromium ===
echo.

call :pip_upgrade
if errorlevel 1 goto :fail

echo [install] requirements.txt
call :pyrun -m pip install -r requirements.txt
if errorlevel 1 goto :fail

echo [install] playwright chromium
call :pyrun -m playwright install chromium
if errorlevel 1 goto :fail

echo.
echo OK. Run run.bat when ready.
pause
exit /b 0

:pip_upgrade
call :pyrun -m pip install --upgrade pip
exit /b %ERRORLEVEL%

:pyrun
py -3 %*
if errorlevel 1 python %*
exit /b %ERRORLEVEL%

:fail
echo FAILED.
pause
exit /b 1
