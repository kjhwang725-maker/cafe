@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

REM ---------------------------------------------------------------------------
REM 로컬 모드(기본): docs\data.json·index.html·yyyy-mm-dd.png·ticker.png 갱신. 카페는 수동 업로드.
REM 원격 반영(Git push + jsDelivr 퍼지): 아래 CAFE_DOOR_REMOTE 를 1 로 바꾸세요.
REM ---------------------------------------------------------------------------
set CAFE_DOOR_REMOTE=

echo [1/4] generate_dashboard.py
call :pyrun scripts\generate_dashboard.py
if errorlevel 1 goto :fail

echo [2/4] capture_ticker.py
call :pyrun scripts\capture_ticker.py --wait-ms 4000
if errorlevel 1 goto :fail

if "%CAFE_DOOR_REMOTE%"=="1" goto :remote

echo [3/4] 로컬 모드 — git push·CDN 퍼지 생략
echo [4/4] 바탕화면에 yyyy-mm-dd.png 복사
goto :after_remote

:remote
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

:after_remote
REM 생성 이미지 docs\yyyy-mm-dd.png → 바탕화면 (Join-Path 는 인자 2개만 가능)
powershell -NoProfile -ExecutionPolicy Bypass -Command "$d = Get-Date -Format 'yyyy-MM-dd'; $src = Join-Path (Join-Path '%cd%' 'docs') ($d + '.png'); $dst = Join-Path ([Environment]::GetFolderPath('Desktop')) ($d + '.png'); if (-not (Test-Path -LiteralPath $src)) { Write-Host 'WARN: not found:' $src; exit 0 }; Copy-Item -LiteralPath $src -Destination $dst -Force; Write-Host 'Desktop:' $dst"

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
