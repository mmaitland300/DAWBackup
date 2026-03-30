"""User configuration load, save, and validation (Milestone 2)."""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import toml

from spb.constants import (
    CURRENT_SCHEMA_VERSION,
    config_file_path,
    ensure_config_directory_usable,
)


@dataclass(slots=True)
class AppConfig:
    """Validated configuration (``schema_version`` 1)."""

    schema_version: int
    default_source: str | None
    default_dest: str | None


@dataclass(slots=True)
class ConfigFileMissing:
    """No ``config.toml`` on disk."""


@dataclass(slots=True)
class ConfigFileInvalid:
    """Existing file could not be parsed or failed schema checks."""

    reason: str


@dataclass(slots=True)
class ConfigFileOk:
    """Config file loaded successfully."""

    config: AppConfig


ConfigReadResult = ConfigFileMissing | ConfigFileInvalid | ConfigFileOk


def read_config(path: Path | None = None) -> ConfigReadResult:
    """Load and validate ``config.toml``. Unknown keys are ignored for validation."""
    if path is None:
        try:
            resolved = config_file_path()
        except ValueError as exc:
            return ConfigFileInvalid(reason=str(exc))
    else:
        ensure_config_directory_usable(path.parent)
        resolved = path
    if not resolved.exists():
        return ConfigFileMissing()

    try:
        with resolved.open(encoding="utf-8") as handle:
            raw = toml.load(handle)
    except (OSError, UnicodeDecodeError, toml.TomlDecodeError) as exc:
        return ConfigFileInvalid(reason=f"Could not read config file: {exc}")

    outcome = dict_to_app_config(raw)
    if isinstance(outcome, str):
        return ConfigFileInvalid(reason=outcome)
    return ConfigFileOk(config=outcome)


def dict_to_app_config(data: object) -> AppConfig | str:
    """Parse a TOML root table into :class:`AppConfig` or an error string."""
    if not isinstance(data, dict):
        return "Config root must be a table."

    table: dict[str, Any] = data

    if "schema_version" not in table:
        return "Missing schema_version."
    schema_version = table["schema_version"]
    if not isinstance(schema_version, int) or schema_version != CURRENT_SCHEMA_VERSION:
        return f"schema_version must be {CURRENT_SCHEMA_VERSION}."

    default_source_raw = table.get("default_source")
    default_dest_raw = table.get("default_dest")

    if default_source_raw is not None and not isinstance(default_source_raw, str):
        return "default_source must be a string."
    if default_dest_raw is not None and not isinstance(default_dest_raw, str):
        return "default_dest must be a string."

    if default_source_raw in (None, ""):
        default_source: str | None = None
    else:
        default_source = str(Path(cast(str, default_source_raw)).expanduser())

    if default_dest_raw in (None, ""):
        default_dest: str | None = None
    else:
        default_dest = str(Path(cast(str, default_dest_raw)).expanduser())

    return AppConfig(
        schema_version=CURRENT_SCHEMA_VERSION,
        default_source=default_source,
        default_dest=default_dest,
    )


def _load_existing_merge_table(cfg_path: Path) -> dict[str, Any]:
    """Load ``cfg_path`` for merge, or return an empty table if absent."""
    if not cfg_path.exists():
        return {}
    try:
        with cfg_path.open(encoding="utf-8") as handle:
            loaded = toml.load(handle)
    except (OSError, UnicodeDecodeError, toml.TomlDecodeError) as exc:
        msg = f"Existing config is invalid: {exc}"
        raise ValueError(msg) from exc
    if not isinstance(loaded, dict):
        msg = "Existing config root must be a table."
        raise TypeError(msg)
    merge_err = validate_existing_table_for_merge(loaded)
    if merge_err is not None:
        raise ValueError(merge_err)
    return dict(loaded)


def persist_config_updates(
    *,
    source: Path | None,
    dest: Path | None,
    path: Path | None = None,
) -> None:
    """Merge ``--source`` / ``--dest`` into config and write atomically.

    Raises ``ValueError`` for invalid merge inputs, bad existing files, or
    when ``--source`` is not an existing directory.

    """
    if source is None and dest is None:
        msg = "Specify at least one of --source or --dest."
        raise ValueError(msg)

    if path is None:
        cfg_path = config_file_path()
    else:
        ensure_config_directory_usable(path.parent)
        cfg_path = path

    if source is not None:
        src = source.expanduser()
        if not src.is_dir():
            msg = f"Source is not an existing directory: {src}"
            raise ValueError(msg)

    existing_table = _load_existing_merge_table(cfg_path)

    output_table: dict[str, Any] = dict(existing_table)
    output_table["schema_version"] = CURRENT_SCHEMA_VERSION
    if source is not None:
        output_table["default_source"] = str(source.expanduser())
    if dest is not None:
        output_table["default_dest"] = str(dest.expanduser())

    merged_validation = dict_to_app_config(output_table)
    if isinstance(merged_validation, str):
        msg = f"Refusing to write config: {merged_validation}"
        raise ValueError(msg)  # noqa: TRY004

    atomic_write_toml(cfg_path, output_table)


def validate_existing_table_for_merge(table: dict[str, Any]) -> str | None:
    """Reject incompatible existing ``schema_version`` before merge."""
    version = table.get("schema_version")
    if version is None:
        return None
    if not isinstance(version, int) or version != CURRENT_SCHEMA_VERSION:
        return "Existing schema_version must be 1 to update."
    return None


def atomic_write_toml(path: Path, data: dict[str, Any]) -> None:
    """Write TOML atomically (temp file in the same directory, then replace)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="wb",
        delete=False,
        dir=path.parent,
        prefix=".spb-cfg-",
        suffix=".toml",
    ) as handle:
        temporary_path = Path(handle.name)
        text = toml.dumps(data)
        handle.write(text.encode("utf-8"))
    try:
        temporary_path.replace(path)
    except OSError:
        temporary_path.unlink(missing_ok=True)
        raise


def format_status_lines(result: ConfigReadResult, resolved_path: Path) -> list[str]:
    """Human-readable lines for ``spb status`` (always lists keys; uses ``unset``)."""
    lines = [f"Config file: {resolved_path}"]
    if isinstance(result, ConfigFileMissing):
        lines.append("State: config file not found (not configured yet).")
        lines.append("schema_version: unset")
        lines.append("default_source: unset")
        lines.append("default_dest: unset")
        return lines
    if isinstance(result, ConfigFileInvalid):
        lines.append(f"State: invalid - {result.reason}")
        lines.append("schema_version: unset")
        lines.append("default_source: unset")
        lines.append("default_dest: unset")
        return lines

    cfg = result.config
    lines.append("State: ok")
    lines.append(f"schema_version: {cfg.schema_version}")
    lines.append(
        f"default_source: {cfg.default_source}"
        if cfg.default_source
        else "default_source: unset",
    )
    lines.append(
        f"default_dest: {cfg.default_dest}"
        if cfg.default_dest
        else "default_dest: unset",
    )
    return lines


def paths_for_backup(cfg: AppConfig) -> tuple[Path, Path]:
    """Return source and destination paths for ``run_backup`` (0-arg backup)."""
    if not cfg.default_source or not cfg.default_dest:
        msg = (
            "Both default_source and default_dest must be set in the config file "
            "to run `spb backup` with no arguments."
        )
        raise ValueError(msg)
    return Path(cfg.default_source), Path(cfg.default_dest)
