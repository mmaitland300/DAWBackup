"""SQLite manifest storage for backup state."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import TYPE_CHECKING, Self

from spb.constants import MANIFEST_FILENAME, METADATA_DIR_RELATIVE
from spb.core.shared import BackupSummary, utc_now_iso

if TYPE_CHECKING:
    from pathlib import Path
    from types import TracebackType


@dataclass(slots=True)
class FileRecord:
    """Stored metadata for a tracked file."""

    relative_path: str
    content_hash: str
    file_size: int
    source_mtime_ns: int
    backup_relative_path: str
    last_backed_up_at: str
    deleted: bool


class ManifestStore:
    """Thin wrapper over the SQLite manifest schema."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._connection.row_factory = sqlite3.Row
        self._initialize()

    def __enter__(self) -> Self:
        """Open the manifest context (no-op; connection is already active)."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Commit or roll back and close the SQLite connection."""
        if exc is None:
            self._connection.commit()
        else:
            self._connection.rollback()
        self._connection.close()

    @classmethod
    def for_destination(cls, destination_root: Path) -> ManifestStore:
        """Create a store backed by ``dest/.spb/manifest.sqlite``."""
        metadata_dir = destination_root / METADATA_DIR_RELATIVE
        metadata_dir.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(metadata_dir / MANIFEST_FILENAME)
        return cls(connection=connection)

    def start_run(self, source_root: Path, destination_root: Path) -> int:
        """Insert a runs row and return its id."""
        cursor = self._connection.execute(
            """
            INSERT INTO runs (
                started_at,
                source_root,
                destination_root,
                scanned_files,
                copied_files,
                unchanged_files,
                skipped_entries,
                deleted_in_source,
                error_count
            )
            VALUES (?, ?, ?, 0, 0, 0, 0, 0, 0)
            """,
            (utc_now_iso(), str(source_root), str(destination_root)),
        )
        self._connection.commit()
        run_id = cursor.lastrowid
        if run_id is None:
            msg = "SQLite did not return a run id for the inserted backup run."
            raise RuntimeError(msg)
        return int(run_id)

    def finish_run(self, run_id: int, summary: BackupSummary) -> None:
        """Persist final counters and finished timestamp for a run."""
        self._connection.execute(
            """
            UPDATE runs
            SET finished_at = ?,
                scanned_files = ?,
                copied_files = ?,
                unchanged_files = ?,
                skipped_entries = ?,
                deleted_in_source = ?,
                error_count = ?
            WHERE id = ?
            """,
            (
                utc_now_iso(),
                summary.scanned_files,
                summary.copied_files,
                summary.unchanged_files,
                summary.skipped_entries,
                summary.deleted_in_source,
                summary.error_count,
                run_id,
            ),
        )
        self._connection.commit()

    def fetch_file(self, relative_path: str) -> FileRecord | None:
        """Return the manifest row for a relative path, if any."""
        row = self._connection.execute(
            """
            SELECT relative_path,
                   content_hash,
                   file_size,
                   source_mtime_ns,
                   backup_relative_path,
                   last_backed_up_at,
                   deleted
            FROM files
            WHERE relative_path = ?
            """,
            (relative_path,),
        ).fetchone()
        if row is None:
            return None

        return FileRecord(
            relative_path=row["relative_path"],
            content_hash=row["content_hash"],
            file_size=row["file_size"],
            source_mtime_ns=row["source_mtime_ns"],
            backup_relative_path=row["backup_relative_path"],
            last_backed_up_at=row["last_backed_up_at"],
            deleted=bool(row["deleted"]),
        )

    def mark_seen(
        self,
        relative_path: str,
        content_hash: str,
        file_size: int,
        source_mtime_ns: int,
    ) -> None:
        """Update metadata for an unchanged file and clear ``deleted``."""
        self._connection.execute(
            """
            UPDATE files
            SET content_hash = ?,
                file_size = ?,
                source_mtime_ns = ?,
                last_backed_up_at = ?,
                deleted = 0
            WHERE relative_path = ?
            """,
            (
                content_hash,
                file_size,
                source_mtime_ns,
                utc_now_iso(),
                relative_path,
            ),
        )

    def upsert_file(  # noqa: PLR0913
        self,
        relative_path: str,
        content_hash: str,
        file_size: int,
        source_mtime_ns: int,
        backup_relative_path: str,
    ) -> None:
        """Insert or update a file row and mark it live (``deleted = 0``)."""
        self._connection.execute(
            """
            INSERT INTO files (
                relative_path,
                content_hash,
                file_size,
                source_mtime_ns,
                backup_relative_path,
                last_backed_up_at,
                deleted
            )
            VALUES (?, ?, ?, ?, ?, ?, 0)
            ON CONFLICT(relative_path) DO UPDATE SET
                content_hash = excluded.content_hash,
                file_size = excluded.file_size,
                source_mtime_ns = excluded.source_mtime_ns,
                backup_relative_path = excluded.backup_relative_path,
                last_backed_up_at = excluded.last_backed_up_at,
                deleted = 0
            """,
            (
                relative_path,
                content_hash,
                file_size,
                source_mtime_ns,
                backup_relative_path,
                utc_now_iso(),
            ),
        )

    def mark_deleted_missing(self, observed_paths: set[str]) -> int:
        """Mark live rows missing from ``observed_paths`` deleted; return count."""
        rows = self._connection.execute(
            """
            SELECT relative_path
            FROM files
            WHERE deleted = 0
            """,
        ).fetchall()
        live_paths = {str(row["relative_path"]) for row in rows}
        missing_paths = sorted(live_paths - observed_paths)

        if not missing_paths:
            return 0

        self._connection.executemany(
            """
            UPDATE files
            SET deleted = 1
            WHERE relative_path = ?
            """,
            [(path,) for path in missing_paths],
        )
        return len(missing_paths)

    def _initialize(self) -> None:
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS files (
                relative_path TEXT PRIMARY KEY,
                content_hash TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                source_mtime_ns INTEGER NOT NULL,
                backup_relative_path TEXT NOT NULL,
                last_backed_up_at TEXT NOT NULL,
                deleted INTEGER NOT NULL DEFAULT 0
            )
            """,
        )
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                source_root TEXT NOT NULL,
                destination_root TEXT NOT NULL,
                scanned_files INTEGER NOT NULL,
                copied_files INTEGER NOT NULL,
                unchanged_files INTEGER NOT NULL,
                skipped_entries INTEGER NOT NULL,
                deleted_in_source INTEGER NOT NULL,
                error_count INTEGER NOT NULL
            )
            """,
        )
        self._connection.commit()
