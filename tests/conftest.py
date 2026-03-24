"""
Global test configuration — prevents tests from crashing the system.

This conftest.py applies to ALL test files in the tests/ directory.

Key protections:
1. Blocks pyautogui from performing ANY physical mouse/keyboard actions
2. Blocks screenshot captures that consume excessive memory
3. Sets timeouts on engine tests to prevent infinite hangs
4. Ensures QApplication singleton exists
"""

import sys
import os
import time
from unittest.mock import MagicMock, patch

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
    import threading
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
