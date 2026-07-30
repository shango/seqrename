"""Rename operations.

`RenameOps` is a flat description of everything the user asked for; `apply_ops`
turns a source frame into a target file name.  Operations are applied in a fixed
order: name edits -> case -> version -> renumber -> repad -> extension.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from .scanner import Sequence


class Case(str, Enum):
    KEEP = "keep"
    LOWER = "lower"
    UPPER = "upper"
    TITLE = "title"


class VersionOp(str, Enum):
    KEEP = "keep"
    BUMP = "bump"
    SET = "set"
    STRIP = "strip"


class ExtCase(str, Enum):
    KEEP = "keep"
    LOWER = "lower"
    UPPER = "upper"


class OutputMode(str, Enum):
    RENAME = "rename"  # in place
    MOVE = "move"      # to another directory
    COPY = "copy"      # to another directory, sources untouched


_VERSION = re.compile(r"(?P<v>v)(?P<num>\d+)", re.IGNORECASE)


class OpError(ValueError):
    """Raised when the operation settings themselves are invalid."""


@dataclass
class RenameOps:
    # name
    find: str = ""
    replace: str = ""
    use_regex: bool = False
    case: Case = Case.KEEP
    # version
    version_op: VersionOp = VersionOp.KEEP
    version_value: int = 1
    version_pad: int = 0  # 0 = keep the width found in the name
    # numbering
    renumber: bool = False
    start: int = 1001
    step: int = 1
    reverse: bool = False
    offset: int = 0  # applied when renumber is off
    # padding
    repad: bool = False
    pad: int = 4
    # extension
    ext_replace: str = ""  # e.g. "exr" or ".exr"
    ext_case: ExtCase = ExtCase.KEEP
    # output
    mode: OutputMode = OutputMode.RENAME
    dest: str = ""

    def is_noop(self) -> bool:
        return not (
            self.find
            or self.case is not Case.KEEP
            or self.version_op is not VersionOp.KEEP
            or self.renumber
            or self.offset
            or self.repad
            or self.ext_replace
            or self.ext_case is not ExtCase.KEEP
            or self.mode is not OutputMode.RENAME
        )


def _apply_text(text: str, ops: RenameOps) -> str:
    if ops.find:
        if ops.use_regex:
            try:
                text = re.sub(ops.find, ops.replace, text)
            except re.error as exc:
                raise OpError(f"Invalid regex: {exc}") from exc
        else:
            text = text.replace(ops.find, ops.replace)
    if ops.case is Case.LOWER:
        text = text.lower()
    elif ops.case is Case.UPPER:
        text = text.upper()
    elif ops.case is Case.TITLE:
        text = text.title()
    if ops.version_op is not VersionOp.KEEP:
        text = _apply_version(text, ops)
    return text


def _apply_version(text: str, ops: RenameOps) -> str:
    def sub(m: re.Match[str]) -> str:
        if ops.version_op is VersionOp.STRIP:
            return ""
        num = int(m.group("num"))
        new = num + 1 if ops.version_op is VersionOp.BUMP else ops.version_value
        width = ops.version_pad or len(m.group("num"))
        return f"{m.group('v')}{new:0{width}d}"

    return _VERSION.sub(sub, text)


def _new_numbers(seq: Sequence, ops: RenameOps) -> list[int]:
    """Target frame number for each source frame, in source order."""
    numbers = seq.numbers
    if ops.renumber:
        if ops.step == 0:
            raise OpError("Frame step cannot be 0.")
        order = list(range(len(numbers)))
        if ops.reverse:
            order.reverse()
        new = [0] * len(numbers)
        for slot, idx in enumerate(order):
            new[idx] = ops.start + slot * ops.step
        return new
    if ops.reverse:
        # Keep the existing number set, assign it in reverse to the frames.
        return list(reversed(numbers))
    return [n + ops.offset for n in numbers]


def _apply_ext(ext: str, ops: RenameOps) -> str:
    if ops.ext_replace:
        ext = ops.ext_replace if ops.ext_replace.startswith(".") else "." + ops.ext_replace
    if ops.ext_case is ExtCase.LOWER:
        ext = ext.lower()
    elif ops.ext_case is ExtCase.UPPER:
        ext = ext.upper()
    return ext


def target_names(seq: Sequence, ops: RenameOps) -> list[str]:
    """Compute the new file name for every frame of ``seq``, in source order."""
    prefix = _apply_text(seq.prefix, ops)
    suffix = _apply_text(seq.suffix, ops)
    ext = _apply_ext(seq.ext, ops)
    numbers = _new_numbers(seq, ops)

    names = []
    for frame, number in zip(seq.frames, numbers):
        width = ops.pad if ops.repad else len(frame.digits)
        sign = "-" if number < 0 else ""
        digits = f"{abs(number):0{width}d}"
        names.append(f"{prefix}{sign}{digits}{suffix}{ext}")
    return names
