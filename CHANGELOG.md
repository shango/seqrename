# Changelog

Semantic versioning. The version lives in `src/seqrename/__init__.py`; the
package metadata, the app header badge and the Windows file-version resource
are all derived from it.

## [0.4.0] - 2026-07-30

### Added
- **Clear** button in the Sequences panel, next to Select all. Empties the
  queue without touching a single file; F5 scans the folder again.

### Changed
- **Undo journals no longer sit next to the renamed files.** They now live in
  per-user application data (`%LOCALAPPDATA%\SeqRename\journals` on Windows,
  `$XDG_DATA_HOME/seqrename/journals` elsewhere), so a rename leaves the media
  folder containing only media. Undo is unaffected - each journal records the
  folder it belongs to, and the app looks up history by folder.
  - The journals are the undo history, so deleting them on completion would
    have removed the ability to undo; moving them keeps both properties.
  - A `.seqrename` folder left by an earlier version is migrated into the new
    location and removed the next time that folder is scanned. Undo entries
    written by the old version keep working.
  - Retention: the oldest journals are pruned once there are more than 200.
  - `SEQRENAME_JOURNAL_DIR` overrides the location.

## [0.3.0] - 2026-07-30

### Changed
- The installer is now a real setup executable built with Inno Setup, replacing
  the PowerShell script and `install.bat`. `build.bat -Installer` produces
  `dist\SeqRename-<version>-setup.exe` (32 MB, down from a 44 MB zip).
  - Still a per-user install: `PrivilegesRequired=lowest` means no elevation and
    no UAC prompt, `{autopf}` resolves to `%LOCALAPPDATA%\Programs`, and the
    uninstall entry stays in HKCU. `/ALLUSERS` opts into a machine-wide install
    for anyone who does have admin.
  - Supports the usual silent switches (`/VERYSILENT`, `/DIR=`, `/NORESTART`)
    for deploying across several workstations.
  - Extracted files carry no mark-of-the-web, so the workaround the script
    installer needed is no longer necessary.

### Removed
- `packaging/Install-SeqRename.ps1`, `packaging/install.bat` and
  `packaging/INSTALL.txt`, superseded by the Inno Setup installer.

## [0.2.0] - 2026-07-30

### Added
- Per-user installer, for locked-down and networked workstations. `build.bat
  -Installer` produces `dist\SeqRename-<version>-win64.zip`; unzip it on the
  target machine and run `install.bat`.
  - Installs to `%LOCALAPPDATA%\Programs\SeqRename`, writes Start Menu and
    Desktop shortcuts and an uninstall entry under HKCU only. Nothing touches
    Program Files, HKLM, the PATH, services or drivers, so no administrator
    rights and no UAC prompt are involved.
  - Clears the mark-of-the-web that Windows applies to files copied over a
    network, which otherwise blocks the app from launching.
  - `-InstallDir` for a different location, `-NoDesktopShortcut`, `-Quiet`,
    and `-Uninstall`. Uninstall also works from Apps & features.
  - The built package is committed to `releases/` so it can be downloaded
    straight from the repo. The zip unpacks into a single named folder.

## [0.1.0] - 2026-07-30

First working build: engine plus the PySide6 desktop app for Windows 11.

### Added
- Sequence scanner: groups on `prefix + frame + suffix + ext`, detects padding,
  reports frame gaps, flags mixed padding, handles negative frames and frame 0.
- Operations: find/replace (literal or regex), case, version set/bump/strip,
  renumber (start, step, reverse) or offset, repad, extension swap and case,
  and rename / move / copy.
- Safety model: dry-run preview by default, collision and duplicate detection,
  cycle-safe two-phase renames, rollback on any mid-commit failure, JSON undo
  journal, pre-commit checks for locked files and unwritable directories.
- Cross-volume moves fall back to copy → verify → delete, with an optional
  checksum comparison.
- PySide6 GUI: three-pane layout, diff-highlighted preview, thumbnails for
  Qt-readable formats, threaded scan and apply, drag-and-drop folders.
- Windows delivery: `build.bat` / `build.ps1` (PyInstaller onedir),
  `run-dev.ps1`, and `sync-to-windows.sh` for the Linux → Windows mirror.
- 35 tests covering detection, collisions, cycles, cross-volume copy, undo
  round-trips, and a headless GUI apply → undo run.

### Known gaps
The CLI, `seqrename.toml` config and presets, token templating, sidecar
renaming, JSON/CSV export, fileseq interop, Nuke/Deadline integration, and
OpenImageIO thumbnails for EXR/DPX are all still unimplemented.
