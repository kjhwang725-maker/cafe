@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

REM Pipeline: dashboard -> capture -> git commit+push -> GitHub Pages auto-deploy
echo [1/3] generate_dashboard.py
call :pyrun scripts\generate_dashboard.py
if errorlevel 1 goto :fail

echo [2/3] capture_ticker.py
call :pyrun scripts\capture_ticker.py --wait-ms 4000
if errorlevel 1 goto :fail

echo [3/3] git commit and push
git add docs\data.json docs\index.html docs\ticker.png
git diff --cached --quiet
if errorlevel 1 (
    for /f "tokens=*" %%d in ('powershell -NoProfile -Command "Get-Date -Format 'yyyy-MM-dd HH:mm UTC'"') do set "TS=%%d"
    git commit -m "chore: ticker update %TS%"
    git pull --rebase origin main
    git push origin main
    if errorlevel 1 goto :fail
    echo Push OK.
) else (
    echo 변경 없음 - push 생략.
)

REM Copy ticker.png to Desktop
set "SRC=%~dp0docs\ticker.png"
for /f "usebackq delims=" %%D in (`powershell -NoProfile -Command "[Environment]::GetFolderPath('Desktop')"`) do set "DESKTOP=%%D"
copy /y "%SRC%" "%DESKTOP%\ticker.png" >nul 2>&1

echo Done.
exit /b 0

:pyrun
py -3 %*
if errorlevel 1 python %*
exit /b %ERRORLEVEL%

:fail
echo FAILED.
pause
exit /b 1
