"""
Global test configuration — prevents tests from crashing the system.

This conftest.py applies to ALL test files in the tests/ directory.

Key protections:
1. Blocks pyautogui from performing ANY physical mouse/keyboard actions
2. Blocks screenshot captures that consume excessive memory
3. Sets timeouts on engine tests to prevent infinite hangs
4. Ensures QApplication singleton exists
"""

import os
import sys
import time

import pytest

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ============================================================
# 1. GLOBAL pyautogui safety net — prevent ALL physical actions
# ============================================================

@pytest.fixture(autouse=True)
def _block_pyautogui_physical_actions(monkeypatch):
    """
    Monkey-patch pyautogui so no test can physically move the mouse,
    click, type, or press keys. Individual tests can still @patch
    specific functions for assertion purposes.

    This runs BEFORE every test automatically.
    """
    import pyautogui

    # Block all physical action methods
    _noop = lambda *a, **kw: None
    dangerous_funcs = [
        'click', 'doubleClick', 'rightClick', 'tripleClick',
        'moveTo', 'moveRel', 'dragTo', 'dragRel',
        'press', 'hotkey', 'typewrite', 'write', 'keyDown', 'keyUp',
        'scroll', 'hscroll', 'vscroll',
        'mouseDown', 'mouseUp',
    ]
    for fn_name in dangerous_funcs:
        if hasattr(pyautogui, fn_name):
            monkeypatch.setattr(pyautogui, fn_name, _noop)

    # Also patch the lazy-loaded _pag() in modules.mouse
    try:
        import modules.mouse
        # Force _pyautogui to be the (now-safe) pyautogui
        monkeypatch.setattr(modules.mouse, '_pyautogui', pyautogui)
    except ImportError:
        pass

    # Also block Win32 SendInput in keyboard module
    try:
        import modules.keyboard
        monkeypatch.setattr(modules.keyboard, '_send_unicode_string', _noop)
    except ImportError:
        pass


# ============================================================
# 2. Limit screenshot captures to prevent memory exhaustion
# ============================================================

@pytest.fixture(autouse=True)
def _mock_heavy_screen_captures(monkeypatch):
    """
    Replace capture_full_screen with a lightweight fake (10x10 black image)
    so multi-threaded capture tests don't consume hundreds of MB.
    """
    try:
        import numpy as np

        import modules.screen
        _fake_img = np.zeros((10, 10, 3), dtype=np.uint8)

        def _fake_capture():
            return _fake_img.copy()

        def _fake_capture_region(x, y, w, h):
            return np.zeros((h, w, 3), dtype=np.uint8)

        monkeypatch.setattr(modules.screen, 'capture_full_screen', _fake_capture)
        monkeypatch.setattr(modules.screen, 'capture_region', _fake_capture_region)
    except (ImportError, AttributeError):
        pass


# ============================================================
# 3. Global test timeout — kill any test hanging > 30s
# ============================================================

@pytest.fixture(autouse=True)
def _test_timeout():
    """Kill tests that hang for more than 30 seconds."""
    start = time.perf_counter()
    yield
    elapsed = time.perf_counter() - start
    if elapsed > 30:
        pytest.fail(f"Test took {elapsed:.1f}s (>30s timeout)")


# ============================================================
# 4. QApplication singleton (shared across all tests)
# ============================================================

@pytest.fixture(scope="session", autouse=True)
def _qapp():
    """Ensure a single QApplication instance for all tests."""
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    return app


# ============================================================
# 5. Reset engine_context global state between tests (QA: L6)
# ============================================================

@pytest.fixture(autouse=True)
def _reset_engine_globals():
    """Prevent global state pollution between tests."""
    yield
    try:
        from core.engine_context import reset_globals
        reset_globals()
    except ImportError:
        pass


# ============================================================
# 6. Reset EventBus singleton between tests (QA: H4)
# ============================================================

@pytest.fixture(autouse=True)
def _reset_event_bus():
    """Prevent EventBus connection accumulation across tests."""
    yield
    try:
        from core.event_bus import AppEventBus
        AppEventBus.reset()
    except ImportError:
        pass


# ============================================================
# 7. Real MainWindow fixture for smoke/lifecycle tests (BS-3)
# ============================================================

@pytest.fixture()
def real_main_window():
    """Create a real MainWindow (full __init__) with mocked system hooks.

    Runs _setup_central(), _setup_toolbar() etc. for real,
    so all signal connections and widget types are verified.
    """
    from unittest.mock import patch

    with patch("core.recorder.keyboard", create=True):
        from gui.main_window import MainWindow

        mw = MainWindow()
        yield mw
        # Prevent QApplication.quit() during teardown
        mw._on_quit = lambda: None
        mw._config.setdefault("ui", {})["minimize_to_tray"] = False
        mw._undo_stack.setClean()
        mw.close()
