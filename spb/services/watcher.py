"""Filesystem watch with debounced incremental backup (Milestone 3)."""

from __future__ import annotations

import contextlib
import signal
import threading
from collections.abc import Callable
from pathlib import Path

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from spb.constants import METADATA_DIR_RELATIVE
from spb.core.backup import BackupResult, run_backup

TimerFactory = Callable[[float, Callable[[], None]], threading.Timer]


def _default_timer_factory(delay: float, fn: Callable[[], None]) -> threading.Timer:
    timer = threading.Timer(delay, fn)
    timer.daemon = True
    return timer


class Debouncer:
    """Single-thread debounce: rapid ``ping`` calls collapse to one delayed callback."""

    def __init__(
        self,
        debounce_seconds: float,
        callback: Callable[[], None],
        *,
        timer_factory: TimerFactory,
    ) -> None:
        self._debounce_seconds = debounce_seconds
        self._callback = callback
        self._timer_factory = timer_factory
        self._lock = threading.Lock()
        self._timer: threading.Timer | None = None

    def ping(self) -> None:
        """Restart the debounce timer so ``callback`` runs after quiet period."""
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
            self._timer = self._timer_factory(self._debounce_seconds, self._fire)
            self._timer.start()

    def cancel(self) -> None:
        """Cancel any scheduled callback without running it."""
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None

    def _fire(self) -> None:
        with self._lock:
            self._timer = None
        self._callback()


class WatchCoordinator:
    """Coalesces filesystem noise into serialized ``run_backup`` calls."""

    def __init__(
        self,
        *,
        source: Path,
        destination: Path,
        debounce_seconds: float,
        on_backup_result: Callable[[BackupResult], None],
        timer_factory: TimerFactory | None = None,
    ) -> None:
        self._source = source
        self._destination = destination
        self._on_backup_result = on_backup_result
        self._state = threading.Lock()
        self._running = False
        self._rerun_wanted = False
        self._backup_worker: threading.Thread | None = None
        factory = timer_factory or _default_timer_factory
        self._debouncer = Debouncer(
            debounce_seconds,
            self._on_debounce_fire,
            timer_factory=factory,
        )

    def notify_filesystem_activity(self) -> None:
        """Schedule a debounced backup (or mark rerun if a backup is in progress)."""
        self._debouncer.ping()

    def cancel_pending_backup(self) -> None:
        """Cancel a scheduled backup timer (e.g. on shutdown)."""
        self._debouncer.cancel()

    def join_in_flight_backup(self, timeout: float | None = None) -> None:
        """Block until the current ``run_backup`` worker finishes, if any."""
        with self._state:
            worker = self._backup_worker
        if worker is not None and worker.is_alive():
            worker.join(timeout=timeout)

    def _run_backup_on_worker(self) -> None:
        try:
            result = run_backup(source=self._source, destination=self._destination)
            self._on_backup_result(result)
        finally:
            with self._state:
                self._running = False
                need_rerun = self._rerun_wanted
                self._rerun_wanted = False
                self._backup_worker = None
            if need_rerun:
                self._debouncer.ping()

    def _on_debounce_fire(self) -> None:
        with self._state:
            if self._running:
                self._rerun_wanted = True
                return
            self._running = True
            worker = threading.Thread(
                target=self._run_backup_on_worker,
                name="spb-backup",
                daemon=False,
            )
            self._backup_worker = worker
        worker.start()


_RESERVED_TOP_LEVEL = METADATA_DIR_RELATIVE.name


def _event_path_triggers_backup(source_root: Path, event_path: Path) -> bool:
    """Return True when a filesystem event should schedule a backup.

    Paths under the source tree's reserved top-level ``.spb`` directory are
    ignored to match manual backup rules. Resolved paths outside ``source_root``
    are ignored (e.g. symlink targets outside the tree).
    """
    try:
        resolved_root = source_root.resolve(strict=True)
        relative = event_path.resolve().relative_to(resolved_root)
    except ValueError:
        return False
    parts = relative.parts
    if parts and parts[0] == _RESERVED_TOP_LEVEL:
        return False
    return True


class _SourceTreeHandler(FileSystemEventHandler):
    """Forwards relevant filesystem events to a :class:`WatchCoordinator`."""

    def __init__(self, coordinator: WatchCoordinator, source_root: Path) -> None:
        super().__init__()
        self._coordinator = coordinator
        self._source_root = source_root

    def on_any_event(self, event: FileSystemEvent) -> None:
        candidate_paths: list[Path] = [Path(event.src_path)]
        dest_path = getattr(event, "dest_path", None)
        if dest_path:
            candidate_paths.append(Path(dest_path))
        if any(
            _event_path_triggers_backup(self._source_root, candidate)
            for candidate in candidate_paths
        ):
            self._coordinator.notify_filesystem_activity()


def _install_signal_handlers(stop_event: threading.Event) -> None:
    def handler(_signum: int, _frame: object) -> None:
        stop_event.set()

    signal.signal(signal.SIGINT, handler)
    with contextlib.suppress(OSError):
        # SIGTERM handler is not supported on some platforms under Python.
        signal.signal(signal.SIGTERM, handler)


def run_watch(
    *,
    source: Path,
    destination: Path,
    debounce_seconds: float,
    on_backup_result: Callable[[BackupResult], None],
    on_info: Callable[[str], None],
    poll_interval: float = 0.25,
) -> None:
    """Watch ``source`` recursively and run debounced incremental backups.

    Blocks until SIGINT or SIGTERM. Shutdown stops the observer, cancels any
    scheduled debounce timer, then waits for an in-flight ``run_backup`` (if
    any) to finish before returning.

    ``poll_interval`` is only the sleep granularity while waiting for shutdown;
    the ``watchdog`` observer uses OS-specific APIs for change notification.
    """
    resolved_source = source.expanduser()
    dest_path = destination.expanduser()
    stop_event = threading.Event()
    _install_signal_handlers(stop_event)

    coordinator = WatchCoordinator(
        source=resolved_source,
        destination=dest_path,
        debounce_seconds=debounce_seconds,
        on_backup_result=on_backup_result,
    )
    observer = Observer()
    handler = _SourceTreeHandler(coordinator, resolved_source)
    watch_path = str(resolved_source.resolve(strict=True))
    observer.schedule(handler, watch_path, recursive=True)
    observer.start()
    on_info(
        f"Watching {resolved_source} -> {dest_path} "
        f"(debounce {debounce_seconds}s, Ctrl+C to stop).",
    )
    try:
        while not stop_event.wait(timeout=poll_interval):
            pass
    finally:
        observer.stop()
        observer.join(timeout=10.0)
        coordinator.cancel_pending_backup()
        coordinator.join_in_flight_backup()
