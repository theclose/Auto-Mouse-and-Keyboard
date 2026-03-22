"""
Screen capture module.
Uses mss for fast screenshots (~10x faster than PIL).
Thread-safe singleton with auto-recovery on stale handle.
"""
from __future__ import annotations

import logging
import threading
from typing import Any, Optional, cast

import cv2
import mss
import numpy as np
from numpy.typing import NDArray

logger = logging.getLogger(__name__)

# Thread-safe mss singleton
_sct: Any = None
_sct_lock = threading.Lock()


def _get_sct() -> Any:
    global _sct
    if _sct is None:
        with _sct_lock:
            if _sct is None:
                _sct = mss.mss()
    assert _sct is not None
    return _sct


def _reset_sct() -> Any:
    """Recreate mss instance (after stale handle error)."""
    global _sct
    with _sct_lock:
        try:
            if _sct:
                _sct.close()
        except Exception:
            pass
        _sct = mss.mss()
        logger.info("mss instance recreated")
        return _sct


def _safe_grab(region: dict[str, int]) -> NDArray[np.uint8]:
    """Grab with auto-recovery on mss errors (OPT-5: no ThreadPool overhead)."""
    try:
        sct = _get_sct()
        with _sct_lock:
            return np.array(sct.grab(region))
    except Exception as e:
        logger.warning("mss grab failed (%s), recreating...", e)
        sct = _reset_sct()
        with _sct_lock:
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
