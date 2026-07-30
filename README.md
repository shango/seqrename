# SeqRename

A safe, previewable renamer for VFX image sequences (EXR, DPX, TIFF, PNG, …),
built to the spec in [`prd.md`](prd.md). Pure-stdlib engine plus a PySide6
desktop app for Windows 11.

![SeqRename](docs/screenshot.png)

## What it does

Scans a folder, groups files into sequences, and previews every rename before
anything touches disk.

- **Operations:** find/replace (literal or regex), case, version set/bump/strip,
  renumber (start, step, reverse) or offset, repad, extension swap, and
  rename / move / copy.
- **Nothing is written until you press Apply.** The preview highlights the
  changed characters per file and flags collisions and duplicate targets.
- **Safe by construction:** cycle-safe two-phase renames, rollback on any
  mid-commit failure, a JSON undo journal, pre-commit checks for locked files,
  and copy → verify → delete across volumes.

Shortcuts: `Ctrl+O` browse · `F5` rescan · `Ctrl+Enter` apply · `Ctrl+Z` undo.

## Download

Prebuilt Windows installer, no Python or build step needed:

**[releases/SeqRename-0.2.0-win64.zip](releases/SeqRename-0.2.0-win64.zip)** - 44 MB

```
sha256  ac9ac556451d042b809cdf5a7ec05c649697bc18c2385804dd55e7b84f705e74
```

Unzip it, open the `SeqRename-0.2.0-win64` folder, and run `install.bat`. It is
a per-user install and needs no administrator rights - see
[Installing on another machine](#installing-on-another-machine).

## Run it

**Windows** (the target platform):

```powershell
.\build.bat                 # tests + package -> dist\SeqRename\SeqRename.exe
.\build.bat -SkipTests -Run # fast rebuild and launch
.\build.bat -KillRunning    # close a running SeqRename.exe first
.\run-dev.ps1               # run from source instead, no packaging
```

### Installing on another machine

```powershell
.\build.bat -Installer      # -> dist\SeqRename-<version>-win64.zip
```

Copy the zip to the target workstation, unzip it, and run `install.bat`. It is a
per-user install: files go to `%LOCALAPPDATA%\Programs\SeqRename`, shortcuts and
the uninstall entry are written under HKCU, and nothing touches Program Files,
HKLM, the PATH or any service. No administrator rights, no UAC prompt - which is
what makes it work on a locked-down networked workstation. It also clears the
mark-of-the-web that would otherwise block a build copied across the network.
See [`packaging/INSTALL.txt`](packaging/INSTALL.txt) for options such as
`-InstallDir`, `-Quiet` and `-Uninstall`.

`build.bat` wraps `build.ps1`, which takes the same flags plus `-Clean`. The
build refuses to run while `SeqRename.exe` is open (a running copy holds its
DLLs), and after packaging it launches the exe with `--selftest` and fails if it
does not exit cleanly.

**Linux** (development):

```bash
python -m venv .venv && .venv/bin/pip install PySide6 pytest
PYTHONPATH=src .venv/bin/python -m seqrename.gui
PYTHONPATH=src .venv/bin/python -m pytest tests -q
```

## Syncing Linux → Windows

The repo lives on a Linux partition; builds happen on the Windows side.

```bash
./sync-to-windows.sh            # mirror to C:\Users\USERNAME\Documents\win_dev\seqrename
./sync-to-windows.sh --dry-run  # preview the file list
./sync-to-windows.sh --build    # sync, then build over there
WIN_USER=someone ./sync-to-windows.sh
DEST=/mnt/c/elsewhere ./sync-to-windows.sh
```

`USERNAME` is your Windows account name, looked up automatically; override it
with `WIN_USER`, or give a full path with `DEST`.

The Windows-side `.venv/`, `build/` and `dist/` are excluded, so repeated syncs
never wipe the environment.

## Library use

The engine has no dependency on Qt:

```python
from seqrename import Plan, RenameOps, scan, last_undoable, undo

seqs = scan("D:/renders", recursive=True)
plan = Plan(seqs, RenameOps(find="v001", replace="v002", repad=True, pad=5))
for entry in plan.preview():
    print(entry.src.name, "->", entry.dst.name, entry.status.value)

plan.commit()                    # refuses to run if anything collides
undo(last_undoable("D:/renders"))
```

## Layout

```
src/seqrename/       scanner, ops, plan, fsops, journal   (stdlib only)
src/seqrename/gui/   PySide6 app: window, theme, panels, workers
tests/               pytest suite (engine + headless GUI)
packaging/           PyInstaller spec, icon and version-resource generators
```

Version lives in `src/seqrename/__init__.py` and flows to the package metadata,
the app header badge and the Windows file-version resource. See
[`CHANGELOG.md`](CHANGELOG.md) for what is in this release and what from the PRD
is still unimplemented.
