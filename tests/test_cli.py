"""CLI-level tests for Smart Project Backup."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from click.testing import CliRunner

from spb.cli.main import cli
from spb.constants import SPB_CONFIG_DIR_ENV


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

    def test_backup_rejects_single_path_argument(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["backup", "/only-one"])
        self.assertNotEqual(result.exit_code, 0)

    def test_backup_with_no_paths_uses_config(self) -> None:
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmp:
            previous = os.environ.get(SPB_CONFIG_DIR_ENV)
            os.environ[SPB_CONFIG_DIR_ENV] = tmp
            try:
                source = Path(tmp) / "src"
                dest = Path(tmp) / "dest"
                source.mkdir()
                (source / "f.txt").write_text("x", encoding="utf-8")
                cfg = runner.invoke(
                    cli,
                    ["configure", "--source", str(source), "--dest", str(dest)],
                )
                self.assertEqual(cfg.exit_code, 0, msg=cfg.output)
                run = runner.invoke(cli, ["backup"])
                self.assertEqual(run.exit_code, 0, msg=run.output)
                self.assertTrue((dest / "f.txt").exists())
            finally:
                if previous is None:
                    del os.environ[SPB_CONFIG_DIR_ENV]
                else:
                    os.environ[SPB_CONFIG_DIR_ENV] = previous

    def test_status_missing_config_exits_zero(self) -> None:
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmp:
            previous = os.environ.get(SPB_CONFIG_DIR_ENV)
            os.environ[SPB_CONFIG_DIR_ENV] = tmp
            try:
                result = runner.invoke(cli, ["status"])
                self.assertEqual(result.exit_code, 0, msg=result.output)
                self.assertIn("default_source: unset", result.output)
            finally:
                if previous is None:
                    del os.environ[SPB_CONFIG_DIR_ENV]
                else:
                    os.environ[SPB_CONFIG_DIR_ENV] = previous

    def test_status_invalid_config_exits_nonzero(self) -> None:
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmp:
            previous = os.environ.get(SPB_CONFIG_DIR_ENV)
            os.environ[SPB_CONFIG_DIR_ENV] = tmp
            try:
                bad = Path(tmp) / "config.toml"
                bad.write_text("not valid toml {{{", encoding="utf-8")
                result = runner.invoke(cli, ["status"])
                self.assertNotEqual(result.exit_code, 0)
                self.assertIn("invalid", result.output.lower())
            finally:
                if previous is None:
                    del os.environ[SPB_CONFIG_DIR_ENV]
                else:
                    os.environ[SPB_CONFIG_DIR_ENV] = previous

    def test_status_fails_when_spb_config_dir_is_a_file(self) -> None:
        runner = CliRunner(mix_stderr=False)
        with tempfile.TemporaryDirectory() as tmp:
            blocker = Path(tmp) / "not_a_directory"
            blocker.write_text("x", encoding="utf-8")
            previous = os.environ.get(SPB_CONFIG_DIR_ENV)
            os.environ[SPB_CONFIG_DIR_ENV] = str(blocker)
            try:
                result = runner.invoke(cli, ["status"])
                self.assertNotEqual(result.exit_code, 0, msg=result.output)
                combined = (result.stdout + result.stderr).lower()
                self.assertIn("not a directory", combined)
            finally:
                if previous is None:
                    del os.environ[SPB_CONFIG_DIR_ENV]
                else:
                    os.environ[SPB_CONFIG_DIR_ENV] = previous

    def test_configure_fails_when_spb_config_dir_is_a_file(self) -> None:
        runner = CliRunner(mix_stderr=False)
        with tempfile.TemporaryDirectory() as tmp:
            blocker = Path(tmp) / "not_a_directory"
            blocker.write_text("x", encoding="utf-8")
            src = Path(tmp) / "src"
            src.mkdir()
            previous = os.environ.get(SPB_CONFIG_DIR_ENV)
            os.environ[SPB_CONFIG_DIR_ENV] = str(blocker)
            try:
                result = runner.invoke(
                    cli,
                    ["configure", "--source", str(src), "--dest", str(Path(tmp) / "d")],
                )
                self.assertNotEqual(result.exit_code, 0, msg=result.output)
                combined = (result.stdout + result.stderr).lower()
                self.assertIn("not a directory", combined)
            finally:
                if previous is None:
                    del os.environ[SPB_CONFIG_DIR_ENV]
                else:
                    os.environ[SPB_CONFIG_DIR_ENV] = previous

    def test_backup_no_args_fails_when_only_source_configured(self) -> None:
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmp:
            previous = os.environ.get(SPB_CONFIG_DIR_ENV)
            os.environ[SPB_CONFIG_DIR_ENV] = tmp
            try:
                source = Path(tmp) / "src"
                source.mkdir()
                runner.invoke(cli, ["configure", "--source", str(source)])
                run = runner.invoke(cli, ["backup"])
                self.assertNotEqual(run.exit_code, 0)
            finally:
                if previous is None:
                    del os.environ[SPB_CONFIG_DIR_ENV]
                else:
                    os.environ[SPB_CONFIG_DIR_ENV] = previous
