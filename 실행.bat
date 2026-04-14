@echo off
setlocal
cd /d "%~dp0"
call cafe_door.bat
exit /b %ERRORLEVEL%
