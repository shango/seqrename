"""Undo journal: one JSON file per commit, written next to the source files."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

JOURNAL_DIR = ".seqrename"


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
    directory = Path(root) / JOURNAL_DIR
    directory.mkdir(parents=True, exist_ok=True)
    journal.path = directory / f"journal-{jid}.json"
    journal.path.write_text(
        json.dumps(
            {
                "id": journal.id,
                "created": journal.created,
                "mode": journal.mode,
                "root": journal.root,
                "entries": [{"src": e.src, "dst": e.dst} for e in journal.entries],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return journal


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
    """Journals under ``root``, newest first."""
    directory = Path(root) / JOURNAL_DIR
    if not directory.is_dir():
        return []
    files = sorted(directory.glob("journal-*.json"), reverse=True)
    out = []
    for f in files[:limit]:
        try:
            out.append(load(f))
        except (OSError, ValueError, KeyError):
            continue
    return out


def mark_undone(journal: Journal) -> None:
    """Rename the journal file so it drops out of the undo queue."""
    if journal.path is None or journal.undone:
        return
    target = journal.path.with_name(journal.path.stem + ".undone.json")
    journal.path.replace(target)
    journal.path = target
