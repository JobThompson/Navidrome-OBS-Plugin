@echo off
setlocal
cd /d "%~dp0"
echo Navidrome OBS Overlay - Start
echo.
echo If this is your first time, run "Setup Overlay (GUI).bat" first.
echo.
py -3 navidrome_obs_overlay.py
if errorlevel 1 (
  echo.
  echo The overlay failed to start.
  echo.
  echo Common fixes:
  echo  - Run "Setup Overlay (GUI).bat" to create a .env file
  echo  - Change OVERLAY_PORT if another app is using it
  echo  - Install Python 3.10+ from https://www.python.org/downloads/
)
echo.
pause
