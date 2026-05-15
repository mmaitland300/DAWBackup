# Security Policy

Smart Project Backup (SPB) is a source-installable backup utility that copies
local files, records SHA-256 hashes, and stores run state in a local SQLite
manifest. Please report issues privately when they could cause data loss,
unexpected file access, or unsafe restore/copy behavior.

## Supported Versions

| Version | Status |
| --- | --- |
| `v0.2.0` | Current source release |
| `main` | Active development |

## Please Report Privately

Use a private report for issues involving:

- Path traversal, path confusion, or copying outside the requested source and
  destination trees.
- Unexpected overwrite, deletion, restore, or pruning behavior.
- Manifest behavior that could make a backup appear safer or more complete than
  it is.
- Watch-mode behavior that repeatedly copies the wrong files or destination.
- Exposure of private local paths, project names, or file contents in logs,
  errors, or issue reports.

SPB does not currently perform automatic destructive restores, pruning, cloud
sync, or remote storage. If a report depends on one of those behaviors, please
describe the command or workflow where it appeared.

## How To Report

Open a private GitHub security advisory from this repository's **Security**
tab if available. If that is not available, contact the maintainer through the
portfolio contact route and include "SPB security report" in the message.

Please include:

- SPB version or commit.
- Operating system and Python version.
- Exact command or workflow.
- Expected behavior and actual behavior.
- Minimal reproduction steps using temporary directories when possible.
- Redacted paths if needed. Do not send private project files, DAW sessions, API
  keys, or secrets.

## Public Issues

Use a normal GitHub issue for ordinary bugs, documentation corrections, platform
compatibility notes, or feature requests that do not expose private paths,
private data, unsafe copy behavior, or data-loss risk.

