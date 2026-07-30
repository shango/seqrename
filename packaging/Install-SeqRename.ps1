<#
.SYNOPSIS
    Per-user installer for SeqRename. Needs no administrator rights.

.DESCRIPTION
    Installs to %LOCALAPPDATA%\Programs\SeqRename, writes shortcuts and an
    uninstall entry under HKCU only, and never touches Program Files, HKLM or
    the PATH. Nothing here requires elevation, which is what makes it work on
    a locked-down networked workstation.

.EXAMPLE
    .\Install-SeqRename.ps1
    .\Install-SeqRename.ps1 -InstallDir D:\Tools\SeqRename -NoDesktopShortcut
    .\Install-SeqRename.ps1 -Quiet
    .\Install-SeqRename.ps1 -Uninstall
#>
[CmdletBinding()]
param(
    [string]$InstallDir,
    [switch]$NoDesktopShortcut,
    [switch]$NoStartMenuShortcut,
    [switch]$Quiet,
    [switch]$Uninstall
)

$ErrorActionPreference = "Stop"

$AppName = "SeqRename"
$RegKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\$AppName"

function Say($text, $colour = "Gray") {
    if (-not $Quiet) { Write-Host $text -ForegroundColor $colour }
}

function Step($text) { Say "`n=== $text" "Cyan" }

function Get-ShortcutPaths {
    @{
        StartMenu = Join-Path ([Environment]::GetFolderPath('Programs')) "$AppName.lnk"
        Desktop   = Join-Path ([Environment]::GetFolderPath('Desktop')) "$AppName.lnk"
    }
}

function Stop-RunningApp {
    $running = Get-Process $AppName -ErrorAction SilentlyContinue
    if (-not $running) { return }
    if (-not $Quiet) {
        Write-Host "$AppName is running (PID $($running.Id -join ', ')). Closing it." -ForegroundColor Yellow
    }
    $running | Stop-Process -Force
    Start-Sleep -Milliseconds 700
}

function Remove-Shortcuts {
    foreach ($path in (Get-ShortcutPaths).Values) {
        if (Test-Path $path) { Remove-Item $path -Force }
    }
}

# -- uninstall -----------------------------------------------------------

if ($Uninstall) {
    Step "Uninstalling $AppName"
    $target = $InstallDir
    if (-not $target -and (Test-Path $RegKey)) {
        $target = (Get-ItemProperty $RegKey -ErrorAction SilentlyContinue).InstallLocation
    }
    if (-not $target) { $target = Join-Path $env:LOCALAPPDATA "Programs\$AppName" }

    Stop-RunningApp
    Remove-Shortcuts
    if (Test-Path $RegKey) { Remove-Item $RegKey -Recurse -Force }

    # Step out of the folder first so it is not held open while being removed.
    Set-Location $env:TEMP
    if (Test-Path $target) {
        Remove-Item $target -Recurse -Force -ErrorAction SilentlyContinue
        if (Test-Path $target) {
            Say "Could not fully remove $target - delete it by hand." "Yellow"
        }
    }
    Say "`n$AppName has been removed." "Green"
    return
}

# -- install -------------------------------------------------------------

$payload = Join-Path $PSScriptRoot "app"
$exeName = "$AppName.exe"
if (-not (Test-Path (Join-Path $payload $exeName))) {
    throw "Cannot find $exeName in '$payload'. Run this script from the unzipped installer folder."
}

if (-not $InstallDir) { $InstallDir = Join-Path $env:LOCALAPPDATA "Programs\$AppName" }

$version = (Get-Item (Join-Path $payload $exeName)).VersionInfo.FileVersion
Say "`n$AppName $version" "White"
Say "Installing to: $InstallDir"
Say "No administrator rights are needed; nothing outside your user profile is touched."

Step "Unblocking files"
# Files copied from a network share or downloaded carry a mark-of-the-web that
# makes Windows refuse to run them. Clearing it here avoids that whole class of
# "permission" error.
Get-ChildItem $PSScriptRoot -Recurse -File | Unblock-File -ErrorAction SilentlyContinue

Step "Copying files"
Stop-RunningApp
if (-not (Test-Path $InstallDir)) { New-Item $InstallDir -ItemType Directory -Force | Out-Null }

# /MIR so an upgrade drops files that no longer ship. Robocopy uses exit codes
# 0-7 for success; 8 and above are real failures.
$roboArgs = @($payload, $InstallDir, "/MIR", "/NFL", "/NDL", "/NJH", "/NJS", "/NP", "/R:2", "/W:2")
$null = & robocopy.exe @roboArgs
if ($LASTEXITCODE -ge 8) { throw "Copy failed (robocopy exit code $LASTEXITCODE)" }

# Keep the uninstaller with the app so it survives deleting the download.
Copy-Item $PSCommandPath (Join-Path $InstallDir "Install-SeqRename.ps1") -Force
$uninstallCmd = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$InstallDir\Install-SeqRename.ps1`" -Uninstall"
Set-Content -Path (Join-Path $InstallDir "Uninstall.bat") `
    -Value "@echo off`r`n$uninstallCmd`r`npause" -Encoding ASCII

$exePath = Join-Path $InstallDir $exeName

Step "Creating shortcuts"
$shell = New-Object -ComObject WScript.Shell
$paths = Get-ShortcutPaths
foreach ($entry in @(
        @{ Path = $paths.StartMenu; Skip = $NoStartMenuShortcut },
        @{ Path = $paths.Desktop;   Skip = $NoDesktopShortcut })) {
    if ($entry.Skip) { continue }
    $link = $shell.CreateShortcut($entry.Path)
    $link.TargetPath = $exePath
    $link.WorkingDirectory = $InstallDir
    $link.IconLocation = $exePath
    $link.Description = "SeqRename - VFX sequence renamer"
    $link.Save()
    Say "  $($entry.Path)"
}

Step "Registering for Add/Remove Programs"
$size = [math]::Round((Get-ChildItem $InstallDir -Recurse -File |
        Measure-Object -Property Length -Sum).Sum / 1KB)
New-Item $RegKey -Force | Out-Null
Set-ItemProperty $RegKey DisplayName     $AppName
Set-ItemProperty $RegKey DisplayVersion  $version
Set-ItemProperty $RegKey Publisher       $AppName
Set-ItemProperty $RegKey InstallLocation $InstallDir
Set-ItemProperty $RegKey DisplayIcon     $exePath
Set-ItemProperty $RegKey UninstallString $uninstallCmd
Set-ItemProperty $RegKey EstimatedSize   ([int]$size) -Type DWord
Set-ItemProperty $RegKey NoModify        1 -Type DWord
Set-ItemProperty $RegKey NoRepair        1 -Type DWord

Say "`n$AppName $version installed." "Green"
Say "  Run it from the Start Menu, or: $exePath"
Say "  Uninstall from Apps & features, or run: $InstallDir\Uninstall.bat"
