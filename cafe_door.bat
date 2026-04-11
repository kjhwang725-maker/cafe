@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

echo [1/4] generate_dashboard.py
call :pyrun scripts\generate_dashboard.py
if errorlevel 1 goto :fail

echo [2/4] capture_ticker.py
call :pyrun scripts\capture_ticker.py --wait-ms 4000
if errorlevel 1 goto :fail

echo [3/4] git commit and push
git add docs\data.json docs\index.html docs\ticker.png
git diff --cached --quiet
if errorlevel 1 (
    git commit -m "chore: ticker update"
    git pull --rebase origin main
    git push origin main
    if errorlevel 1 goto :fail
    echo Push OK.
) else (
    echo No changes - skip push.
)

echo [4/4] jsDelivr purge
powershell -NoProfile -Command "Invoke-WebRequest -Uri 'https://purge.jsdelivr.net/gh/kjhwang725-maker/cafe@main/docs/ticker.png' -UseBasicParsing | Out-Null" 2>nul
echo CDN purge done.

powershell -NoProfile -Command "Copy-Item -Path 'docs\ticker.png' -Destination ([Environment]::GetFolderPath('Desktop'))" 2>nul

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
