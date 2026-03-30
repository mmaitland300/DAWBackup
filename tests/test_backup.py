"""Integration tests for backup behavior."""

from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

from spb.core.backup import run_backup


class BackupIntegrationTests(unittest.TestCase):
    """Exercise the backup engine against real filesystem state."""

    def test_initial_repeat_and_incremental_backup(self) -> None:
        with (
            tempfile.TemporaryDirectory() as source_dir,
            tempfile.TemporaryDirectory() as dest_dir,
        ):
            source = Path(source_dir)
            dest = Path(dest_dir)
            _write_file(source / "song.txt", "v1")
            _write_file(source / "nested" / "mix.txt", "mix-a")

            first = run_backup(source, dest)
            self.assertEqual(first.summary.scanned_files, 2)
            self.assertEqual(first.summary.copied_files, 2)
            self.assertEqual(first.summary.unchanged_files, 0)
            self.assertEqual(first.summary.skipped_entries, 0)
            self.assertEqual(first.summary.deleted_in_source, 0)
            self.assertEqual(first.summary.error_count, 0)
            self.assertTrue((dest / ".spb" / "manifest.sqlite").exists())
            self.assertEqual((dest / "song.txt").read_text(encoding="utf-8"), "v1")
            self.assertEqual(
                (dest / "nested" / "mix.txt").read_text(encoding="utf-8"),
                "mix-a",
            )

            second = run_backup(source, dest)
            self.assertEqual(second.summary.scanned_files, 2)
            self.assertEqual(second.summary.copied_files, 0)
            self.assertEqual(second.summary.unchanged_files, 2)
            self.assertEqual(second.summary.skipped_entries, 0)
            self.assertEqual(second.summary.deleted_in_source, 0)
            self.assertEqual(second.summary.error_count, 0)

            _write_file(source / "song.txt", "v2")
            _write_file(source / "nested" / "new.txt", "fresh")

            third = run_backup(source, dest)
            self.assertEqual(third.summary.scanned_files, 3)
            self.assertEqual(third.summary.copied_files, 2)
            self.assertEqual(third.summary.unchanged_files, 1)
            self.assertEqual(third.summary.skipped_entries, 0)
            self.assertEqual(third.summary.deleted_in_source, 0)
            self.assertEqual(third.summary.error_count, 0)
            self.assertEqual((dest / "song.txt").read_text(encoding="utf-8"), "v2")
            self.assertEqual(
                (dest / "nested" / "new.txt").read_text(encoding="utf-8"),
                "fresh",
            )

    def test_deleted_files_remain_on_disk_and_restore_clears_flag(self) -> None:
        with (
            tempfile.TemporaryDirectory() as source_dir,
            tempfile.TemporaryDirectory() as dest_dir,
        ):
            source = Path(source_dir)
            dest = Path(dest_dir)
            _write_file(source / "keep.txt", "keep")
            _write_file(source / "remove.txt", "gone-soon")

            run_backup(source, dest)
            (source / "remove.txt").unlink()

            deleted_run = run_backup(source, dest)
            self.assertEqual(deleted_run.summary.deleted_in_source, 1)
            self.assertTrue((dest / "remove.txt").exists())

            db_path = dest / ".spb" / "manifest.sqlite"
            self.assertEqual(_deleted_flag_for(db_path, "remove.txt"), 1)

            _write_file(source / "remove.txt", "returned")
            restored_run = run_backup(source, dest)
            self.assertEqual(restored_run.summary.deleted_in_source, 0)
            self.assertEqual(restored_run.summary.copied_files, 1)
            self.assertEqual(_deleted_flag_for(db_path, "remove.txt"), 0)
            self.assertEqual(
                (dest / "remove.txt").read_text(encoding="utf-8"),
                "returned",
            )

    def test_top_level_reserved_path_is_skipped_but_nested_dot_spb_is_allowed(
        self,
    ) -> None:
        with (
            tempfile.TemporaryDirectory() as source_dir,
            tempfile.TemporaryDirectory() as dest_dir,
        ):
            source = Path(source_dir)
            dest = Path(dest_dir)
            _write_file(source / ".spb" / "ignored.txt", "skip-me")
            _write_file(source / "project" / ".spb" / "kept.txt", "keep-me")

            result = run_backup(source, dest)

            self.assertEqual(result.summary.scanned_files, 1)
            self.assertEqual(result.summary.copied_files, 1)
            self.assertEqual(result.summary.skipped_entries, 1)
            self.assertIn("Skipping reserved top-level path: .spb", result.warnings)
            self.assertTrue((dest / "project" / ".spb" / "kept.txt").exists())
            self.assertFalse((dest / ".spb" / "ignored.txt").exists())

    def test_symlinks_are_skipped_when_supported(self) -> None:
        with (
            tempfile.TemporaryDirectory() as source_dir,
            tempfile.TemporaryDirectory() as dest_dir,
        ):
            source = Path(source_dir)
            dest = Path(dest_dir)
            target = source / "real.txt"
            _write_file(target, "real")

            link_path = source / "real-link.txt"
            try:
                link_path.symlink_to(target)
            except (NotImplementedError, OSError):
                self.skipTest("Symlinks are not available in this environment.")

            result = run_backup(source, dest)
            self.assertEqual(result.summary.scanned_files, 1)
            self.assertEqual(result.summary.copied_files, 1)
            self.assertEqual(result.summary.skipped_entries, 1)
            self.assertIn("Skipping symlink file: real-link.txt", result.warnings)
            self.assertFalse((dest / "real-link.txt").exists())

    @unittest.skipUnless(
        hasattr(os, "mkfifo"),
        "Named pipes are not available on this platform.",
    )
    def test_non_ordinary_entries_are_skipped(self) -> None:
        with (
            tempfile.TemporaryDirectory() as source_dir,
            tempfile.TemporaryDirectory() as dest_dir,
        ):
            source = Path(source_dir)
            dest = Path(dest_dir)
            _write_file(source / "regular.txt", "regular")
            fifo_path = source / "pipe-entry"
            os.mkfifo(fifo_path)

            result = run_backup(source, dest)
            self.assertEqual(result.summary.scanned_files, 1)
            self.assertEqual(result.summary.copied_files, 1)
            self.assertEqual(result.summary.skipped_entries, 1)
            self.assertIn("Skipping non-regular file: pipe-entry", result.warnings)


def _deleted_flag_for(db_path: Path, relative_path: str) -> int:
    connection = sqlite3.connect(db_path)
    try:
        row = connection.execute(
            "SELECT deleted FROM files WHERE relative_path = ?",
            (relative_path,),
        ).fetchone()
    finally:
        connection.close()
    if row is None:
        msg = f"Missing manifest row for {relative_path}"
        raise AssertionError(msg)
    return int(row[0])


def _write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
