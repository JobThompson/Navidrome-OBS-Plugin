@echo off
setlocal
cd /d "%~dp0"
echo Navidrome OBS Overlay - Setup
echo.
echo This will open a setup window to save your settings.
echo.
py -3 navidrome_obs_overlay.py --gui
if errorlevel 1 (
  echo.
  echo Setup failed.
  echo.
  echo If you do not have Python installed, install Python 3.10+ from https://www.python.org/downloads/
  echo Then run this file again.
)
echo.
pause
