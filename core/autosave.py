"""
AutoSave Manager – Periodic macro auto-save with backup rotation.

Features:
- Daemon thread saves every 60s (configurable)
- Only saves when dirty flag is set (changes detected)
- Keeps N backup copies with rotation
- Thread-safe
"""

import logging
import shutil
import threading
import time
from collections.abc import Callable
from pathlib import Path

logger = logging.getLogger("AutoSave")


class AutoSaveManager:
    """
    Background auto-save with backup rotation.

    Usage:
        autosave = AutoSaveManager(interval_s=60, max_backups=5)
        autosave.start(save_callback=my_save_fn, backup_dir=Path("macros"))
        autosave.mark_dirty()  # when user modifies something
        ...
        autosave.stop()
    """

    def __init__(self, interval_s: int = 60, max_backups: int = 5):
        self._interval = interval_s
        self._max_backups = max_backups
        self._running = False
        self._dirty_event = threading.Event()
        self._stop_event = threading.Event()  # HARD-3: for interruptible sleep
        self._thread: threading.Thread | None = None
        self._save_callback: Callable[[], bool] | None = None
        self._backup_dir: Path | None = None
        self._current_file: Path | None = None

    def start(
        self,
        save_callback: Callable[[], bool],
        backup_dir: Path,
        current_file: Path | None = None,
    ) -> None:
        """Start background auto-save thread."""
        if self._running:
            return
        self._save_callback = save_callback
        self._backup_dir = backup_dir
        self._current_file = current_file
        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="AutoSave")
        self._thread.start()
        logger.info("AutoSave started (interval=%ds)", self._interval)

    def stop(self) -> None:
        self._running = False
        self._stop_event.set()  # HARD-3: wake thread immediately
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None

    def mark_dirty(self) -> None:
        """Flag that changes need saving."""
        self._dirty_event.set()

    def mark_clean(self) -> None:
        self._dirty_event.clear()

    def set_current_file(self, path: Path | None) -> None:
        self._current_file = path

    def _loop(self) -> None:
        while self._running:
            # HARD-3: Interruptible sleep — wakes immediately on stop()
            self._stop_event.wait(timeout=self._interval)
            if not self._running:
                break
            if self._dirty_event.is_set() and self._save_callback:
                try:
                    self._create_backup()
                    if self._save_callback():
                        self._dirty_event.clear()
                        logger.info("AutoSave completed")
                except Exception as e:
                    logger.exception("AutoSave failed: %s", e)

    def _create_backup(self) -> None:
        if not self._backup_dir or not self._current_file:
            return
        if not self._current_file.exists():
            return

        backup_dir = self._backup_dir / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)

        # Rotate old backups
        backups = sorted(backup_dir.glob("backup_*.json"))
        while len(backups) >= self._max_backups:
            oldest = backups.pop(0)
            try:
                oldest.unlink()
            except (OSError, PermissionError):
                pass

        # Copy current file
        ts = time.strftime("%Y%m%d_%H%M%S")
        backup_path = backup_dir / f"backup_{ts}.json"
        shutil.copy2(self._current_file, backup_path)
        logger.debug("Backup created: %s", backup_path.name)
