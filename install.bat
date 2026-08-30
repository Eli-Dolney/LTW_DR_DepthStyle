@echo off
set "DEST=%APPDATA%\Blackmagic Design\DaVinci Resolve\Support\Fusion\Scripts\Edit"
mkdir "%DEST%" 2>nul
copy /Y "%~dp0scripts\ltw_depth_style.py" "%DEST%\" >nul
copy /Y "%~dp0scripts\ltw_depth_lib.py" "%DEST%\" >nul
echo Installed to:
echo   %DEST%
echo.
echo Restart DaVinci Resolve, then: Workspace - Scripts - Edit - ltw_depth_style
pause
