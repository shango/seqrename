"""Filesystem primitives: path normalisation, volume checks, locks, verified copy."""

from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path

WINDOWS = os.name == "nt"


def norm(path: Path) -> str:
    """Comparison key for a path, case-folded on Windows."""
    s = os.path.normpath(str(path))
    return s.lower() if WINDOWS else s


def long_path(path: Path) -> str:
    r"""Windows ``\\?\`` prefixed string for paths near the 260 char limit."""
    s = str(path)
    if not WINDOWS or s.startswith("\\\\?\\"):
        return s
    s = os.path.abspath(s)
    if len(s) < 250:
        return s
    if s.startswith("\\\\"):
        return "\\\\?\\UNC\\" + s[2:]
    return "\\\\?\\" + s


def same_volume(a: Path, b: Path) -> bool:
    """True when a plain ``os.rename`` can move between the two paths."""
    if WINDOWS:
        return os.path.splitdrive(os.path.abspath(a))[0].lower() == \
            os.path.splitdrive(os.path.abspath(b))[0].lower()
    try:
        return os.stat(a).st_dev == os.stat(_existing_parent(b)).st_dev
    except OSError:
        return False


def _existing_parent(path: Path) -> Path:
    p = path if path.exists() else path.parent
    while not p.exists() and p != p.parent:
        p = p.parent
    return p


def is_locked(path: Path) -> bool:
    """True when another process holds the file open for writing.

    Only meaningful on Windows, where an exclusive open fails outright.  POSIX
    advisory locks are not checked.

    A read-only file is *not* a lock: renaming depends on the directory, not on
    the file's own permissions, so delivered read-only plates rename fine and
    must not be reported.
    """
    if not os.access(path, os.W_OK):
        return False
    try:
        fd = os.open(long_path(path), os.O_RDWR)
    except PermissionError:
        return True
    except OSError:
        return False
    os.close(fd)
    return False


def is_writable(path: Path) -> bool:
    return os.access(path, os.W_OK)


def checksum(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.blake2b(digest_size=16)
    with open(long_path(path), "rb") as fh:
        while block := fh.read(chunk):
            h.update(block)
    return h.hexdigest()


def move(src: Path, dst: Path, *, verify: bool = False) -> None:
    """Rename within a volume, copy+verify+delete across volumes."""
    if same_volume(src, dst):
        os.replace(long_path(src), long_path(dst))
        return
    copy(src, dst, verify=verify)
    os.remove(long_path(src))


def copy(src: Path, dst: Path, *, verify: bool = False) -> None:
    shutil.copy2(long_path(src), long_path(dst))
    if os.path.getsize(long_path(src)) != os.path.getsize(long_path(dst)):
        raise OSError(f"Size mismatch after copying {src.name}")
    if verify and checksum(src) != checksum(dst):
        raise OSError(f"Checksum mismatch after copying {src.name}")


def human_size(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"
