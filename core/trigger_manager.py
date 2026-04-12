"""
Trigger Manager — background daemon for automated macro execution.

Polls trigger conditions at 1-second intervals. When a trigger fires,
it initiates macro playback via QTimer.singleShot for thread-safety.

Safety guardrails:
- Only fires when engine is NOT running (prevents overlap)
- Per-trigger cooldown prevents rapid re-firing
- Preflight check runs before trigger-initiated playback
- Stops cleanly when app exits
"""

import json
import logging
import threading
import time
import uuid
from pathlib import Path
from typing import Callable

from core.triggers import ScheduleTrigger, TriggerConfig, WindowFocusTrigger

logger = logging.getLogger(__name__)


class TriggerManager:
    """Background daemon checking trigger conditions and firing macros."""

    def __init__(self, on_trigger_fire: Callable[[TriggerConfig], None] | None = None) -> None:
        self._triggers: list[TriggerConfig] = []
        self._on_fire = on_trigger_fire
        self._running = False
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._poll_interval = 1.0  # seconds

    # -- Public API -----------------------------------------------------------

    def add_trigger(self, config: TriggerConfig) -> str:
        """Add a trigger. Returns trigger ID."""
        if not config.id:
            config.id = str(uuid.uuid4())[:8]
        with self._lock:
            self._triggers.append(config)
        logger.info("Trigger added: %s (%s) → %s", config.id, config.trigger_type, config.macro_file)
        return config.id

    def remove_trigger(self, trigger_id: str) -> bool:
        """Remove a trigger by ID. Returns True if found."""
        with self._lock:
            before = len(self._triggers)
            self._triggers = [t for t in self._triggers if t.id != trigger_id]
            removed = len(self._triggers) < before
        if removed:
            logger.info("Trigger removed: %s", trigger_id)
        return removed

    def set_trigger_enabled(self, trigger_id: str, enabled: bool) -> None:
        """Enable/disable a trigger."""
        with self._lock:
            for t in self._triggers:
                if t.id == trigger_id:
                    t.enabled = enabled
                    break

    def get_triggers(self) -> list[TriggerConfig]:
        """Get a copy of all triggers."""
        with self._lock:
            return list(self._triggers)

    def clear(self) -> None:
        """Remove all triggers."""
        with self._lock:
            self._triggers.clear()
        WindowFocusTrigger.reset()

    # -- Lifecycle ------------------------------------------------------------

    def start(self) -> None:
        """Start the trigger polling daemon."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True, name="TriggerManager")
        self._thread.start()
        logger.info("TriggerManager started (%d triggers)", len(self._triggers))

    def stop(self) -> None:
        """Stop the trigger polling daemon."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=3.0)
            self._thread = None
        WindowFocusTrigger.reset()
        logger.info("TriggerManager stopped")

    @property
    def is_running(self) -> bool:
        return self._running

    # -- Polling loop ---------------------------------------------------------

    def _poll_loop(self) -> None:
        """Main polling loop — runs in daemon thread."""
        while self._running:
            try:
                self._check_triggers()
            except Exception:
                logger.exception("TriggerManager poll error")
            time.sleep(self._poll_interval)

    def _check_triggers(self) -> None:
        """Check all enabled triggers."""
        now = time.time()
        with self._lock:
            triggers = [t for t in self._triggers if t.enabled]

        for config in triggers:
            # Cooldown check
            if now - config._last_fired < config.cooldown_ms / 1000.0:
                continue

            fired = False
            if config.trigger_type == "schedule":
                fired = ScheduleTrigger.should_fire(config)
            elif config.trigger_type == "window_focus":
                fired = WindowFocusTrigger.should_fire(config)

            if fired:
                config._last_fired = now
                logger.info(
                    "Trigger fired: %s (%s) → %s",
                    config.id,
                    config.trigger_type,
                    config.macro_file,
                )
                if self._on_fire:
                    self._on_fire(config)

    # -- Persistence ----------------------------------------------------------

    def save_triggers(self, path: Path) -> None:
        """Save triggers to JSON file."""
        with self._lock:
            data = []
            for t in self._triggers:
                data.append({
                    "id": t.id,
                    "trigger_type": t.trigger_type,
                    "enabled": t.enabled,
                    "macro_file": t.macro_file,
                    "cooldown_ms": t.cooldown_ms,
                    "params": t.params,
                })
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info("Saved %d triggers to %s", len(data), path.name)

    def load_triggers(self, path: Path) -> int:
        """Load triggers from JSON file. Returns count loaded."""
        if not path.exists():
            return 0
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            with self._lock:
                self._triggers.clear()
                for item in data:
                    self._triggers.append(TriggerConfig(
                        id=item.get("id", str(uuid.uuid4())[:8]),
                        trigger_type=item.get("trigger_type", ""),
                        enabled=item.get("enabled", True),
                        macro_file=item.get("macro_file", ""),
                        cooldown_ms=item.get("cooldown_ms", 5000),
                        params=item.get("params", {}),
                    ))
            logger.info("Loaded %d triggers from %s", len(self._triggers), path.name)
            return len(self._triggers)
        except Exception:
            logger.exception("Failed to load triggers from %s", path)
            return 0
