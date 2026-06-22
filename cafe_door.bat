@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

rem 파이썬 런처를 한 번만 탐지: py -3 우선, 없으면 python (설치.bat 과 동일 기준)
set "PYEXE=py -3"
%PYEXE% --version >nul 2>&1 || set "PYEXE=python"

echo [1/5] generate_dashboard.py
call :pyrun scripts\generate_dashboard.py
if errorlevel 1 goto :fail

echo [2/5] capture_ticker.py
call :pyrun scripts\capture_ticker.py --wait-ms 4000
if errorlevel 1 goto :fail

for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd_HHmmss"') do set STAMP=%%i
copy /Y docs\ticker.png docs\%STAMP%.png >nul
powershell -NoProfile -Command "Set-Content -Path 'docs\.last_ticker.txt' -Value '%STAMP%' -Encoding ascii -NoNewline"

echo [3/5] git commit and push
git add -f docs\%STAMP%.png
git add docs\data.json docs\index.html docs\ticker.png docs\ticker_version.txt cafe-door.html
git diff --cached --quiet
if errorlevel 1 (
    git commit -m "chore: ticker update"
    echo [3b] cafe-door — jsDelivr 경로에 ticker.png 가 들어간 커밋 SHA 사용 (amend 금지: 이전 SHA 가 원격에 없어짐^)
    call :pyrun scripts\write_cafe_door_jdelivr.py
    if errorlevel 1 goto :fail
    git add cafe-door.html
    git commit -m "chore: cafe-door jsDelivr @commit"
    git push -f origin main
    if errorlevel 1 goto :fail
    echo Push OK.
) else (
    echo No changes - skip push.
)

echo [4/5] jsDelivr purge
powershell -NoProfile -Command "Invoke-WebRequest -Uri 'https://purge.jsdelivr.net/gh/kjhwang725-maker/cafe@main/docs/ticker.png' -UseBasicParsing | Out-Null" 2>nul
powershell -NoProfile -Command "Invoke-WebRequest -Uri ('https://purge.jsdelivr.net/gh/kjhwang725-maker/cafe@main/docs/%STAMP%.png') -UseBasicParsing | Out-Null" 2>nul
echo CDN purge done.

echo [5/5] 바탕화면 공간시장.txt — 카페 붙여넣기용 HTML (최종 cafe-door 반영^)
call :pyrun scripts\write_desktop_cafe_txt.py
if errorlevel 1 goto :fail

echo Done.
exit /b 0

:pyrun
%PYEXE% %*
exit /b %ERRORLEVEL%

:fail
echo FAILED.
pause
exit /b 1
