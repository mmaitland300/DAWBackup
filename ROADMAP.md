# Roadmap

Smart Project Backup is a source-installable milestone build. The current public baseline covers manual incremental backup, user configuration, watch mode, SQLite manifest state, tests, and CI.

## Current Focus: Milestone 4 Operational Hardening

- Exclude patterns for common generated/cache folders.
- Clearer last-run status from the manifest.
- Optional initial sync when `spb watch` starts.
- Observer error handling and clearer watch-mode diagnostics.
- Stricter test coverage for path validation, shutdown behavior, and edge-case filesystem entries.
- Restore guidance and tests around safe manual recovery workflows.

## Packaging And Release Polish

- Keep GitHub release notes aligned with source-installable milestones.
- Document release verification steps.
- Evaluate PyInstaller or similar packaging after CLI behavior stabilizes.

## Longer-Term Ideas

- Performance improvements for large project trees.
- Multiple watch roots.
- Path arguments for `spb watch` after config behavior is stable.
- Service/daemon packaging for users who want continuous background backups.

## Not Planned Without A Design Discussion

- Automatic destructive restore, deletion, or pruning behavior.
- Cloud sync or remote storage backends.
- DAW-specific project editing or file interpretation.
- GUI work that bypasses the tested CLI and manifest model.
