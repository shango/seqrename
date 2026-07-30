@echo off
REM Double-click to install SeqRename for the current user.
REM No administrator rights are required.
REM
REM   install.bat                        install to %LOCALAPPDATA%\Programs\SeqRename
REM   install.bat -NoDesktopShortcut     skip the desktop shortcut
REM   install.bat -InstallDir D:\Tools\SeqRename
REM   install.bat -Uninstall             remove it again

setlocal
cd /d "%~dp0"

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Install-SeqRename.ps1" %*
set RC=%ERRORLEVEL%

if %RC% neq 0 (
    echo.
    echo INSTALL FAILED ^(exit code %RC%^)
)

if "%~1"=="" pause

exit /b %RC%
