#!/usr/bin/env bash
# Copy the SeqRename source tree from this Linux repo to the Windows side.
#
#   ./sync-to-windows.sh              # sync
#   ./sync-to-windows.sh --dry-run    # show what would change
#   ./sync-to-windows.sh --build      # sync, then run build.ps1 on Windows
#   DEST=/mnt/c/some/other/dir ./sync-to-windows.sh
#
# The Windows-side venv, build/ and dist/ are never touched, so rebuilds stay
# incremental.

set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST="${DEST:-/mnt/c/Users/shann/Documents/win_dev/seqrename}"

DRY=()
BUILD=0
for arg in "$@"; do
  case "$arg" in
    --dry-run|-n) DRY=(--dry-run) ;;
    --build|-b)   BUILD=1 ;;
    -h|--help)    sed -n '2,12p' "$0"; exit 0 ;;
    *) echo "Unknown option: $arg" >&2; exit 2 ;;
  esac
done

if [[ ! -d "$(dirname "$DEST")" ]]; then
  echo "Destination parent does not exist: $(dirname "$DEST")" >&2
  echo "Is the Windows drive mounted at /mnt/c ?" >&2
  exit 1
fi

mkdir -p "$DEST"

echo "  source: $SRC"
echo "  target: $DEST"
echo

# --delete keeps the target a mirror; excluded paths on the target are left
# alone by rsync, which is what protects the Windows venv and dist folder.
rsync -rlt --delete "${DRY[@]+"${DRY[@]}"}" \
  --exclude '.git/' \
  --exclude '.venv/' \
  --exclude 'venv/' \
  --exclude '__pycache__/' \
  --exclude '*.pyc' \
  --exclude '.pytest_cache/' \
  --exclude '.ruff_cache/' \
  --exclude 'build/' \
  --exclude 'dist/' \
  --exclude 'releases/' \
  --exclude '*.egg-info/' \
  --itemize-changes \
  "$SRC/" "$DEST/"

# Windows tolerates LF fine in PowerShell, but CRLF avoids surprises in editors.
if [[ ${#DRY[@]} -eq 0 ]] && command -v unix2dos >/dev/null 2>&1; then
  unix2dos -q "$DEST"/*.ps1 2>/dev/null || true
fi

echo
echo "Synced."

if [[ $BUILD -eq 1 && ${#DRY[@]} -eq 0 ]]; then
  WIN_DEST="$(wslpath -w "$DEST")"
  echo "Building on Windows: $WIN_DEST"
  powershell.exe -NoProfile -ExecutionPolicy Bypass \
    -File "$WIN_DEST\\build.ps1" -Root "$WIN_DEST"
else
  echo "Next, in Windows PowerShell:"
  echo "    cd '$(wslpath -w "$DEST" 2>/dev/null || echo "$DEST")'"
  echo "    .\\build.ps1          # package SeqRename.exe"
  echo "    .\\run-dev.ps1        # or just run it from source"
fi
