"""
AppEventBus — Central event bus for decoupled component communication.

Panels and widgets subscribe to events instead of directly connecting
to engine signals. This reduces coupling and allows independent testing.

Usage:
    from core.event_bus import AppEventBus
    bus = AppEventBus.instance()
    bus.engine_started.connect(my_handler)
"""

from PyQt6.QtCore import QObject, pyqtSignal


class AppEventBus(QObject):
    """Singleton event bus — bridges engine signals and UI events."""

    # ── Engine lifecycle events ─────────────────────────────────
    engine_started = pyqtSignal()
    engine_stopped = pyqtSignal()
    engine_error = pyqtSignal(str)
    engine_progress = pyqtSignal(int, int)  # current, total
    engine_action = pyqtSignal(str)  # action display name
    engine_loop = pyqtSignal(int, int)  # current, total
    engine_step = pyqtSignal(int, str)  # index, name

    # ── UI / macro events ──────────────────────────────────────
    macro_loaded = pyqtSignal(str)  # file path
    macro_saved = pyqtSignal(str)  # file path
    actions_changed = pyqtSignal()  # action list modified
    theme_changed = pyqtSignal(str)  # theme name

    # ── Singleton ──────────────────────────────────────────────
    _instance: "AppEventBus | None" = None

    @classmethod
    def instance(cls) -> "AppEventBus":
        """Get or create the global event bus."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset singleton (for testing)."""
        cls._instance = None

    def bridge_engine(self, engine) -> None:
        """Connect engine signals to bus signals (one-way forward).

        Call this after creating/replacing the MacroEngine instance.
        """
        engine.started_signal.connect(self.engine_started.emit)
        engine.stopped_signal.connect(self.engine_stopped.emit)
        engine.error_signal.connect(self.engine_error.emit)
        engine.progress_signal.connect(self.engine_progress.emit)
        engine.action_signal.connect(self.engine_action.emit)
        engine.loop_signal.connect(self.engine_loop.emit)
        engine.step_signal.connect(self.engine_step.emit)
