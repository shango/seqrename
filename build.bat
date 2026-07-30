@echo off
REM Double-click me, or run from a terminal:
REM     build.bat                 full build -> dist\SeqRename\SeqRename.exe
REM     build.bat -SkipTests      skip the test run
REM     build.bat -Clean          fresh venv, wipe build\ and dist\
REM     build.bat -Installer      also produce the per-user installer zip
REM     build.bat -SkipTests -Run rebuild and launch
REM Any arguments are passed straight through to build.ps1.

setlocal
cd /d "%~dp0"

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0build.ps1" %*
set BUILD_EXIT=%ERRORLEVEL%

if %BUILD_EXIT% neq 0 (
    echo.
    echo BUILD FAILED ^(exit code %BUILD_EXIT%^)
)

REM Keep the window open when double-clicked so the result stays readable.
if "%~1"=="" pause

exit /b %BUILD_EXIT%
