@echo off
setlocal
cd /d "%~dp0"

rem 파이썬 런처를 한 번만 탐지: py -3 우선, 없으면 python (cafe_door.bat 과 동일 기준)
set "PYEXE=py -3"
%PYEXE% --version >nul 2>&1 || set "PYEXE=python"

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
echo OK. Run 실행.bat (or cafe_door.bat) when ready.
pause
exit /b 0

:pip_upgrade
call :pyrun -m pip install --upgrade pip
exit /b %ERRORLEVEL%

:pyrun
%PYEXE% %*
exit /b %ERRORLEVEL%

:fail
echo FAILED.
pause
exit /b 1
