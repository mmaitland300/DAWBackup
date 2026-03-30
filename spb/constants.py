"""Project-wide constants."""

import os
from pathlib import Path

import appdirs

METADATA_DIRNAME = ".spb"
MANIFEST_FILENAME = "manifest.sqlite"
METADATA_DIR_RELATIVE = Path(METADATA_DIRNAME)

CONFIG_FILENAME = "config.toml"
SPB_CONFIG_DIR_ENV = "SPB_CONFIG_DIR"
CURRENT_SCHEMA_VERSION = 1
_APPDIRS_APP_NAME = "spb"


def default_user_config_dir() -> Path:
    """Return the default config directory when ``SPB_CONFIG_DIR`` is unset."""
    # appauthor=False keeps Windows paths simpler (per Milestone 2 policy).
    return Path(appdirs.user_config_dir(_APPDIRS_APP_NAME, appauthor=False))


def resolve_config_dir() -> Path:
    """Config directory: ``SPB_CONFIG_DIR`` if set, else appdirs user config dir."""
    override = os.environ.get(SPB_CONFIG_DIR_ENV, "").strip()
    if override:
        return Path(override).expanduser()
    return default_user_config_dir()


def ensure_config_directory_usable(directory: Path) -> None:
    """Raise ``ValueError`` if ``directory`` exists and is not a directory.

    A missing path is allowed (parents are created when writing config).

    """
    if directory.exists() and not directory.is_dir():
        msg = (
            "Configuration directory path exists but is not a directory: "
            f"{directory}. When set, {SPB_CONFIG_DIR_ENV} must refer to a "
            "directory path."
        )
        raise ValueError(msg)


def config_file_path() -> Path:
    """Return the path to ``config.toml`` under the resolved config directory.

    Raises ``ValueError`` when that directory exists but is not a directory.

    """
    base = resolve_config_dir()
    ensure_config_directory_usable(base)
    return base / CONFIG_FILENAME
