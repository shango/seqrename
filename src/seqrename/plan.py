"""Preview, validation and transactional commit."""

from __future__ import annotations

import os
import uuid
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable, Iterable

from . import fsops, journal
from .journal import Journal
from .ops import OpError, OutputMode, RenameOps, target_names
from .scanner import Sequence

Progress = Callable[[int, int, str], None]


class Status(str, Enum):
    OK = "ok"
    UNCHANGED = "unchanged"
    COLLISION = "collision"      # target already exists on disk
    DUPLICATE = "duplicate"      # two sources map to the same target

    @property
    def blocking(self) -> bool:
        return self in (Status.COLLISION, Status.DUPLICATE)


@dataclass
class Entry:
    src: Path
    dst: Path
    status: Status
    note: str = ""
    sequence: str = ""

    @property
    def changed(self) -> bool:
        return self.status is not Status.UNCHANGED


@dataclass
class CommitResult:
    moved: int = 0
    mode: str = "rename"
    journal: Journal | None = None
    rolled_back: bool = False
    error: str = ""

    @property
    def ok(self) -> bool:
        return not self.error


class Plan:
    """A set of sequences plus the operations to apply to them."""

    def __init__(self, sequences: Iterable[Sequence], ops: RenameOps):
        self.sequences = list(sequences)
        self.ops = ops
        self._entries: list[Entry] | None = None
        self._error: str = ""

    # -- preview ---------------------------------------------------------

    @property
    def error(self) -> str:
        if self._entries is None:
            self.preview()
        return self._error

    def preview(self) -> list[Entry]:
        if self._entries is None:
            self._entries = self._build()
        return self._entries

    def _dest_dir(self, seq: Sequence) -> Path:
        if self.ops.mode is OutputMode.RENAME or not self.ops.dest:
            return seq.directory
        return Path(self.ops.dest)

    def _build(self) -> list[Entry]:
        self._error = ""
        entries: list[Entry] = []
        if self.ops.mode is not OutputMode.RENAME:
            if not self.ops.dest:
                self._error = f"Choose a destination folder to {self.ops.mode.value} into."
                return []
            if Path(self.ops.dest).is_file():
                self._error = f"Destination is a file, not a folder: {self.ops.dest}"
                return []
        try:
            pairs: list[tuple[Sequence, Path, Path]] = []
            for seq in self.sequences:
                dest = self._dest_dir(seq)
                for frame, name in zip(seq.frames, target_names(seq, self.ops)):
                    pairs.append((seq, frame.path, dest / name))
        except OpError as exc:
            self._error = str(exc)
            return []

        src_keys = {fsops.norm(src) for _, src, _ in pairs}
        seen: dict[str, Path] = {}
        existing = self._existing_targets(d for _, _, d in pairs)

        for seq, src, dst in pairs:
            key = fsops.norm(dst)
            status, note = Status.OK, ""
            if src == dst:
                status = Status.UNCHANGED
            elif key in seen:
                status = Status.DUPLICATE
                note = f"also the target of {seen[key].name}"
            elif key in existing and key not in src_keys:
                status = Status.COLLISION
                note = "target already exists"
            seen[key] = src
            entries.append(Entry(src, dst, status, note, seq.display_name()))
        return entries

    @staticmethod
    def _existing_targets(targets: Iterable[Path]) -> set[str]:
        """One scandir per destination directory instead of a stat per file."""
        dirs = {t.parent for t in targets}
        found: set[str] = set()
        for d in dirs:
            try:
                with os.scandir(d) as it:
                    found.update(fsops.norm(Path(e.path)) for e in it)
            except OSError:
                continue
        return found

    # -- summary ---------------------------------------------------------

    def counts(self) -> dict[Status, int]:
        out: dict[Status, int] = defaultdict(int)
        for e in self.preview():
            out[e.status] += 1
        return dict(out)

    @property
    def blocking(self) -> list[Entry]:
        return [e for e in self.preview() if e.status.blocking]

    @property
    def actionable(self) -> list[Entry]:
        return [e for e in self.preview() if e.status is Status.OK]

    # -- validation ------------------------------------------------------

    def validate(self, progress: Progress | None = None) -> list[str]:
        """Pre-commit checks that touch the filesystem: locks and permissions.

        Runs here rather than in preview so that scanning stays cheap.
        """
        problems: list[str] = []
        entries = self.actionable
        if not entries:
            return ["Nothing to do."]

        dests = {e.dst.parent for e in entries}
        for d in dests:
            if not d.exists():
                if self.ops.mode is OutputMode.RENAME:
                    problems.append(f"Missing directory: {d}")
                continue
            if not fsops.is_writable(d):
                problems.append(f"Directory is not writable: {d}")

        copying = self.ops.mode is OutputMode.COPY
        total = len(entries)
        for i, e in enumerate(entries):
            if progress and i % 64 == 0:
                progress(i, total, "Checking for locked files")
            if not e.src.exists():
                problems.append(f"Source is gone: {e.src.name}")
            elif not copying and fsops.is_locked(e.src):
                problems.append(f"Locked by another program: {e.src.name}")
            if len(problems) >= 20:
                problems.append("... more problems not listed")
                break
        return problems

    # -- commit ----------------------------------------------------------

    def commit(
        self,
        *,
        progress: Progress | None = None,
        force: bool = False,
        verify: bool = False,
        journal_root: Path | None = None,
    ) -> CommitResult:
        """Execute the plan.  Rolls back everything on any failure.

        ``journal_root`` is where the undo journal is written; pass the folder
        the user scanned so a recursive commit stays undoable from one place.
        """
        if self.error:
            return CommitResult(error=self.error)
        entries = [e for e in self.preview() if e.status is Status.OK]
        if not force:
            blocking = self.blocking
            if blocking:
                return CommitResult(
                    error=f"{len(blocking)} file(s) would collide - resolve them or enable Force."
                )
        else:
            entries += [e for e in self.preview() if e.status is Status.COLLISION]
        if not entries:
            return CommitResult(error="Nothing to do.")

        copying = self.ops.mode is OutputMode.COPY
        mode = "copy" if copying else self.ops.mode.value
        for d in {e.dst.parent for e in entries}:
            d.mkdir(parents=True, exist_ok=True)

        done: list[tuple[Path, Path]] = []
        temps: list[tuple[Path, Path]] = []  # (temp, final) awaiting phase two
        total = len(entries)
        try:
            two_phase = not copying and self._overlaps(entries)
            token = uuid.uuid4().hex[:8]
            for i, e in enumerate(entries):
                if progress:
                    progress(i, total, e.src.name)
                if copying:
                    fsops.copy(e.src, e.dst, verify=verify)
                    done.append((e.src, e.dst))
                elif two_phase:
                    tmp = e.dst.with_name(f".seqrename-{token}-{i:07d}.tmp")
                    fsops.move(e.src, tmp, verify=verify)
                    done.append((e.src, tmp))
                    temps.append((tmp, e.dst))
                else:
                    fsops.move(e.src, e.dst, verify=verify)
                    done.append((e.src, e.dst))

            for i, (tmp, dst) in enumerate(temps):
                if progress:
                    progress(i, total, dst.name)
                os.replace(fsops.long_path(tmp), fsops.long_path(dst))
                done[i] = (done[i][0], dst)
        except (OSError, ValueError) as exc:
            self._rollback(done, copying)
            return CommitResult(mode=mode, rolled_back=True, error=str(exc))

        if progress:
            progress(total, total, "Writing journal")
        root = journal_root or (
            self.sequences[0].directory if self.sequences else entries[0].src.parent
        )
        jrn = journal.write(root, mode, done)
        self._entries = None  # preview is stale now
        return CommitResult(moved=len(done), mode=mode, journal=jrn)

    @staticmethod
    def _overlaps(entries: list[Entry]) -> bool:
        """True when a target path is also somebody else's source path."""
        srcs = {fsops.norm(e.src) for e in entries}
        return any(fsops.norm(e.dst) in srcs - {fsops.norm(e.src)} for e in entries)

    @staticmethod
    def _rollback(done: list[tuple[Path, Path]], copying: bool) -> None:
        for src, dst in reversed(done):
            try:
                if copying:
                    os.remove(fsops.long_path(dst))
                else:
                    fsops.move(dst, src)
            except OSError:
                continue


# -- undo ----------------------------------------------------------------


def undo(jrn: Journal, *, progress: Progress | None = None) -> CommitResult:
    """Revert a journalled commit.

    Renames and moves go back to their original paths; a copy commit is undone
    by deleting the files it created.
    """
    pairs = [(Path(e.dst), Path(e.src)) for e in jrn.entries]
    total = len(pairs)
    done: list[tuple[Path, Path]] = []

    if jrn.mode == "copy":
        for i, (created, _) in enumerate(pairs):
            if progress:
                progress(i, total, created.name)
            try:
                os.remove(fsops.long_path(created))
                done.append((created, created))
            except FileNotFoundError:
                continue
            except OSError as exc:
                return CommitResult(mode=jrn.mode, error=str(exc))
        journal.mark_undone(jrn)
        return CommitResult(moved=len(done), mode=jrn.mode)

    missing = [str(s) for s, _ in pairs if not s.exists()]
    if missing:
        return CommitResult(
            mode=jrn.mode,
            error=f"{len(missing)} file(s) from this operation are no longer where the journal expects them.",
        )
    try:
        srcs = {fsops.norm(s) for s, _ in pairs}
        two_phase = any(fsops.norm(d) in srcs - {fsops.norm(s)} for s, d in pairs)
        token = uuid.uuid4().hex[:8]
        temps: list[tuple[Path, Path]] = []
        for i, (src, dst) in enumerate(pairs):
            if progress:
                progress(i, total, src.name)
            dst.parent.mkdir(parents=True, exist_ok=True)
            if two_phase:
                tmp = dst.with_name(f".seqrename-{token}-{i:07d}.tmp")
                fsops.move(src, tmp)
                done.append((src, tmp))
                temps.append((tmp, dst))
            else:
                fsops.move(src, dst)
                done.append((src, dst))
        for i, (tmp, dst) in enumerate(temps):
            os.replace(fsops.long_path(tmp), fsops.long_path(dst))
            done[i] = (done[i][0], dst)
    except OSError as exc:
        Plan._rollback(done, False)
        return CommitResult(mode=jrn.mode, rolled_back=True, error=str(exc))

    journal.mark_undone(jrn)
    return CommitResult(moved=len(done), mode=jrn.mode)


def last_undoable(root: Path) -> Journal | None:
    for j in journal.history(root):
        if not j.undone:
            return j
    return None
