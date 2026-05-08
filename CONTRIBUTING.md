# Contributing to Smart Project Backup

Thanks for taking a look at SPB. This is a small, source-installable Python backup utility, so the most useful contributions are practical, testable improvements that make backup behavior safer and clearer.

## Welcome Contributions

- Bug reports with exact commands, paths anonymized if needed, OS, Python version, and observed output.
- Documentation improvements that make setup, backup behavior, or recovery expectations clearer.
- Windows, Linux, and macOS compatibility fixes with tests where possible.
- Small CLI improvements that preserve existing command behavior.
- Tests for filesystem edge cases, watch-mode behavior, manifest state, and config handling.

## Out Of Scope For Now

- Automatic destructive restore or cleanup behavior without a prior design discussion.
- Cloud sync, GUI, daemon/service installers, or DAW-specific integrations as first-pass PRs.
- Large rewrites that replace the current CLI, manifest, or hashing model without an issue first.
- Claims that SPB is production-grade backup software. It is currently a milestone build.

## Local Setup

```bash
poetry install
poetry run spb --help
```

You can also install from source with pip:

```bash
pip install .
spb --help
```

## Checks

Before opening a PR, run the checks that match the change:

```bash
poetry run ruff check .
poetry run ruff format --check .
poetry run mypy spb
poetry run pytest
```

If you cannot run a check locally, mention that in the PR and explain why.

## Development Notes

- Use temporary directories in tests. Do not rely on personal project folders, DAW folders, or machine-specific paths.
- Keep backup/manifest behavior explicit. If a change affects copies, deletion tracking, destination metadata, or watch shutdown, add or update tests.
- Preserve current safety behavior unless the change is intentionally discussed: source deletions are recorded, but prior backup copies are not automatically deleted.
- Keep CLI output stable when possible because users may rely on stderr prefixes and summary lines.

## Pull Request Checklist

- The change is focused and easy to review.
- Tests or docs were updated when behavior changed.
- Safety implications are described for backup, watch, manifest, or restore-adjacent changes.
- The PR notes which checks were run.
