@echo off
REM Same as cafe_door.bat but opens the GUI window
chcp 65001 >nul
cd /d "%~dp0"
python scripts\cafe_door_upload.py --gui
