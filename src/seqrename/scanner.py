"""Sequence detection.

Groups files in a directory into image sequences by (prefix, suffix, extension),
treating the last run of digits in the stem as the frame number.
"""

from __future__ import annotations

import os
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

# Extensions we consider part of a renderable sequence by default.
IMAGE_EXTS = {
    ".exr", ".dpx", ".tif", ".tiff", ".png", ".jpg", ".jpeg", ".tga",
    ".cin", ".hdr", ".bmp", ".psd", ".sgi", ".rat", ".webp",
}

_DIGITS = re.compile(r"\d+")


@dataclass(frozen=True)
class Frame:
    """One file of a sequence."""

    number: int
    path: Path
    digits: str  # the frame token as it appears on disk, e.g. "01002"
    size: int


@dataclass
class Sequence:
    """A group of files sharing everything but a frame number.

    A file name is decomposed as ``prefix + frame + suffix + ext``, e.g.
    ``shot010_comp.1001.beauty.exr`` -> prefix ``shot010_comp.``,
    frame ``1001``, suffix ``.beauty``, ext ``.exr``.
    """

    directory: Path
    prefix: str
    suffix: str
    ext: str
    frames: list[Frame] = field(default_factory=list)

    @property
    def numbers(self) -> list[int]:
        return [f.number for f in self.frames]

    @property
    def start(self) -> int:
        return self.frames[0].number

    @property
    def end(self) -> int:
        return self.frames[-1].number

    @property
    def count(self) -> int:
        return len(self.frames)

    @property
    def total_size(self) -> int:
        return sum(f.size for f in self.frames)

    @property
    def padding(self) -> int:
        """Most common digit width in the sequence."""
        widths = Counter(len(f.digits) for f in self.frames)
        return widths.most_common(1)[0][0]

    @property
    def padding_consistent(self) -> bool:
        return len({len(f.digits) for f in self.frames}) == 1

    @property
    def missing(self) -> list[int]:
        """Frame numbers absent between start and end."""
        if self.count < 2:
            return []
        present = set(self.numbers)
        return [n for n in range(self.start, self.end + 1) if n not in present]

    @property
    def is_single(self) -> bool:
        return self.count == 1

    def display_name(self) -> str:
        """Human-facing name, e.g. ``shot010_comp.####.beauty.exr``."""
        pad = "#" * self.padding
        return f"{self.prefix}{pad}{self.suffix}{self.ext}"

    def range_str(self) -> str:
        """fileseq-style range, e.g. ``1001-1050`` or ``1001-1010,1020-1050``."""
        if not self.frames:
            return ""
        parts: list[str] = []
        run_start = prev = self.numbers[0]
        for n in self.numbers[1:]:
            if n == prev + 1:
                prev = n
                continue
            parts.append(str(run_start) if run_start == prev else f"{run_start}-{prev}")
            run_start = prev = n
        parts.append(str(run_start) if run_start == prev else f"{run_start}-{prev}")
        return ",".join(parts)

    def sort_key(self) -> tuple:
        return (str(self.directory).lower(), self.prefix.lower(), self.ext.lower())


def split_stem(stem: str) -> tuple[str, int, str, str] | None:
    """Split a file stem into (prefix, frame_number, digits, suffix).

    Uses the *last* run of digits, so ``shot010_v003.1001`` frames on 1001.
    The whole run is taken, so an unseparated name that ends in digits
    (``shot0101001``) is ambiguous and frames on ``0101001`` - grouping and
    renaming stay consistent, but the padding is reported as the full run.
    A ``-`` immediately before the digits counts as a negative sign only when
    it follows a separator (or starts the stem), so ``plate-01`` stays positive
    but ``plate.-0001`` does not.  Returns ``None`` when the stem has no digits.
    """
    matches = list(_DIGITS.finditer(stem))
    if not matches:
        return None
    m = matches[-1]
    s, e = m.start(), m.end()
    digits = m.group()
    sign = 1
    if s > 0 and stem[s - 1] == "-" and (s == 1 or not stem[s - 2].isalnum()):
        s -= 1
        sign = -1
    return stem[:s], sign * int(digits), digits, stem[e:]


def scan(
    source: str | os.PathLike[str],
    *,
    recursive: bool = False,
    include_single: bool = False,
    exts: set[str] | None = None,
) -> list[Sequence]:
    """Detect sequences under ``source``.

    Uses ``os.scandir`` and reads size from the directory entry, so no extra
    ``stat`` call per file.
    """
    root = Path(source)
    exts = exts if exts is not None else IMAGE_EXTS
    groups: dict[tuple, Sequence] = {}

    for directory, entries in _walk(root, recursive):
        for entry in entries:
            name = entry.name
            dot = name.rfind(".")
            if dot <= 0:
                continue
            stem, ext = name[:dot], name[dot:]
            if exts and ext.lower() not in exts:
                continue
            parts = split_stem(stem)
            if parts is None:
                continue
            prefix, number, digits, suffix = parts
            key = (directory, prefix, suffix, ext.lower())
            seq = groups.get(key)
            if seq is None:
                seq = Sequence(directory=directory, prefix=prefix, suffix=suffix, ext=ext)
                groups[key] = seq
            try:
                size = entry.stat().st_size
            except OSError:
                size = 0
            seq.frames.append(Frame(number, directory / name, digits, size))

    result = []
    for seq in groups.values():
        if seq.is_single and not include_single:
            continue
        seq.frames.sort(key=lambda f: f.number)
        result.append(seq)
    result.sort(key=Sequence.sort_key)
    return result


def _walk(root: Path, recursive: bool):
    """Yield ``(directory, [DirEntry, ...])`` for files, skipping our own journals."""
    stack = [root]
    while stack:
        directory = stack.pop()
        files = []
        try:
            with os.scandir(directory) as it:
                for entry in it:
                    if entry.is_dir(follow_symlinks=False):
                        if recursive and entry.name != ".seqrename":
                            stack.append(Path(entry.path))
                    else:
                        files.append(entry)
        except OSError:
            continue
        yield directory, files
