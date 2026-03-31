# Smart Project Backup (SPB)

[![CI Checks](https://github.com/mmaitland300/DAWBackup/actions/workflows/ci.yml/badge.svg)](https://github.com/mmaitland300/DAWBackup/actions/workflows/ci.yml)
[![Coverage](https://img.shields.io/badge/Coverage-Tracked%20in%20CI-informational)](https://github.com/mmaitland300/DAWBackup/actions/workflows/ci.yml) [![Linter: Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)

A cross-platform Python backup tool that hashes project files, copies only new or changed content, and tracks state in SQLite. You can pass source and destination on the command line or store defaults in a user config file. **`spb watch`** runs incremental backups when the configured source tree changes, with debouncing for bursty editors (for example DAW saves).

## Current Features

* **Manual backup CLI:** `spb backup <source> <dest>` or `spb backup` after configuring defaults.
* **Watch mode:** `spb watch` uses the same config defaults as zero-argument `spb backup`, watches the source tree with [watchdog](https://github.com/gorakhargosh/watchdog), and runs `run_backup` after a quiet period (default 1.5s; override with `--debounce SECONDS`).
* **User config:** `spb configure` and `spb status`; defaults live in a TOML file under the user config directory (or `SPB_CONFIG_DIR` if set).
* **Content Hashing:** Uses SHA-256 hashing to detect actual content changes, ignoring metadata.
* **Incremental Backups:** Only copies new or modified files into the mirrored destination tree.
* **Manifest:** Maintains `dest/.spb/manifest.sqlite` with per-file and per-run state.
* **Deletion Tracking:** Records source deletions in SQLite without deleting prior backup copies.
* **Cross-Platform Baseline:** Validated by tests on Linux and Windows in CI.

## Installation

### Poetry

```bash
poetry install
poetry run spb --help
```

### Pip

```bash
pip install .
spb --help
```

## Usage

```bash
spb backup <source> <dest>
```

Or, after setting defaults (see **Configuration**):

```bash
spb backup
```

Continuous sync after configuration (same defaults as `spb backup` with no args):

```bash
spb watch
```

Optional debounce interval (seconds of filesystem quiet before running a backup):

```bash
spb watch --debounce 2
```

Press Ctrl+C to stop watching; the process exits cleanly (pending debounced runs are cancelled; already running backups are allowed to finish).

`spb backup` accepts **either zero arguments** (use configured `default_source` and `default_dest`) **or exactly two** paths. One argument is always an error. **`spb watch` does not take path arguments**; it always uses the configured defaults, like zero-argument `spb backup`.

Example with explicit paths:

```bash
spb backup "C:\Projects\MySong" "D:\Backups\MySong"
```

The destination will contain:

* A mirrored copy of backed-up files under `dest/`
* SPB metadata under `dest/.spb/manifest.sqlite`

Operational rules:

* Only regular files are backed up.
* Symlinks and other non-ordinary filesystem entries are skipped with warnings.
* The top-level destination metadata directory `dest/.spb/` is reserved for SPB internals.
* The top-level **source** tree's `.spb` directory is skipped so it does not collide with mirror metadata.
* **Watch mode** ignores events under that reserved source `.spb` directory, consistent with backup. The observer follows the platform's filesystem notification rules; symlink and non-regular file handling for *copies* remains the same as manual backup (skipped with warnings). Platform limits of `watchdog` (buffer sizes, quirks on network paths, etc.) apply; see upstream docs.
* Files restored after a source deletion are treated as live again on the next run.
* Every regular file is hashed on every run for correctness-first behavior.

## Configuration

Defaults are stored in **`config.toml`** with `schema_version = 1`.

**Config directory**

1. If **`SPB_CONFIG_DIR`** is set, it must refer to a **directory** (the path may be missing and will be created when needed; if the path exists as a non-directory, commands fail with a clear error). That directory holds `config.toml`.
2. Otherwise, SPB uses **`appdirs.user_config_dir("spb", appauthor=False)`** (per-OS user config location).

**Commands**

* **`spb configure --source DIR`** and/or **`--dest DIR`** - merge into `config.toml` and write **atomically**. At least one flag is required.
  * `--source` must already exist and be a directory.
  * `--dest` may point to a path that does not exist yet.
  * You may set only one default at a time; `spb backup` with no arguments still requires **both** defaults before a run succeeds.
* **`spb status`** - print the resolved config path and whether `default_source` / `default_dest` are set (**`unset`** if missing). Exit **0** if the file is absent or valid; **non-zero** only if `config.toml` exists but is invalid.

Path strings are normalized with **`expanduser()`** when saving, so literals like `~` are stored as expanded paths in `config.toml`. Environment variable expansion inside values is **not** applied.

Unknown keys in `config.toml` are **ignored** when reading.

## Roadmap

* Performance optimizations for large project trees
* Richer packaging and release automation
* Possible follow-ons: multiple watch roots, path arguments for watch, service/daemon packaging

## Contributing

```bash
poetry install
poetry run ruff check .
poetry run ruff format --check .
poetry run mypy spb
poetry run pytest
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
