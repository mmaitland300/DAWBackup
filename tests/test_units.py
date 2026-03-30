"""Focused unit tests for core helpers and manifest transitions."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from spb.core.backup import _hash_file, normalize_relative_path
from spb.core.shared import BackupSummary
from spb.services.manifest import ManifestStore


class HelperUnitTests(unittest.TestCase):
    """Cover small helper behaviors directly."""

    def test_normalize_relative_path_uses_forward_slashes(self) -> None:
        path = Path("tracks") / "mixes" / "final.wav"
        self.assertEqual(normalize_relative_path(path), "tracks/mixes/final.wav")

    def test_hash_file_is_content_based(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "demo.txt"
            file_path.write_text("same-content", encoding="utf-8")

            first_hash = _hash_file(file_path)
            file_path.touch()
            second_hash = _hash_file(file_path)

            self.assertEqual(first_hash, second_hash)

    def test_backup_summary_has_stable_output(self) -> None:
        summary = BackupSummary(
            scanned_files=4,
            copied_files=2,
            unchanged_files=1,
            skipped_entries=1,
            deleted_in_source=0,
            error_count=0,
        )

        expected = (
            "Backup completed: scanned=4 copied=2 unchanged=1 "
            "skipped=1 deleted_in_source=0 errors=0"
        )
        self.assertEqual(summary.to_output_line(), expected)


class ManifestUnitTests(unittest.TestCase):
    """Cover manifest transitions without full backup orchestration."""

    def test_mark_deleted_missing_only_counts_newly_deleted_rows(self) -> None:
        with tempfile.TemporaryDirectory() as dest_dir:
            destination = Path(dest_dir)
            with ManifestStore.for_destination(destination) as manifest:
                manifest.upsert_file(
                    relative_path="alive.txt",
                    content_hash="hash-a",
                    file_size=1,
                    source_mtime_ns=1,
                    backup_relative_path="alive.txt",
                )
                manifest.upsert_file(
                    relative_path="missing.txt",
                    content_hash="hash-b",
                    file_size=1,
                    source_mtime_ns=1,
                    backup_relative_path="missing.txt",
                )

                first_deleted = manifest.mark_deleted_missing({"alive.txt"})
                second_deleted = manifest.mark_deleted_missing({"alive.txt"})

                self.assertEqual(first_deleted, 1)
                self.assertEqual(second_deleted, 0)
