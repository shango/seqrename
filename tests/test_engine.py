from __future__ import annotations

from pathlib import Path

import pytest

from seqrename import (
    journal,
    Case,
    ExtCase,
    OutputMode,
    Plan,
    RenameOps,
    Status,
    VersionOp,
    last_undoable,
    scan,
    undo,
)
from seqrename.scanner import split_stem


def touch(directory: Path, *names: str) -> None:
    for n in names:
        (directory / n).write_bytes(b"x" * 10)


def make_seq(directory: Path, prefix: str, frames, pad=4, ext=".exr") -> None:
    for f in frames:
        touch(directory, f"{prefix}{f:0{pad}d}{ext}")


# -- detection -----------------------------------------------------------


@pytest.mark.parametrize(
    "stem,expected",
    [
        ("shot010.1001", ("shot010.", 1001, "1001", "")),
        ("shot010_1001", ("shot010_", 1001, "1001", "")),
        ("frame1001", ("frame", 1001, "1001", "")),
        # Ambiguous: no separator and the name itself ends in digits, so the
        # whole trailing run is the frame token.  Grouping stays consistent.
        ("shot0101001", ("shot", 101001, "0101001", "")),
        ("comp_v003.1001", ("comp_v003.", 1001, "1001", "")),
        ("render.1001.beauty", ("render.", 1001, "1001", ".beauty")),
        ("plate.-0001", ("plate.", -1, "0001", "")),
        ("plate-01", ("plate-", 1, "01", "")),
        ("frame.0000", ("frame.", 0, "0000", "")),
        ("nodigits", None),
    ],
)
def test_split_stem(stem, expected):
    assert split_stem(stem) == expected


def test_scan_groups_and_reports(tmp_path):
    make_seq(tmp_path, "shot_", [1001, 1002, 1004])
    make_seq(tmp_path, "other.", [1, 2], pad=3, ext=".dpx")
    touch(tmp_path, "notes.txt", "single.0001.exr")

    seqs = scan(tmp_path)
    assert len(seqs) == 2
    by_name = {s.display_name(): s for s in seqs}
    a = by_name["other.###.dpx"]
    b = by_name["shot_####.exr"]
    assert b.missing == [1003]
    assert b.range_str() == "1001-1002,1004"
    assert a.count == 2 and a.padding == 3
    assert b.total_size == 30


def test_scan_include_single_and_recursive(tmp_path):
    sub = tmp_path / "sub"
    sub.mkdir()
    touch(tmp_path, "single.0001.exr")
    make_seq(sub, "deep.", [1, 2])

    assert scan(tmp_path) == []
    assert len(scan(tmp_path, include_single=True)) == 1
    assert len(scan(tmp_path, recursive=True)) == 1
    assert len(scan(tmp_path, recursive=True, include_single=True)) == 2


def test_inconsistent_padding_flagged(tmp_path):
    touch(tmp_path, "mix.1001.exr", "mix.01002.exr", "mix.1003.exr")
    seq = scan(tmp_path)[0]
    assert not seq.padding_consistent
    assert seq.padding == 4


# -- preview -------------------------------------------------------------


def test_replace_and_repad(tmp_path):
    make_seq(tmp_path, "shot_v001.", [1001, 1002])
    seq = scan(tmp_path)[0]
    ops = RenameOps(find="v001", replace="v002", repad=True, pad=5)
    entries = Plan([seq], ops).preview()
    assert [e.dst.name for e in entries] == ["shot_v002.01001.exr", "shot_v002.01002.exr"]
    assert all(e.status is Status.OK for e in entries)


def test_regex_and_case_and_ext(tmp_path):
    touch(tmp_path, "SHOT_A.1001.EXR", "SHOT_A.1002.EXR")
    seq = scan(tmp_path)[0]
    ops = RenameOps(
        find=r"SHOT_(\w+)\.",
        replace=r"sh\1.",
        use_regex=True,
        case=Case.LOWER,
        ext_case=ExtCase.LOWER,
    )
    assert [e.dst.name for e in Plan([seq], ops).preview()] == ["sha.1001.exr", "sha.1002.exr"]


def test_version_ops(tmp_path):
    make_seq(tmp_path, "cmp_v003.", [1])
    seq = scan(tmp_path, include_single=True)[0]
    bump = Plan([seq], RenameOps(version_op=VersionOp.BUMP)).preview()
    assert bump[0].dst.name == "cmp_v004.0001.exr"
    setv = Plan([seq], RenameOps(version_op=VersionOp.SET, version_value=12, version_pad=3)).preview()
    assert setv[0].dst.name == "cmp_v012.0001.exr"
    strip = Plan([seq], RenameOps(version_op=VersionOp.STRIP)).preview()
    assert strip[0].dst.name == "cmp_.0001.exr"


def test_renumber_step_and_reverse(tmp_path):
    make_seq(tmp_path, "s.", [1001, 1002, 1003])
    seq = scan(tmp_path)[0]
    ops = RenameOps(renumber=True, start=1, step=2)
    assert [e.dst.name for e in Plan([seq], ops).preview()] == ["s.0001.exr", "s.0003.exr", "s.0005.exr"]
    rev = RenameOps(renumber=True, start=1, step=1, reverse=True)
    assert [e.dst.name for e in Plan([seq], rev).preview()] == ["s.0003.exr", "s.0002.exr", "s.0001.exr"]


def test_negative_frames_round_trip(tmp_path):
    touch(tmp_path, "h.-0002.exr", "h.-0001.exr")
    seq = scan(tmp_path)[0]
    assert seq.numbers == [-2, -1]
    entries = Plan([seq], RenameOps(offset=2)).preview()
    assert [e.dst.name for e in entries] == ["h.0000.exr", "h.0001.exr"]


def test_collision_and_duplicate_detected(tmp_path):
    make_seq(tmp_path, "a.", [1001, 1002])
    touch(tmp_path, "b.1001.exr")
    seq = [s for s in scan(tmp_path) if s.prefix == "a."][0]
    collide = Plan([seq], RenameOps(find="a.", replace="b.")).preview()
    assert collide[0].status is Status.COLLISION
    assert collide[1].status is Status.OK

    bad_step = Plan([seq], RenameOps(renumber=True, start=5, step=0))
    assert bad_step.preview() == []
    assert "step" in bad_step.error


def test_repad_can_create_duplicates(tmp_path):
    """Mixed padding on the same frame number collapses to one target."""
    touch(tmp_path, "a.1001.exr", "a.01001.exr")
    seq = scan(tmp_path)[0]
    entries = Plan([seq], RenameOps(repad=True, pad=5)).preview()
    assert [e.status for e in entries].count(Status.DUPLICATE) == 1


def test_unchanged_entries(tmp_path):
    make_seq(tmp_path, "a.", [1001])
    seq = scan(tmp_path, include_single=True)[0]
    assert Plan([seq], RenameOps()).preview()[0].status is Status.UNCHANGED


# -- commit --------------------------------------------------------------


def test_commit_and_undo_round_trip(tmp_path):
    make_seq(tmp_path, "shot_", [1001, 1002, 1003])
    before = sorted(p.name for p in tmp_path.glob("*.exr"))
    plan = Plan(scan(tmp_path), RenameOps(find="shot_", replace="plate_", repad=True, pad=5))
    result = plan.commit()

    assert result.ok and result.moved == 3
    assert sorted(p.name for p in tmp_path.glob("*.exr")) == [
        "plate_01001.exr", "plate_01002.exr", "plate_01003.exr",
    ]

    jrn = last_undoable(tmp_path)
    assert jrn is not None
    assert undo(jrn).ok
    assert sorted(p.name for p in tmp_path.glob("*.exr")) == before
    assert last_undoable(tmp_path) is None


def test_commit_leaves_nothing_beside_the_files(tmp_path):
    """The journal must not litter the folder holding the renamed sequence."""
    make_seq(tmp_path, "s.", [1001, 1002])
    assert Plan(scan(tmp_path), RenameOps(find="s.", replace="t.")).commit().ok

    assert not (tmp_path / journal.LEGACY_DIR).exists()
    assert sorted(p.name for p in tmp_path.iterdir()) == ["t.1001.exr", "t.1002.exr"]
    # ...but the journal still exists, in the per-user location.
    assert last_undoable(tmp_path) is not None


def test_legacy_journal_folder_is_migrated_and_removed(tmp_path):
    """A .seqrename folder from an older version is swept up on scan."""
    make_seq(tmp_path, "s.", [1001, 1002])
    plan = Plan(scan(tmp_path), RenameOps(find="s.", replace="t."))
    assert plan.commit().ok

    # Put the journal back where the old version used to write it.
    legacy = tmp_path / journal.LEGACY_DIR
    legacy.mkdir()
    current = last_undoable(tmp_path)
    (legacy / current.path.name).write_bytes(current.path.read_bytes())
    current.path.unlink()
    assert legacy.exists()

    assert journal.migrate_legacy(tmp_path) == 1
    assert not legacy.exists()

    # Undo still works after the move.
    restored = last_undoable(tmp_path)
    assert restored is not None
    assert undo(restored).ok
    assert sorted(p.name for p in tmp_path.glob("*.exr")) == ["s.1001.exr", "s.1002.exr"]


def test_migrate_legacy_keeps_a_folder_holding_other_files(tmp_path):
    legacy = tmp_path / journal.LEGACY_DIR
    legacy.mkdir()
    (legacy / "notes.txt").write_text("someone else's file")
    assert journal.migrate_legacy(tmp_path) == 0
    assert legacy.exists()


def test_journal_retention_prunes_the_oldest(tmp_path):
    from datetime import datetime, timedelta

    start = datetime(2026, 1, 1, 12, 0, 0)
    for i in range(8):
        journal.write(tmp_path, "rename", [(tmp_path / f"a{i}", tmp_path / f"b{i}")],
                      now=start + timedelta(seconds=i))
    journal.prune(keep=3)
    assert len(list(journal.journal_dir().glob("journal-*.json"))) == 3


def test_recursive_commit_journals_at_the_scanned_root(tmp_path):
    sub = tmp_path / "shot" / "beauty"
    sub.mkdir(parents=True)
    make_seq(sub, "s.", [1001, 1002])
    plan = Plan(scan(tmp_path, recursive=True), RenameOps(find="s.", replace="t."))
    assert plan.commit(journal_root=tmp_path).ok

    jrn = last_undoable(tmp_path)
    assert jrn is not None
    assert undo(jrn).ok
    assert sorted(p.name for p in sub.glob("*.exr")) == ["s.1001.exr", "s.1002.exr"]


def test_cycle_safe_shift(tmp_path):
    """Shifting +1 inside the same sequence must not clobber."""
    make_seq(tmp_path, "s.", [1001, 1002, 1003])
    plan = Plan(scan(tmp_path), RenameOps(offset=1))
    assert plan.commit().ok
    assert sorted(p.name for p in tmp_path.glob("*.exr")) == [
        "s.1002.exr", "s.1003.exr", "s.1004.exr",
    ]
    assert undo(last_undoable(tmp_path)).ok
    assert sorted(p.name for p in tmp_path.glob("*.exr")) == [
        "s.1001.exr", "s.1002.exr", "s.1003.exr",
    ]


def test_reverse_in_place_is_cycle_safe(tmp_path):
    for i, n in enumerate([1001, 1002, 1003]):
        (tmp_path / f"s.{n}.exr").write_bytes(bytes([i]))
    assert Plan(scan(tmp_path), RenameOps(reverse=True)).commit().ok
    assert (tmp_path / "s.1001.exr").read_bytes() == bytes([2])
    assert (tmp_path / "s.1003.exr").read_bytes() == bytes([0])


def test_commit_refuses_collisions(tmp_path):
    make_seq(tmp_path, "a.", [1001])
    touch(tmp_path, "b.1001.exr")
    seq = [s for s in scan(tmp_path, include_single=True) if s.prefix == "a."][0]
    plan = Plan([seq], RenameOps(find="a.", replace="b."))
    result = plan.commit()
    assert not result.ok and "collide" in result.error
    assert (tmp_path / "a.1001.exr").exists()


def test_force_overwrites(tmp_path):
    (tmp_path / "a.1001.exr").write_bytes(b"new")
    (tmp_path / "b.1001.exr").write_bytes(b"old")
    seq = [s for s in scan(tmp_path, include_single=True) if s.prefix == "a."][0]
    assert Plan([seq], RenameOps(find="a.", replace="b.")).commit(force=True).ok
    assert (tmp_path / "b.1001.exr").read_bytes() == b"new"


def test_move_to_directory(tmp_path):
    src = tmp_path / "in"
    src.mkdir()
    dest = tmp_path / "out" / "v002"
    make_seq(src, "s.", [1001, 1002])
    ops = RenameOps(mode=OutputMode.MOVE, dest=str(dest))
    assert Plan(scan(src), ops).commit().ok
    assert len(list(dest.glob("*.exr"))) == 2
    assert not list(src.glob("*.exr"))


def test_move_without_destination_is_rejected(tmp_path):
    make_seq(tmp_path, "s.", [1001, 1002])
    plan = Plan(scan(tmp_path), RenameOps(mode=OutputMode.MOVE))
    assert plan.preview() == []
    assert "destination" in plan.error
    assert not plan.commit().ok


def test_copy_leaves_source_and_undo_removes_copies(tmp_path):
    src = tmp_path / "in"
    src.mkdir()
    dest = tmp_path / "out"
    make_seq(src, "s.", [1001, 1002])
    ops = RenameOps(mode=OutputMode.COPY, dest=str(dest))
    assert Plan(scan(src), ops).commit(verify=True).ok
    assert len(list(src.glob("*.exr"))) == 2
    assert len(list(dest.glob("*.exr"))) == 2

    assert undo(last_undoable(src)).ok
    assert not list(dest.glob("*.exr"))
    assert len(list(src.glob("*.exr"))) == 2


def test_rollback_on_failure(tmp_path, monkeypatch):
    make_seq(tmp_path, "s.", [1001, 1002, 1003])
    plan = Plan(scan(tmp_path), RenameOps(find="s.", replace="t."))
    plan.preview()

    calls = {"n": 0}
    import seqrename.fsops as fsops
    original = fsops.move

    def flaky(src, dst, **kw):
        calls["n"] += 1
        if calls["n"] == 3:
            raise OSError("disk on fire")
        original(src, dst, **kw)

    monkeypatch.setattr(fsops, "move", flaky)
    result = plan.commit()
    assert not result.ok and result.rolled_back
    assert sorted(p.name for p in tmp_path.glob("*.exr")) == [
        "s.1001.exr", "s.1002.exr", "s.1003.exr",
    ]


def test_read_only_files_are_not_flagged(tmp_path):
    """Delivered plates are often read-only; that never blocks a rename."""
    make_seq(tmp_path, "s.", [1001, 1002])
    for f in tmp_path.glob("*.exr"):
        f.chmod(0o444)
    plan = Plan(scan(tmp_path), RenameOps(find="s.", replace="t."))
    assert plan.validate() == []
    assert plan.commit().ok


def test_validate_reports_missing_source(tmp_path):
    make_seq(tmp_path, "s.", [1001, 1002])
    plan = Plan(scan(tmp_path), RenameOps(find="s.", replace="t."))
    plan.preview()
    (tmp_path / "s.1001.exr").unlink()
    assert any("gone" in p for p in plan.validate())
