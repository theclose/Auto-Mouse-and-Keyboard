"""
AppEventBus — Central event bus for decoupled component communication.

Panels and widgets subscribe to events instead of directly connecting
to engine signals. This reduces coupling and allows independent testing.

Usage:
    from core.event_bus import AppEventBus
    bus = AppEventBus.instance()
    bus.engine_started.connect(my_handler)
"""

__all__ = ['AppEventBus']


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

    _SIGNAL_PAIRS = [
        ("started_signal", "engine_started"),
        ("stopped_signal", "engine_stopped"),
        ("error_signal", "engine_error"),
        ("progress_signal", "engine_progress"),
        ("action_signal", "engine_action"),
        ("loop_signal", "engine_loop"),
        ("step_signal", "engine_step"),
    ]

    def bridge_engine(self, engine) -> None:
        """Connect engine signals to bus signals (one-way forward).

        Call this after creating/replacing the MacroEngine instance.
        Automatically disconnects previous engine to prevent duplicates.
        """
        # Disconnect previous engine (H4: prevent connection leak)
        old = getattr(self, "_bridged_engine", None)
        old_refs = getattr(self, "_bridge_refs", [])
        if old is not None:
            for eng_sig_name, ref in old_refs:
                try:
                    getattr(old, eng_sig_name).disconnect(ref)
                except (TypeError, RuntimeError):
                    pass  # Already disconnected or engine destroyed
        # Connect new engine and store references for future disconnect
        self._bridged_engine = engine
        self._bridge_refs = []
        for eng_sig, bus_sig in self._SIGNAL_PAIRS:
            bus_emit = getattr(self, bus_sig).emit  # Capture reference
            getattr(engine, eng_sig).connect(bus_emit)
            self._bridge_refs.append((eng_sig, bus_emit))
