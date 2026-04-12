"""
AutoPilot – Auto Mouse & Keyboard with Image Recognition
Entry point for the application.
"""

import logging
import logging.handlers
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from core.hotkey_manager import HotkeyManager

from core.app_paths import LOG_DIR

logger = logging.getLogger("AutoPilot")


def setup_logging() -> None:
    """Initialize logging — call once from main(), NOT at import time."""
    LOG_DIR.mkdir(exist_ok=True)

    _log_formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    # Rotating log: 5MB per file, keep 3 backups (total max ~20MB)
    _file_handler = logging.handlers.RotatingFileHandler(
        LOG_DIR / "autopilot.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    _file_handler.setFormatter(_log_formatter)

    _console_handler = logging.StreamHandler(sys.stdout)
    _console_handler.setFormatter(_log_formatter)

    # Support --debug flag for verbose logging
    if "--debug" in sys.argv:
        _log_level_name = "DEBUG"
        sys.argv.remove("--debug")  # Remove so Qt doesn't see it
    else:
        _log_level_name = os.environ.get("AUTOPILOT_LOG_LEVEL", "INFO").upper()
    _log_level = getattr(logging, _log_level_name, logging.INFO)

    logging.basicConfig(
        level=_log_level,
        handlers=[_file_handler, _console_handler],
    )



def setup_global_hotkeys(config: dict[str, Any]) -> "HotkeyManager | None":
    """Register system-wide hotkeys using Win32 RegisterHotKey."""
    try:
        from PyQt6.QtCore import QTimer

        from core.hotkey_manager import HotkeyManager

        hotkeys = config.get("hotkeys", {})
        hk_mgr = HotkeyManager()

        def _find_main_window() -> Any:
            from PyQt6.QtWidgets import QApplication

            app = QApplication.instance()
            if app and isinstance(app, QApplication):
                for widget in app.topLevelWidgets():
                    if hasattr(widget, "_on_play"):
                        return widget
            return None

        def toggle_play() -> None:
            w = _find_main_window()
            if w:
                QTimer.singleShot(0, w._on_play)

        def toggle_pause() -> None:
            w = _find_main_window()
            if w:
                # If recording, pause/resume recording instead of engine
                if hasattr(w, "_rec_panel") and w._rec_panel._recorder.is_recording:
                    QTimer.singleShot(0, w._rec_panel._toggle_pause)
                    return
                QTimer.singleShot(0, w._on_pause)

        def emergency_stop() -> None:
            w = _find_main_window()
            if w:
                # If recording, stop recording
                if hasattr(w, "_rec_panel") and w._rec_panel._recorder.is_recording:
                    QTimer.singleShot(0, w._rec_panel._stop_recording)
                    return
                QTimer.singleShot(0, w._on_stop)

        def toggle_record() -> None:
            w = _find_main_window()
            if w and hasattr(w, "_rec_panel"):
                QTimer.singleShot(0, w._rec_panel.toggle_recording)

        start_key = hotkeys.get("start_stop", "F6")
        pause_key = hotkeys.get("pause_resume", "F7")
        stop_key = hotkeys.get("emergency_stop", "F8")
        record_key = hotkeys.get("record", "F9")

        hk_mgr.register(start_key, toggle_play)
        hk_mgr.register(pause_key, toggle_pause)
        hk_mgr.register(stop_key, emergency_stop)
        hk_mgr.register(record_key, toggle_record)
        hk_mgr.start()

        logger.info(
            "Global hotkeys (Win32): Start=%s, Pause=%s, Stop=%s, Record=%s", start_key, pause_key, stop_key, record_key
        )
        return hk_mgr  # Keep reference to prevent GC
    except Exception as e:
        logger.warning("Failed to set up global hotkeys: %s", e)
        return None


def main() -> None:
    # Change to app directory so relative paths work
    app_dir = Path(__file__).parent.resolve()
    os.chdir(app_dir)

    # Initialize logging (no side-effects at import time)
    setup_logging()

    # Fix Qt DPI warning: set DPI awareness BEFORE Qt loads
    # so Qt doesn't call SetProcessDpiAwarenessContext() again
    try:
        import ctypes

        awareness = ctypes.c_void_p(-4)  # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2
        ctypes.windll.user32.SetProcessDpiAwarenessContext(awareness)
    except (AttributeError, OSError):
        pass  # non-Windows or already set

    from PyQt6.QtWidgets import QApplication

    from gui.main_window import MainWindow
    from gui.settings_dialog import load_config

    app = QApplication(sys.argv)
    app.setApplicationName("AutoPilot")
    app.setOrganizationName("AutoPilot")

    # Suppress scroll-to-change-value on SpinBox/ComboBox when not focused
    from gui.no_scroll_widgets import patch_wheel_events
    patch_wheel_events()

    # --- Tier 1: CrashHandler (replaces simple excepthook) ---
    from core.crash_handler import CrashHandler

    CrashHandler.install()

    # --- Tier 1: MemoryManager for 24/7 stability ---
    from core.memory_manager import MemoryManager
    from modules.image import ImageFinder

    # Load config first to get user-defined memory threshold
    config = load_config()
    mem_threshold = config.get("performance", {}).get("memory_limit_mb", 200)
    mem_mgr = MemoryManager.instance()
    mem_mgr.set_threshold(mem_threshold)
    mem_mgr.register_cleanup(ImageFinder.clear_cache)
    mem_mgr.start()

    # Set up hotkeys (reuse config loaded above)
    _hk_mgr = setup_global_hotkeys(config)  # prevent GC

    # Show main window
    window = MainWindow()
    window._hk_mgr = _hk_mgr  # Enable restart-free hotkey rebind
    window.show()

    # Audit: log all registered action types for diagnostics
    from core.action import audit_registry

    registry = audit_registry()
    logger.info("Action registry: %d types registered", len(registry))
    logger.debug("Registry details: %s", registry)

    logger.info("AutoPilot started")
    exit_code = app.exec()

    # Clean shutdown
    mem_mgr.stop()
    logger.info("AutoPilot exiting with code %d", exit_code)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
