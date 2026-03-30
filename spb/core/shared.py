"""Shared core models and utilities."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(slots=True)
class BackupSummary:
    """Aggregated results for a backup run."""

    scanned_files: int = 0
    copied_files: int = 0
    unchanged_files: int = 0
    skipped_entries: int = 0
    deleted_in_source: int = 0
    error_count: int = 0

    def to_output_line(self) -> str:
        """Return a stable summary for CLI output."""
        return (
            "Backup completed: "
            f"scanned={self.scanned_files} "
            f"copied={self.copied_files} "
            f"unchanged={self.unchanged_files} "
            f"skipped={self.skipped_entries} "
            f"deleted_in_source={self.deleted_in_source} "
            f"errors={self.error_count}"
        )


def utc_now_iso() -> str:
    """Return a UTC timestamp in ISO 8601 form."""
    return datetime.now(tz=UTC).isoformat(timespec="seconds")
