"""
Screen capture module.
Uses mss for fast screenshots (~10x faster than PIL).
Thread-safe singleton with auto-recovery on stale handle.
"""

from __future__ import annotations

import logging
import threading
from typing import Any, cast

import cv2
import mss
import numpy as np
from numpy.typing import NDArray

logger = logging.getLogger(__name__)

# Thread-local mss instances: each thread gets its own handle (no lock contention)
_thread_local = threading.local()


def _get_sct() -> Any:
    """Get thread-local mss instance, creating one if needed."""
    sct = getattr(_thread_local, 'sct', None)
    if sct is None:
        _thread_local.sct = mss.mss()
        sct = _thread_local.sct
    if sct is None:
        raise RuntimeError("Failed to initialize mss screen capture")
    return sct


def _reset_sct() -> Any:
    """Recreate mss instance for current thread (after stale handle error)."""
    old = getattr(_thread_local, 'sct', None)
    try:
        if old:
            old.close()
    except Exception:
        pass
    _thread_local.sct = mss.mss()
    logger.info("mss instance recreated (thread=%s)", threading.current_thread().name)
    return _thread_local.sct


def _safe_grab(region: dict[str, int]) -> NDArray[np.uint8]:
    """Grab with auto-recovery on mss errors. Lock-free per-thread."""
    try:
        sct = _get_sct()
        return np.array(sct.grab(region))
    except Exception as e:
        logger.warning("mss grab failed (%s), recreating...", e)
        sct = _reset_sct()
        return np.array(sct.grab(region))


def capture_full_screen() -> NDArray[np.uint8]:
    """
    Capture the entire primary screen.
    Returns an OpenCV BGR numpy array.
    Thread-safe with auto-recovery.
    """
    sct = _get_sct()
    monitor = sct.monitors[1]  # primary monitor
    img = _safe_grab(monitor)
    # mss returns BGRA, convert to BGR for OpenCV
    return cast(NDArray[np.uint8], cv2.cvtColor(img, cv2.COLOR_BGRA2BGR))


def capture_full_screen_gray() -> NDArray[np.uint8]:
    """
    Capture primary screen directly as grayscale.
    Skips BGR intermediate → saves one full-frame color conversion.
    """
    sct = _get_sct()
    monitor = sct.monitors[1]
    img = _safe_grab(monitor)
    return cast(NDArray[np.uint8], cv2.cvtColor(img, cv2.COLOR_BGRA2GRAY))


def capture_region(x: int, y: int, width: int, height: int) -> NDArray[np.uint8]:
    """
    Capture a specific screen region.
    Returns an OpenCV BGR numpy array.
    Coordinates are clamped to screen bounds.
    """
    # Clamp to non-negative
    x = max(0, x)
    y = max(0, y)
    width = max(1, width)
    height = max(1, height)

    # Clamp to screen bounds
    sct = _get_sct()
    mon = sct.monitors[1]
    x = min(x, mon["width"] - 1)
    y = min(y, mon["height"] - 1)
    width = min(width, mon["width"] - x)
    height = min(height, mon["height"] - y)

    region = {"left": x, "top": y, "width": width, "height": height}
    img = _safe_grab(region)
    return cast(NDArray[np.uint8], cv2.cvtColor(img, cv2.COLOR_BGRA2BGR))


def capture_region_gray(x: int, y: int, width: int, height: int) -> NDArray[np.uint8]:
    """Capture region directly as grayscale (OPT-6: skip BGR intermediate)."""
    x, y = max(0, x), max(0, y)
    width, height = max(1, width), max(1, height)
    sct = _get_sct()
    mon = sct.monitors[1]
    x = min(x, mon["width"] - 1)
    y = min(y, mon["height"] - 1)
    width = min(width, mon["width"] - x)
    height = min(height, mon["height"] - y)
    region = {"left": x, "top": y, "width": width, "height": height}
    img = _safe_grab(region)
    return cast(NDArray[np.uint8], cv2.cvtColor(img, cv2.COLOR_BGRA2GRAY))


def get_screen_size() -> tuple[int, int]:
    """Return (width, height) of the primary monitor."""
    sct = _get_sct()
    mon = sct.monitors[1]
    return mon["width"], mon["height"]


def save_screenshot(filepath: str, region: tuple[int, int, int, int] | None = None) -> str:
    """
    Save a screenshot to disk.
    region: (x, y, width, height) or None for full screen.
    Returns the saved filepath.
    """
    if region:
        img = capture_region(*region)
    else:
        img = capture_full_screen()
    cv2.imwrite(filepath, img)
    logger.info("Screenshot saved: %s", filepath)
    return filepath


def capture_window(hwnd: int) -> NDArray[np.uint8]:
    """
    Capture a specific window using PrintWindow (Win32).

    Works on hidden, minimized, or occluded windows — the target does NOT
    need to be in the foreground. Returns an OpenCV BGR numpy array.

    This is complementary to mss-based capture: mss captures screen regions,
    while this captures a specific window regardless of its visibility state.

    Args:
        hwnd: Window handle (HWND) to capture.

    Returns:
        BGR numpy array (H, W, 3).
    """
    from core.win32_stealth import capture_window as _capture_win32
    return _capture_win32(hwnd)
