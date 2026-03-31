"""Tests for debounced filesystem watching."""

from __future__ import annotations

import tempfile
import threading
import unittest
from pathlib import Path
from typing import ClassVar
from unittest.mock import patch

from spb.core.backup import BackupResult
from spb.core.shared import BackupSummary
from spb.services.watcher import (
    Debouncer,
    WatchCoordinator,
    _event_path_triggers_backup,
)


class _RecordingTimer:
    """Captures timer state for :class:`Debouncer` tests (does not run callbacks)."""

    instances: ClassVar[list[_RecordingTimer]] = []

    def __init__(self, interval: float, function: object) -> None:
        self.interval = interval
        self.function = function
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def start(self) -> None:
        _RecordingTimer.instances.append(self)

    @property
    def cancelled(self) -> bool:
        return self._cancelled


def _fake_timer_factory(delay: float, fn: object) -> threading.Timer:
    return _RecordingTimer(delay, fn)  # type: ignore[return-value]


class DebouncerTests(unittest.TestCase):
    """Unit tests for debounce coalescing."""

    def tearDown(self) -> None:
        _RecordingTimer.instances.clear()

    def test_ping_cancels_previous_timer(self) -> None:
        debouncer = Debouncer(1.0, lambda: None, timer_factory=_fake_timer_factory)
        debouncer.ping()
        debouncer.ping()
        self.assertEqual(len(_RecordingTimer.instances), 2)
        self.assertTrue(_RecordingTimer.instances[0].cancelled)
        self.assertFalse(_RecordingTimer.instances[1].cancelled)

    def test_cancel_clears_pending_timer(self) -> None:
        debouncer = Debouncer(1.0, lambda: None, timer_factory=_fake_timer_factory)
        debouncer.ping()
        debouncer.cancel()
        self.assertTrue(_RecordingTimer.instances[-1].cancelled)


class EventPathFilterTests(unittest.TestCase):
    """Tests for reserved-path filtering aligned with backup rules."""

    def test_reserved_spb_under_source_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            event_path = root / ".spb" / "x.txt"
            event_path.parent.mkdir(parents=True, exist_ok=True)
            event_path.write_text("x", encoding="utf-8")
            self.assertFalse(_event_path_triggers_backup(root, event_path))

    def test_regular_file_triggers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            f = root / "a.txt"
            f.write_text("a", encoding="utf-8")
            self.assertTrue(_event_path_triggers_backup(root, f))


def _empty_result() -> BackupResult:
    return BackupResult(summary=BackupSummary(), warnings=[], errors=[])


class WatchCoordinatorTests(unittest.TestCase):
    """Tests for serialized backup invocation."""

    def test_result_callback_invoked(self) -> None:
        received: list[BackupResult] = []

        with patch(
            "spb.services.watcher.run_backup",
            return_value=_empty_result(),
        ):
            coordinator = WatchCoordinator(
                source=Path("/tmp/spb-src"),
                destination=Path("/tmp/spb-dest"),
                debounce_seconds=0.01,
                on_backup_result=received.append,
                timer_factory=_fake_timer_factory,
            )
            coordinator._on_debounce_fire()

        self.assertEqual(len(received), 1)


class WatchCoordinatorRerunTests(unittest.TestCase):
    """Rerun is requested if a debounced fire happens during an in-flight backup."""

    def tearDown(self) -> None:
        _RecordingTimer.instances.clear()

    def test_debounce_fire_while_running_sets_followup_timer(self) -> None:
        received: list[BackupResult] = []
        entered_backup = threading.Event()
        exit_backup = threading.Event()

        def fake_run_backup(**_kwargs: object) -> BackupResult:
            entered_backup.set()
            assert exit_backup.wait(timeout=5.0)
            return _empty_result()

        def short_timer(delay: float, fn: object) -> threading.Timer:
            return _RecordingTimer(delay, fn)  # type: ignore[return-value]

        with patch(
            "spb.services.watcher.run_backup",
            side_effect=fake_run_backup,
        ):
            coordinator = WatchCoordinator(
                source=Path("/tmp/spb-src"),
                destination=Path("/tmp/spb-dest"),
                debounce_seconds=9.99,
                on_backup_result=received.append,
                timer_factory=short_timer,
            )
            worker = threading.Thread(target=coordinator._on_debounce_fire)
            worker.start()
            assert entered_backup.wait(timeout=5.0)
            coordinator._on_debounce_fire()
            exit_backup.set()
            worker.join(timeout=5.0)

        self.assertEqual(len(received), 1)
        self.assertGreaterEqual(len(_RecordingTimer.instances), 1)
