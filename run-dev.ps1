<#
.SYNOPSIS
    Run SeqRename straight from source - no packaging step.

.EXAMPLE
    .\run-dev.ps1
    .\run-dev.ps1 -Folder "D:\renders\abc_0100"
#>
[CmdletBinding()]
param(
    [string]$Root,
    [string]$Folder
)

$ErrorActionPreference = "Stop"

# See build.ps1 - $PSScriptRoot is not available in param defaults here.
if (-not $Root) { $Root = $PSScriptRoot }
if (-not $Root) { $Root = (Get-Location).Path }
Set-Location $Root

$venv = Join-Path $Root ".venv"
$consolePython = Join-Path $venv "Scripts\python.exe"

if (-not (Test-Path $consolePython)) {
    Write-Host "Creating virtual environment…" -ForegroundColor Cyan
    $base = Get-Command py -ErrorAction SilentlyContinue
    if ($base) { & py -3 -m venv $venv } else { & python -m venv $venv }
    & $consolePython -m pip install --upgrade pip --quiet
    & $consolePython -m pip install "PySide6>=6.6" --quiet
}

$env:PYTHONPATH = Join-Path $Root "src"
$argList = @("-m", "seqrename.gui")
if ($Folder) { $argList += $Folder }

# Console python so tracebacks are visible while iterating.
& $consolePython @argList
