# Changelog

Semantic versioning. The version lives in `src/seqrename/__init__.py`; the
package metadata, the app header badge and the Windows file-version resource
are all derived from it.

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
