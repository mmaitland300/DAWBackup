"""Tests for configuration load, save, and status formatting."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from spb.config import (
    AppConfig,
    ConfigFileInvalid,
    ConfigFileMissing,
    ConfigFileOk,
    atomic_write_toml,
    dict_to_app_config,
    format_status_lines,
    paths_for_backup,
    persist_config_updates,
    read_config,
)
from spb.constants import (
    CURRENT_SCHEMA_VERSION,
    SPB_CONFIG_DIR_ENV,
    config_file_path,
    ensure_config_directory_usable,
)


class ConfigReadTests(unittest.TestCase):
    """Exercise TOML parsing and validation."""

    def test_missing_file_returns_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nope.toml"
            result = read_config(path)
            self.assertIsInstance(result, ConfigFileMissing)

    def test_valid_partial_config_ok(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            src = Path(tmpdir) / "src"
            src.mkdir()
            payload = {
                "schema_version": CURRENT_SCHEMA_VERSION,
                "default_source": str(src),
            }
            outcome = dict_to_app_config(payload)
            self.assertIsInstance(outcome, AppConfig)
            assert isinstance(outcome, AppConfig)
            self.assertEqual(outcome.default_source, str(src.expanduser()))
            self.assertIsNone(outcome.default_dest)

    def test_unknown_keys_ignored_for_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            a = Path(tmpdir) / "a"
            b = Path(tmpdir) / "b"
            a.mkdir()
            b.mkdir()
            payload = {
                "schema_version": CURRENT_SCHEMA_VERSION,
                "future_feature": 1,
                "default_source": str(a),
                "default_dest": str(b),
            }
            outcome = dict_to_app_config(payload)
            self.assertIsInstance(outcome, AppConfig)

    def test_wrong_schema_version_rejected(self) -> None:
        outcome = dict_to_app_config({"schema_version": 2})
        self.assertIsInstance(outcome, str)

    def test_paths_for_backup_requires_both(self) -> None:
        partial = AppConfig(
            schema_version=CURRENT_SCHEMA_VERSION,
            default_source="dummy-source-for-partial-test",
            default_dest=None,
        )
        with self.assertRaises(ValueError):
            paths_for_backup(partial)


class ConfigPersistTests(unittest.TestCase):
    """Exercise configure merges and atomic writes."""

    def test_atomic_write_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cfg.toml"
            src = Path(tmp) / "s"
            src.mkdir()
            atomic_write_toml(
                path,
                {
                    "schema_version": CURRENT_SCHEMA_VERSION,
                    "default_source": str(src),
                },
            )
            result = read_config(path)
            self.assertIsInstance(result, ConfigFileOk)

    def test_partial_write_then_read(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg_path = Path(tmp) / "config.toml"
            src = Path(tmp) / "source_tree"
            src.mkdir()
            persist_config_updates(
                source=src,
                dest=None,
                path=cfg_path,
            )
            result = read_config(cfg_path)
            self.assertIsInstance(result, ConfigFileOk)

    def test_configure_rejects_bad_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg_path = Path(tmp) / "config.toml"
            bogus = Path(tmp) / "not_a_dir"
            with self.assertRaises(ValueError):
                persist_config_updates(source=bogus, dest=None, path=cfg_path)

    def test_persist_rejects_when_merge_would_leave_invalid_known_keys(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg_path = Path(tmp) / "config.toml"
            cfg_path.write_text(
                f"schema_version = {CURRENT_SCHEMA_VERSION}\n" "default_source = 123\n",
                encoding="utf-8",
            )
            dest = Path(tmp) / "dest"
            with self.assertRaises(ValueError) as ctx:
                persist_config_updates(source=None, dest=dest, path=cfg_path)
            self.assertIn("Refusing to write", str(ctx.exception))
            self.assertIn("string", str(ctx.exception).lower())

    def test_preserves_unknown_keys_on_merge(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old_src = root / "old"
            old_src.mkdir()
            cfg_path = root / "config.toml"
            atomic_write_toml(
                cfg_path,
                {
                    "schema_version": CURRENT_SCHEMA_VERSION,
                    "extra_key": "keep-me",
                    "default_source": str(old_src),
                },
            )
            dest = root / "backup_here"
            persist_config_updates(source=None, dest=dest, path=cfg_path)
            text = cfg_path.read_text(encoding="utf-8")
            self.assertIn("extra_key", text)


class StatusFormatTests(unittest.TestCase):
    """Line output for ``spb status``."""

    def test_missing_shows_unset_fields(self) -> None:
        path = Path("example-status-path.toml")
        lines = format_status_lines(ConfigFileMissing(), path)
        joined = "\n".join(lines)
        self.assertIn("not found", joined)
        self.assertIn("default_source: unset", joined)
        self.assertIn("default_dest: unset", joined)
        self.assertIn("schema_version: unset", joined)

    def test_invalid_shows_unset_placeholders(self) -> None:
        path = Path("/x/cfg.toml")
        lines = format_status_lines(ConfigFileInvalid(reason="bad"), path)
        self.assertTrue(any("invalid" in line for line in lines))
        self.assertIn("default_source: unset", lines)


class ConfigDirectoryValidationTests(unittest.TestCase):
    """``SPB_CONFIG_DIR`` and config parent directory must be real directories."""

    def test_ensure_config_directory_rejects_existing_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            blocker = Path(tmp) / "not_a_directory"
            blocker.write_text("x", encoding="utf-8")
            with self.assertRaises(ValueError) as ctx:
                ensure_config_directory_usable(blocker)
            self.assertIn("not a directory", str(ctx.exception).lower())

    def test_config_file_path_fails_when_env_points_at_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            blocker = Path(tmp) / "not_a_directory"
            blocker.write_text("x", encoding="utf-8")
            previous = os.environ.get(SPB_CONFIG_DIR_ENV)
            os.environ[SPB_CONFIG_DIR_ENV] = str(blocker)
            try:
                with self.assertRaises(ValueError):
                    config_file_path()
            finally:
                if previous is None:
                    del os.environ[SPB_CONFIG_DIR_ENV]
                else:
                    os.environ[SPB_CONFIG_DIR_ENV] = previous


class EnvOverrideTests(unittest.TestCase):
    """``SPB_CONFIG_DIR`` resolution."""

    def test_config_file_uses_env_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            previous = os.environ.get(SPB_CONFIG_DIR_ENV)
            os.environ[SPB_CONFIG_DIR_ENV] = tmp
            try:
                path = config_file_path()
                self.assertEqual(path, Path(tmp) / "config.toml")
            finally:
                if previous is None:
                    del os.environ[SPB_CONFIG_DIR_ENV]
                else:
                    os.environ[SPB_CONFIG_DIR_ENV] = previous
