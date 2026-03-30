"""Core backup workflow for Smart Project Backup."""

from __future__ import annotations

import hashlib
import os
import shutil
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from spb.constants import METADATA_DIR_RELATIVE
from spb.core.shared import BackupSummary
from spb.services.manifest import ManifestStore

if TYPE_CHECKING:
    from collections.abc import Iterator

BUFFER_SIZE = 1024 * 1024


@dataclass(slots=True)
class BackupResult:
    """Result payload for a completed run."""

    summary: BackupSummary
    warnings: list[str]
    errors: list[str]


def run_backup(source: Path, destination: Path) -> BackupResult:
    """Perform a single backup run from source to destination."""
    resolved_source = source.resolve(strict=True)
    if not resolved_source.is_dir():
        msg = f"Source must be an existing directory: {resolved_source}"
        raise ValueError(msg)

    resolved_destination = destination.resolve(strict=False)
    if resolved_source == resolved_destination:
        msg = "Source and destination must be different directories."
        raise ValueError(msg)
    if resolved_destination.is_relative_to(resolved_source):
        msg = "Destination cannot live inside the source directory."
        raise ValueError(msg)

    resolved_destination.mkdir(parents=True, exist_ok=True)

    summary = BackupSummary()
    warnings: list[str] = []
    errors: list[str] = []
    observed_paths: set[str] = set()

    with ManifestStore.for_destination(resolved_destination) as manifest:
        run_id = manifest.start_run(resolved_source, resolved_destination)

        for file_path, relative_path, file_stat in _iter_regular_files(
            source_root=resolved_source,
            summary=summary,
            warnings=warnings,
            errors=errors,
        ):
            observed_paths.add(relative_path)
            summary.scanned_files += 1

            try:
                content_hash = _hash_file(file_path)
            except OSError as exc:
                summary.error_count += 1
                errors.append(f"Error hashing {relative_path}: {exc}")
                continue

            backup_path = resolved_destination / Path(relative_path)
            record = manifest.fetch_file(relative_path)
            if (
                record is not None
                and not record.deleted
                and record.content_hash == content_hash
                and backup_path.exists()
            ):
                manifest.mark_seen(
                    relative_path=relative_path,
                    content_hash=content_hash,
                    file_size=file_stat.st_size,
                    source_mtime_ns=file_stat.st_mtime_ns,
                )
                summary.unchanged_files += 1
                continue

            backup_path.parent.mkdir(parents=True, exist_ok=True)

            try:
                _copy_with_atomic_replace(file_path, backup_path)
            except OSError as exc:
                summary.error_count += 1
                errors.append(f"Error copying {relative_path}: {exc}")
                continue

            manifest.upsert_file(
                relative_path=relative_path,
                content_hash=content_hash,
                file_size=file_stat.st_size,
                source_mtime_ns=file_stat.st_mtime_ns,
                backup_relative_path=relative_path,
            )
            summary.copied_files += 1

        summary.deleted_in_source = manifest.mark_deleted_missing(observed_paths)
        manifest.finish_run(run_id=run_id, summary=summary)

    return BackupResult(summary=summary, warnings=warnings, errors=errors)


def _iter_regular_files(
    source_root: Path,
    summary: BackupSummary,
    warnings: list[str],
    errors: list[str],
) -> Iterator[tuple[Path, str, os.stat_result]]:
    for current_root, directory_names, file_names in os.walk(
        source_root,
        topdown=True,
        followlinks=False,
    ):
        current_path = Path(current_root)
        kept_directories: list[str] = []

        for directory_name in directory_names:
            directory_path = current_path / directory_name
            relative_directory_path = normalize_relative_path(
                directory_path.relative_to(source_root),
            )

            should_traverse = _should_traverse_directory(
                relative_directory_path=relative_directory_path,
                directory_path=directory_path,
                summary=summary,
                warnings=warnings,
                errors=errors,
            )
            if not should_traverse:
                continue

            kept_directories.append(directory_name)

        directory_names[:] = kept_directories

        for file_name in file_names:
            file_path = current_path / file_name
            relative_path = normalize_relative_path(file_path.relative_to(source_root))
            file_stat = _classify_file(
                file_path=file_path,
                relative_path=relative_path,
                summary=summary,
                warnings=warnings,
                errors=errors,
            )
            if file_stat is None:
                continue

            yield file_path, relative_path, file_stat


def _hash_file(path: Path) -> str:
    sha256 = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(BUFFER_SIZE):
            sha256.update(chunk)
    return sha256.hexdigest()


def _copy_with_atomic_replace(source: Path, destination: Path) -> None:
    with tempfile.NamedTemporaryFile(
        mode="wb",
        delete=False,
        dir=destination.parent,
        prefix=".spb-tmp-",
    ) as handle:
        temporary_path = Path(handle.name)
        with source.open("rb") as source_handle:
            shutil.copyfileobj(source_handle, handle, length=BUFFER_SIZE)

    try:
        temporary_path.replace(destination)
    except OSError:
        temporary_path.unlink(missing_ok=True)
        raise


def _is_reserved_top_level_path(relative_path: str) -> bool:
    return (
        relative_path == METADATA_DIR_RELATIVE.as_posix()
        or relative_path.startswith(
            f"{METADATA_DIR_RELATIVE.as_posix()}/",
        )
    )


def normalize_relative_path(path: Path) -> str:
    """Normalize a relative path into the manifest identity format."""
    return path.as_posix()


def _should_traverse_directory(
    *,
    relative_directory_path: str,
    directory_path: Path,
    summary: BackupSummary,
    warnings: list[str],
    errors: list[str],
) -> bool:
    if _is_reserved_top_level_path(relative_directory_path):
        summary.skipped_entries += 1
        warnings.append(f"Skipping reserved top-level path: {relative_directory_path}")
        return False

    try:
        directory_stat = directory_path.lstat()
    except OSError as exc:
        summary.error_count += 1
        errors.append(f"Error reading metadata for {relative_directory_path}: {exc}")
        return False

    if stat.S_ISLNK(directory_stat.st_mode):
        summary.skipped_entries += 1
        warnings.append(f"Skipping symlink directory: {relative_directory_path}")
        return False

    if not stat.S_ISDIR(directory_stat.st_mode):
        summary.skipped_entries += 1
        warnings.append(
            f"Skipping non-directory entry during traversal: {relative_directory_path}",
        )
        return False

    return True


def _classify_file(
    *,
    file_path: Path,
    relative_path: str,
    summary: BackupSummary,
    warnings: list[str],
    errors: list[str],
) -> os.stat_result | None:
    if _is_reserved_top_level_path(relative_path):
        summary.skipped_entries += 1
        warnings.append(f"Skipping reserved top-level path: {relative_path}")
        return None

    try:
        file_stat = file_path.lstat()
    except OSError as exc:
        summary.error_count += 1
        errors.append(f"Error reading metadata for {relative_path}: {exc}")
        return None

    if stat.S_ISLNK(file_stat.st_mode):
        summary.skipped_entries += 1
        warnings.append(f"Skipping symlink file: {relative_path}")
        return None

    if not stat.S_ISREG(file_stat.st_mode):
        summary.skipped_entries += 1
        warnings.append(f"Skipping non-regular file: {relative_path}")
        return None

    return file_stat
