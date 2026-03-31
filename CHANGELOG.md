# Changelog

All notable changes to Smart Project Backup (SPB) are documented in this file.

## [0.2.0] - 2026-03-30

### Milestone 3 complete: filesystem watch

SPB can run continuous, debounced incremental backups after one-time configuration.

### Added

- `spb watch`: watches the configured source tree (same defaults as `spb backup` with no arguments), runs `run_backup` after a quiet period; `--debounce` (default 1.5 seconds).
- INFO log on logger `spb.services.watcher` when shutdown waits for an in-flight backup: `Shutdown: waiting for in-flight backup to finish.`

### Fixed

- Watch shutdown waits for the active backup worker to finish so copies are not abandoned mid-run when the process exits.

### Documentation

- README: watch usage, shutdown order, logging, roadmap update.

## [0.1.0] - earlier

Initial public baseline: `spb backup`, SQLite manifest, `spb configure` / `spb status`, user config and zero-argument backup, tests and CI.
