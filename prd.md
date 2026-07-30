# SeqRename: VFX Sequence Renamer — Product Requirements & Technical Spec

**Version:** 1.0 Draft
**Target platform:** Windows 11 primary, Linux/macOS supported
**Language:** Python 3.11+
**Distribution:** pip-installable CLI (`seqrename`), optional PySide6 GUI

---

## 1. Purpose

A production-grade tool for renaming, renumbering, and restructuring image sequences (EXR, DPX, TIFF, PNG, JPG, MOV-adjacent sidecars) in VFX pipelines. Replaces error-prone manual renames and brittle one-off scripts with a safe, previewable, undoable, pipeline-aware renamer.

## 2. Target Users

- Compositors and matchmove artists renaming plate/render deliveries
- VFX supervisors conforming vendor deliveries to studio naming conventions
- Pipeline TDs batch-processing renders across shots

## 3. Core Concepts

### 3.1 Sequence Detection
- Auto-detect sequences from a directory: group files by (prefix, padding, extension), treating the frame number as the variable token.
- Support common patterns: `name.####.ext`, `name_####.ext`, `name####.ext`, `name.%04d.ext`, `name.$F4.ext`.
- Handle multiple sequences in one directory; each is a distinct rename target.
- Detect padding width automatically; flag inconsistent padding within a sequence (e.g. `1001` and `01002` mixed).
- Detect frame gaps and report them (list missing frames); gaps never block a rename, but are surfaced in preview.
- Support negative frame numbers and frame 0.
- Ignore non-sequence files (single stills, sidecars) unless explicitly included.

### 3.2 Rename Operations
All operations are composable in a single pass:

1. **Prefix/name replace:** literal or regex find/replace on the name portion.
2. **Renumber:** new start frame, optional frame step remap (e.g. retime 2s to 1s), reverse ordering.
3. **Repad:** change padding width (e.g. 4 → 5 digits).
4. **Version bump:** detect `v###` tokens; set, increment, or strip version.
5. **Extension change:** case normalization (`.EXR` → `.exr`) or literal swap (label-only; no transcoding).
6. **Token templating:** output pattern language, e.g. `{show}_{shot}_{task}_v{version}.{frame:04d}.{ext}` with tokens sourced from CLI args, config, or parsed from the source name.
7. **Case transforms:** lower/upper/title on name tokens.
8. **Move/copy:** rename in place, move to target directory, or copy (leave source untouched). Target directory template supports tokens (e.g. `{shot}/{task}/v{version}/`).

### 3.3 Safety Model (non-negotiable)
- **Dry-run by default.** No filesystem mutation without `--commit` (CLI) or explicit Apply (GUI).
- **Preview table:** old → new for every file, with per-file status (OK, collision, skipped, gap-adjacent).
- **Collision detection:** refuse to commit if any target path exists or if two sources map to one target. Overwrite requires `--force` plus interactive confirmation.
- **Cycle-safe renames:** when a rename set overlaps itself (e.g. shifting frames by +1 within the same sequence), use two-phase rename via temporary names to avoid clobbering.
- **Atomicity:** commit is transactional per sequence. On any failure mid-commit, automatically roll back completed renames.
- **Undo journal:** every commit writes a JSON journal (`.seqrename/journal-<timestamp>.json`) recording old/new paths. `seqrename undo` reverts the last operation; `seqrename undo --list` shows history.
- **Locked/open file handling:** on Windows, detect files locked by other processes (Nuke, RV) and report before commit rather than failing mid-run.
- **Read-only and permission checks** run during preview, not commit.

## 4. CLI Specification

```
seqrename [SOURCE] [options]

Selection:
  --seq PATTERN          Limit to sequences matching glob/regex
  --frames 1001-1050,1060  Frame range filter
  --recursive            Scan subdirectories
  --include-single       Treat single files as 1-frame sequences

Operations:
  --replace OLD NEW      Literal name replace
  --regex PAT REPL       Regex replace (Python re syntax)
  --start N              Renumber starting at N
  --step N               Frame step remap
  --reverse              Reverse frame order
  --pad N                Repad to N digits
  --version-set N | --version-bump | --version-strip
  --template "TPL"       Full output template
  --ext EXT              Change extension label
  --lower | --upper

Output:
  --move DIR             Move to directory (token templates allowed)
  --copy DIR             Copy instead of rename
  --commit               Execute (default is dry-run)
  --force                Allow overwrites (still confirms)

Info:
  --report [json|csv|table]   Preview format
  undo [--list] [--id ID]
  scan                   List detected sequences, ranges, gaps, sizes
```

Exit codes: 0 success, 1 preview-only, 2 collision/validation failure, 3 partial failure rolled back.

## 5. Configuration

- `seqrename.toml` discovered in cwd, project root, or `~/.config/seqrename/`.
- Defines: naming convention templates, default padding, show/shot token regexes, protected paths (refuse to operate under them, e.g. `/plates/original/`), journal retention.
- Named presets: `seqrename --preset delivery_conform`.

## 6. GUI (Phase 2)

- PySide6 app: drag-and-drop folder, sequence list panel, operation stack (reorderable), live preview table with diff-highlighted filenames, thumbnail strip (first/mid/last frame via OpenImageIO), Apply/Undo buttons.
- Same engine as CLI; GUI is a thin layer over the core library.

## 7. Library API

Core is importable for pipeline integration:

```python
from seqrename import scan, RenameOp, Plan

seqs = scan("D:/renders", recursive=True)
plan = Plan(seqs[0]).replace("v001", "v002").repad(5).renumber(start=1001)
report = plan.preview()      # list of (src, dst, status)
plan.commit()                # raises on collision; journaled
plan.undo()
```

- Fully typed, no side effects at import, pure-Python core with zero required non-stdlib deps.
- Optional extras: `[gui]` (PySide6), `[thumbs]` (OpenImageIO), `[fseq]` (fileseq interop for `1001-1050#` range strings).

## 8. Pipeline Integrations (Phase 2+)

- **fileseq-compatible** range string parsing/printing.
- **Nuke:** menu.py snippet that renames a Read node's sequence on disk and repaths the node.
- **Deadline/tractor:** headless mode with `--report json` for wrapper scripts.
- **Sidecar awareness:** optionally rename matching sidecars (`.json`, `.xml`, `.cube`) that share the sequence basename.

## 9. Performance Requirements

- Scan 100k files in under 5 seconds on local NVMe (os.scandir, no stat per file unless needed).
- Preview generation is O(n) with no filesystem writes.
- Commit uses `os.rename` (same volume) and falls back to copy+verify+delete across volumes, with a progress callback and checksum verification (xxhash) for copies.

## 10. Logging & Reporting

- Structured logging (`--log-level`), log file per commit alongside the journal.
- CSV/JSON report export of any preview or commit for delivery paperwork.

## 11. Testing & Quality

- pytest suite: pattern detection matrix, collision/cycle cases, cross-volume copy, Windows locked-file simulation, undo round-trips, Unicode and long-path (`\\?\` prefix) handling on Windows.
- Property-based tests (hypothesis) for rename/undo inverses.
- CI on Windows + Linux.

## 12. Non-Goals

- No image transcoding or format conversion.
- No color management.
- No asset-management/database integration in v1.

## 13. Milestones

| Phase | Scope |
|-------|-------|
| 0.1 | Scanner, preview, replace/renumber/repad, dry-run, commit, collisions |
| 0.2 | Undo journal, cycle-safe renames, cross-volume copy, config/presets |
| 0.3 | Templates, version tokens, sidecars, JSON/CSV reports |
| 1.0 | Docs, packaging, Windows long-path hardening, CI |
| 2.0 | GUI, thumbnails, Nuke integration |