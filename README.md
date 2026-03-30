# Smart Project Backup (SPB)

[![CI Checks](https://github.com/mmaitland300/DAWBackup/actions/workflows/ci.yml/badge.svg)](https://github.com/mmaitland300/DAWBackup/actions/workflows/ci.yml)
[![Coverage](https://img.shields.io/badge/Coverage-Tracked%20in%20CI-informational)](https://github.com/mmaitland300/DAWBackup/actions/workflows/ci.yml) [![Linter: Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)

A cross-platform Python backup tool that hashes project files, copies only new or changed content, and tracks state in SQLite. The current shipped slice is a manual backup command; config and live watching are planned follow-on milestones.

## Current Features

* **Manual backup CLI:** Run `spb backup <source> <dest>` to back up one project tree into a mirrored destination.
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

Example:

```bash
spb backup "C:\Projects\MySong" "D:\Backups\MySong"
```

The destination will contain:

* A mirrored copy of backed-up files under `dest/`
* SPB metadata under `dest/.spb/manifest.sqlite`

Operational rules in the current milestone:

* Only regular files are backed up.
* Symlinks and other non-ordinary filesystem entries are skipped with warnings.
* The top-level destination metadata directory `dest/.spb/` is reserved for SPB internals.
* Files restored after a source deletion are treated as live again on the next run.
* Every regular file is hashed on every run for correctness-first behavior.

## Configuration

Configuration files are intentionally out of scope for the current milestone. The first shipping slice uses explicit source and destination arguments.

## Roadmap

Planned follow-on work:

* Config file and user-directory support
* Filesystem watching via `watchdog`
* Performance optimizations for large project trees
* Richer packaging and release automation

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
