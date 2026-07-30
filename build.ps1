<#
.SYNOPSIS
    Build SeqRename.exe (PyInstaller, onedir) on Windows 11.

.EXAMPLE
    .\build.ps1                 # venv + deps + tests + package
    .\build.ps1 -SkipTests      # faster iteration
    .\build.ps1 -Clean          # rebuild the venv and wipe build/ dist/
    .\build.ps1 -Run            # package, then launch the result
#>
[CmdletBinding()]
param(
    [string]$Root,
    [switch]$Clean,
    [switch]$SkipTests,
    [switch]$KillRunning,
    [switch]$Installer,
    [switch]$Run
)

$ErrorActionPreference = "Stop"

# Windows PowerShell 5.1 evaluates param defaults before $PSScriptRoot exists
# when the script uses [CmdletBinding()], so resolve the root here instead.
if (-not $Root) { $Root = $PSScriptRoot }
if (-not $Root) { $Root = (Get-Location).Path }
Set-Location $Root

function Step($text) { Write-Host "`n=== $text" -ForegroundColor Cyan }

$venv = Join-Path $Root ".venv"
$python = Join-Path $venv "Scripts\python.exe"

# A running copy holds its DLLs open and PyInstaller cannot replace dist\.
$running = Get-Process SeqRename -ErrorAction SilentlyContinue
if ($running) {
    if ($KillRunning) {
        Write-Host "Stopping running SeqRename (PID $($running.Id -join ', '))" -ForegroundColor Yellow
        $running | Stop-Process -Force
        Start-Sleep -Milliseconds 700
    }
    else {
        throw "SeqRename is running (PID $($running.Id -join ', ')). Close it first, or re-run with -KillRunning."
    }
}

if ($Clean) {
    Step "Cleaning"
    foreach ($dir in @($venv, (Join-Path $Root "build"), (Join-Path $Root "dist"))) {
        if (Test-Path $dir) { Remove-Item $dir -Recurse -Force }
    }
}

if (-not (Test-Path $python)) {
    Step "Creating virtual environment"
    $base = Get-Command py -ErrorAction SilentlyContinue
    if ($base) { & py -3 -m venv $venv } else { & python -m venv $venv }
}

Step "Installing dependencies"
& $python -m pip install --upgrade pip --quiet
& $python -m pip install --upgrade "PySide6>=6.6" "pyinstaller>=6.6" "pytest>=8" --quiet
if ($LASTEXITCODE -ne 0) { throw "pip install failed" }

if (-not $SkipTests) {
    Step "Running tests"
    $env:PYTHONPATH = Join-Path $Root "src"
    & $python -m pytest tests -q
    if ($LASTEXITCODE -ne 0) { throw "Tests failed - build aborted" }
}

Step "Generating icon and version resource"
& $python (Join-Path $Root "packaging\make_icon.py")
& $python (Join-Path $Root "packaging\make_version_info.py")
if ($LASTEXITCODE -ne 0) { throw "Could not generate the version resource" }

Step "Packaging with PyInstaller"
& $python -m PyInstaller (Join-Path $Root "packaging\SeqRename.spec") `
    --noconfirm `
    --distpath (Join-Path $Root "dist") `
    --workpath (Join-Path $Root "build")
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }

$exe = Join-Path $Root "dist\SeqRename\SeqRename.exe"
if (-not (Test-Path $exe)) { throw "Expected $exe but it is missing" }

Step "Smoke-testing the packaged app"
# Runs on the real windows platform plugin - offscreen would hide a missing
# qwindows.dll - so the window flashes up for an instant here. A bundle that
# fails to import shows a blocking error dialog instead of exiting, so treat
# "still running" as a failure, not as success.
$probe = Start-Process $exe -ArgumentList "--selftest" -PassThru
$exited = $probe.WaitForExit(90000)
if (-not $exited) {
    $probe.Kill()
    throw "The packaged app did not start cleanly - it hung or showed an error dialog. Run $exe by hand to see it."
}
if ($probe.ExitCode -ne 0) {
    throw "The packaged app exited with code $($probe.ExitCode) during its self-test."
}
Write-Host "Self-test passed" -ForegroundColor Green

$size = (Get-ChildItem (Join-Path $Root "dist\SeqRename") -Recurse |
         Measure-Object -Property Length -Sum).Sum / 1MB
Write-Host "`nBuilt $exe" -ForegroundColor Green
Write-Host ("Folder size: {0:N0} MB" -f $size)

if ($Installer) {
    Step "Compiling the installer"
    $version = (Get-Item $exe).VersionInfo.FileVersion -replace '\.0$', ''

    # Inno Setup installs per-user too, so look inside the profile first.
    $isccCandidates = @(
        (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"),
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
    )
    $iscc = $isccCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
    if (-not $iscc) {
        $iscc = (Get-Command ISCC.exe -ErrorAction SilentlyContinue).Source
    }
    if (-not $iscc) {
        throw @"
Inno Setup 6 is not installed, so the installer cannot be compiled.
Get it from https://jrsoftware.org/isdl.php and install it for the current
user (the installer accepts /CURRENTUSER, so no admin rights are needed):

  innosetup-6.x.x.exe /VERYSILENT /CURRENTUSER /DIR="%LOCALAPPDATA%\Programs\Inno Setup 6"
"@
    }

    & $iscc "/DAppVersion=$version" (Join-Path $Root "packaging\SeqRename.iss") | ForEach-Object {
        if ($_ -match "^(Error|Warning)") { Write-Host $_ -ForegroundColor Yellow }
    }
    if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed (exit code $LASTEXITCODE)" }

    $setup = Join-Path $Root "dist\SeqRename-$version-setup.exe"
    if (-not (Test-Path $setup)) { throw "Expected $setup but it is missing" }
    $setupSize = (Get-Item $setup).Length / 1MB
    Write-Host "`nInstaller: $setup" -ForegroundColor Green
    Write-Host ("Size: {0:N0} MB - double-click to install, no admin rights needed" -f $setupSize)
}

if ($Run) {
    Step "Launching"
    Start-Process $exe
}
