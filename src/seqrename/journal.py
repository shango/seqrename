"""Undo journal.

Journals live in per-user application data, not beside the renamed files: a
stray folder in a plate or render directory is clutter at best and something
that gets shipped to a client at worst. Each journal records which folder it
applies to, so the history for a folder can still be found.

Older versions wrote into ``<folder>/.seqrename``; :func:`migrate_legacy` moves
those into the user location and removes the folder.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

LEGACY_DIR = ".seqrename"
ENV_DIR = "SEQRENAME_JOURNAL_DIR"
RETENTION = 200  # journals kept before the oldest are pruned


def journal_dir() -> Path:
    """Where journals are stored for this user."""
    override = os.environ.get(ENV_DIR)
    if override:
        return Path(override)
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local"
        return Path(base) / "SeqRename" / "journals"
    base = os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share"
    return Path(base) / "seqrename" / "journals"


@dataclass
class JournalEntry:
    src: str
    dst: str


@dataclass
class Journal:
    id: str
    created: str
    mode: str  # "rename" | "move" | "copy"
    root: str
    entries: list[JournalEntry]
    path: Path | None = None

    @property
    def undone(self) -> bool:
        return self.path is not None and self.path.name.endswith(".undone.json")

    def describe(self) -> str:
        when = self.created.replace("T", " ")[:19]
        return f"{when}  {self.mode}  {len(self.entries)} files"


def _same_root(a: str, b: str) -> bool:
    a, b = os.path.normpath(a), os.path.normpath(b)
    if os.name == "nt":
        return a.lower() == b.lower()
    return a == b


def write(root: Path, mode: str, pairs: list[tuple[Path, Path]], now: datetime | None = None) -> Journal:
    now = now or datetime.now()
    jid = now.strftime("%Y%m%d-%H%M%S-%f")[:-3]
    journal = Journal(
        id=jid,
        created=now.isoformat(timespec="seconds"),
        mode=mode,
        root=str(root),
        entries=[JournalEntry(str(s), str(d)) for s, d in pairs],
    )
    directory = journal_dir()
    directory.mkdir(parents=True, exist_ok=True)
    journal.path = directory / f"journal-{jid}.json"
    journal.path.write_text(_dump(journal), encoding="utf-8")
    prune()
    return journal


def _dump(journal: Journal) -> str:
    return json.dumps(
        {
            "id": journal.id,
            "created": journal.created,
            "mode": journal.mode,
            "root": journal.root,
            "entries": [{"src": e.src, "dst": e.dst} for e in journal.entries],
        },
        indent=2,
    )


def load(path: Path) -> Journal:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return Journal(
        id=data["id"],
        created=data["created"],
        mode=data["mode"],
        root=data["root"],
        entries=[JournalEntry(e["src"], e["dst"]) for e in data["entries"]],
        path=Path(path),
    )


def history(root: Path, limit: int = 50) -> list[Journal]:
    """Journals recorded for ``root``, newest first."""
    found: list[Journal] = []
    for directory in (journal_dir(), Path(root) / LEGACY_DIR):
        if not directory.is_dir():
            continue
        for f in sorted(directory.glob("journal-*.json"), reverse=True):
            try:
                journal = load(f)
            except (OSError, ValueError, KeyError):
                continue
            if _same_root(journal.root, str(root)):
                found.append(journal)
    found.sort(key=lambda j: j.id, reverse=True)
    return found[:limit]


def mark_undone(journal: Journal) -> None:
    """Rename the journal file so it drops out of the undo queue."""
    if journal.path is None or journal.undone:
        return
    target = journal.path.with_name(journal.path.stem + ".undone.json")
    journal.path.replace(target)
    journal.path = target


def prune(keep: int = RETENTION) -> None:
    """Drop the oldest journals once there are more than ``keep``."""
    directory = journal_dir()
    if not directory.is_dir():
        return
    files = sorted(directory.glob("journal-*.json"), reverse=True)
    for old in files[keep:]:
        try:
            old.unlink()
        except OSError:
            continue


def migrate_legacy(root: Path) -> int:
    """Move a ``<root>/.seqrename`` folder into the user journal directory.

    Returns the number of journals moved. The folder is removed once it is
    empty, so nothing of ours is left sitting next to the renamed files.
    """
    legacy = Path(root) / LEGACY_DIR
    if not legacy.is_dir():
        return 0

    target = journal_dir()
    target.mkdir(parents=True, exist_ok=True)
    moved = 0
    for f in legacy.glob("*.json"):
        destination = target / f.name
        if destination.exists():
            destination = target / f"{f.stem}-{f.stat().st_mtime_ns}{f.suffix}"
        try:
            f.replace(destination)
        except OSError:
            try:  # different volume
                destination.write_bytes(f.read_bytes())
                f.unlink()
            except OSError:
                continue
        moved += 1

    try:
        legacy.rmdir()
    except OSError:
        pass  # something else is in there; leave it alone
    return moved
