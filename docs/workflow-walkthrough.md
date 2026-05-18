# Workflow Walkthrough

This walkthrough shows the current Smart Project Backup (`spb`) flow from a fresh source folder to an incremental mirror. It is intentionally small: the goal is to show what runs today, what state SPB records, and where restore safety still requires manual care.

The transcript below was run against temporary local folders and then shortened to use stable placeholder paths:

- `<source>` - a sample project folder with a text file and a nested `stems/` folder.
- `<dest>` - the backup mirror folder.
- `<config>` - a temporary config directory set with `SPB_CONFIG_DIR`.

## 1. Install And Check The CLI

```bash
poetry install
poetry run python -m spb --help
```

Expected shape:

```text
Usage: spb [OPTIONS] COMMAND [ARGS]...

  Smart Project Backup.

Commands:
  backup
  configure
  status
  watch
```

## 2. Run An Explicit Backup

Create a small source tree:

```text
<source>/
  song.txt
  stems/
    guitar.wav
```

Run the first backup:

```bash
poetry run python -m spb backup <source> <dest>
```

Observed output:

```text
Backup completed: scanned=2 copied=2 unchanged=0 skipped=0 deleted_in_source=0 errors=0
```

Run the same backup again without changing files:

```bash
poetry run python -m spb backup <source> <dest>
```

Observed output:

```text
Backup completed: scanned=2 copied=0 unchanged=2 skipped=0 deleted_in_source=0 errors=0
```

That repeat run is the important baseline: SPB hashes the files again, recognizes unchanged content, and avoids copying the same files twice.

## 3. Change The Source And Re-run

After editing `song.txt` and adding `notes.txt`, run backup again:

```bash
poetry run python -m spb backup <source> <dest>
```

Observed output:

```text
Backup completed: scanned=3 copied=2 unchanged=1 skipped=0 deleted_in_source=0 errors=0
```

SPB copied the changed file and the new file while leaving unchanged content alone.

## 4. Store Defaults For Zero-Argument Runs

Set a temporary config directory and store defaults:

```bash
# macOS/Linux
export SPB_CONFIG_DIR=<config>

# PowerShell
$env:SPB_CONFIG_DIR = "<config>"

poetry run python -m spb configure --source <source> --dest <dest>
```

Observed output:

```text
Updated <config>/config.toml
```

Check status:

```bash
poetry run python -m spb status
```

Observed output:

```text
Config file: <config>/config.toml
State: ok
schema_version: 1
default_source: <source>
default_dest: <dest>
```

Now backup can run without path arguments:

```bash
poetry run python -m spb backup
```

Observed output:

```text
Backup completed: scanned=3 copied=0 unchanged=3 skipped=0 deleted_in_source=0 errors=0
```

## 5. Watch Mode

After source and destination defaults are configured, watch mode uses the same defaults as `spb backup` with no arguments:

```bash
poetry run python -m spb watch
```

Optional debounce:

```bash
poetry run python -m spb watch --debounce 2
```

Watch mode waits for filesystem activity to settle, then runs the same backup engine used above. It is meant for bursty creative-project saves where several files may change together.

## Restore Safety

SPB does not perform automatic destructive restores. Source deletions are recorded in the manifest, but existing backup copies are not deleted from the mirror.

When testing a restore, copy files out of `<dest>` into a temporary folder first and confirm the project opens as expected. Do not overwrite an active project folder until the restored copy has been checked.

## Current Boundary

- Current release: `v0.2.0` GitHub source release.
- Install path: source install with Poetry or `pip install .`.
- No PyPI package, standalone installer, binary build, or automatic restore command yet.
- Milestone 4 focus: exclude patterns, clearer last-run status, optional initial sync, observer diagnostics, and stricter edge-case tests.
