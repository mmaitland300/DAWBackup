# Smart Project Backup (SPB)

[![CI Checks](https://github.com/mmaitland300/DAWBackup/actions/workflows/ci.yml/badge.svg)](https://github.com/mmaitland300/DAWBackup/actions/workflows/ci.yml)
[![Code Coverage](https://img.shields.io/badge/Coverage-%3E90%25%20Target-informational)](https://github.com/mmaitland300/DAWBackup/actions/workflows/ci.yml) [![Linter: Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)

A robust, cross-platform Python application that monitors specified project folders (initially focusing on Digital Audio Workstation projects, but applicable generally) and performs incremental backups by identifying and copying only changed or new files based on content hashing.

## Features (Planned)

* **Configuration:** Specify project directories and backup destination via config file or CLI.
* **Monitoring:** Efficiently watches project directories for file changes (create, modify, delete).
* **Content Hashing:** Uses SHA-256 hashing to detect actual content changes, ignoring metadata.
* **Incremental Backups:** Only copies new or modified files to a structured backup location.
* **Manifest:** Maintains an SQLite database tracking backed-up files, hashes, and timestamps.
* **Cross-Platform:** Designed to run on Windows, macOS, and Linux.
* **Efficient:** Uses buffered I/O and event debouncing.

## Installation

*(Placeholder - Instructions will be added for installing via pip and using pre-built executables from GitHub Releases)*

## Usage

*(Placeholder - Instructions will be added for `spb configure`, `spb start`, `spb status` commands)*

## Configuration

*(Placeholder - Details on the configuration file format and options will be added)*

## Contributing

*(Placeholder - Guidelines for development setup, running tests, and submitting PRs will be added)*

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.