"""CLI-level tests for Smart Project Backup."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from click.testing import CliRunner

from spb.cli.main import cli


class CliTests(unittest.TestCase):
    """Exercise the public command interface."""

    def test_backup_command_writes_summary_to_stdout(self) -> None:
        runner = CliRunner()
        with (
            tempfile.TemporaryDirectory() as source_dir,
            tempfile.TemporaryDirectory() as dest_dir,
        ):
            source = Path(source_dir)
            dest = Path(dest_dir)
            (source / "demo.txt").write_text("demo", encoding="utf-8")

            result = runner.invoke(cli, ["backup", str(source), str(dest)])

            self.assertEqual(result.exit_code, 0, msg=result.output)
            expected_summary = (
                "Backup completed: scanned=1 copied=1 unchanged=0 "
                "skipped=0 deleted_in_source=0 errors=0"
            )
            self.assertIn(expected_summary, result.output)
            self.assertNotIn("Warning:", result.output)
            self.assertNotIn("Error:", result.output)

    def test_reserved_path_warning_appears_in_cli_output(self) -> None:
        runner = CliRunner()
        with (
            tempfile.TemporaryDirectory() as source_dir,
            tempfile.TemporaryDirectory() as dest_dir,
        ):
            source = Path(source_dir)
            dest = Path(dest_dir)
            reserved = source / ".spb" / "ignored.txt"
            reserved.parent.mkdir(parents=True, exist_ok=True)
            reserved.write_text("ignore", encoding="utf-8")

            result = runner.invoke(cli, ["backup", str(source), str(dest)])

            self.assertEqual(result.exit_code, 0, msg=result.output)
            self.assertIn(
                "Warning: Skipping reserved top-level path: .spb",
                result.output,
            )
            self.assertIn("Backup completed:", result.output)
