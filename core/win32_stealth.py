"""
Win32 Stealth Automation Layer.

Provides non-invasive window interaction via PostMessage/SendMessage:
- Stealth clicks: send mouse events directly to a window's message queue
  without moving the physical cursor.
- Stealth keyboard: send keystrokes directly to a window without touching
  the physical keyboard.
- Background capture: capture a window's contents using PrintWindow,
  even when the window is hidden, minimized, or occluded.

All operations target a HWND (window handle) and do NOT require
Administrator privileges.

Limitations:
- DirectX/OpenGL fullscreen apps may not receive PostMessage events.
- Some UWP apps have restricted message queues.
- Apps that call GetCursorPos() will detect the cursor hasn't moved.
- Works well with: WinForms, WPF, Java Swing, Electron, Win32, web browsers.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wintypes
import logging
import random
import time
from typing import Optional

import numpy as np
from numpy.typing import NDArray

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════
#  Win32 Constants
# ══════════════════════════════════════════════════════

WM_MOUSEMOVE = 0x0200
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_RBUTTONDOWN = 0x0204
WM_RBUTTONUP = 0x0205
WM_LBUTTONDBLCLK = 0x0203
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_CHAR = 0x0102

MK_LBUTTON = 0x0001
MK_RBUTTON = 0x0002

PW_RENDERFULLCONTENT = 0x00000002
PW_CLIENTONLY = 0x00000001
SRCCOPY = 0x00CC0020

# ══════════════════════════════════════════════════════
#  Win32 API Bindings
# ══════════════════════════════════════════════════════

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
kernel32 = ctypes.windll.kernel32

# Message dispatch
user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.PostMessageW.restype = wintypes.BOOL

user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.SendMessageW.restype = wintypes.LPARAM

# Window discovery
user32.IsWindow.argtypes = [wintypes.HWND]
user32.IsWindow.restype = wintypes.BOOL

user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.IsWindowVisible.restype = wintypes.BOOL

user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowTextW.restype = ctypes.c_int

user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
user32.GetWindowTextLengthW.restype = ctypes.c_int

# Window geometry
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.GetWindowRect.restype = wintypes.BOOL

user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.GetClientRect.restype = wintypes.BOOL

# Capture
user32.PrintWindow.argtypes = [wintypes.HWND, wintypes.HDC, wintypes.UINT]
user32.PrintWindow.restype = wintypes.BOOL

user32.GetDC.argtypes = [wintypes.HWND]
user32.GetDC.restype = wintypes.HDC

user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
user32.ReleaseDC.restype = ctypes.c_int

gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
gdi32.CreateCompatibleDC.restype = wintypes.HDC

gdi32.CreateCompatibleBitmap.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]
gdi32.CreateCompatibleBitmap.restype = wintypes.HBITMAP

gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
gdi32.SelectObject.restype = wintypes.HGDIOBJ

gdi32.BitBlt.argtypes = [
    wintypes.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    wintypes.HDC, ctypes.c_int, ctypes.c_int, wintypes.DWORD,
]
gdi32.BitBlt.restype = wintypes.BOOL

gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
gdi32.DeleteObject.restype = wintypes.BOOL

gdi32.DeleteDC.argtypes = [wintypes.HDC]
gdi32.DeleteDC.restype = wintypes.BOOL

gdi32.GetDIBits.argtypes = [
    wintypes.HDC, wintypes.HBITMAP, wintypes.UINT, wintypes.UINT,
    ctypes.c_void_p, ctypes.c_void_p, wintypes.UINT,
]
gdi32.GetDIBits.restype = ctypes.c_int

# EnumWindows callback type
WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

user32.EnumWindows.argtypes = [WNDENUMPROC, wintypes.LPARAM]
user32.EnumWindows.restype = wintypes.BOOL


# ══════════════════════════════════════════════════════
#  BITMAPINFOHEADER for GetDIBits
# ══════════════════════════════════════════════════════

class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [
        ("bmiHeader", BITMAPINFOHEADER),
        # bmiColors is not needed for BI_RGB
    ]


# ══════════════════════════════════════════════════════
#  Coordinate Helpers
# ══════════════════════════════════════════════════════

def _make_lparam(x: int, y: int) -> int:
    """Pack (x, y) into LPARAM: MAKELPARAM(x, y) = (y << 16) | (x & 0xFFFF)."""
    return (y << 16) | (x & 0xFFFF)


# ══════════════════════════════════════════════════════
#  Window Discovery
# ══════════════════════════════════════════════════════

def get_window_title(hwnd: int) -> str:
    """Get the title text of a window."""
    length = user32.GetWindowTextLengthW(hwnd)
    if length == 0:
        return ""
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    return buf.value


def get_visible_windows() -> list[tuple[int, str]]:
    """
    Return all visible top-level windows with non-empty titles.
    Returns list of (hwnd, title) tuples, sorted by title.
    """
    results: list[tuple[int, str]] = []

    @WNDENUMPROC
    def callback(hwnd: int, _lparam: int) -> bool:
        if user32.IsWindowVisible(hwnd):
            title = get_window_title(hwnd)
            if title.strip():
                results.append((hwnd, title))
        return True

    user32.EnumWindows(callback, 0)
    results.sort(key=lambda x: x[1].lower())
    return results


def find_window_by_title(partial_title: str) -> Optional[int]:
    """
    Find the first visible top-level window whose title contains
    `partial_title` (case-insensitive).
    Returns HWND or None if not found.
    """
    partial_lower = partial_title.lower()

    @WNDENUMPROC
    def callback(hwnd: int, _lparam: int) -> bool:
        if user32.IsWindowVisible(hwnd):
            title = get_window_title(hwnd)
            if partial_lower in title.lower():
                result[0] = hwnd
                return False  # Stop enumeration
        return True

    result = [0]
    user32.EnumWindows(callback, 0)
    return result[0] if result[0] != 0 else None


def is_window_valid(hwnd: int) -> bool:
    """Check if a HWND is still a valid window."""
    return bool(user32.IsWindow(hwnd))


# ══════════════════════════════════════════════════════
#  Stealth Click — PostMessage-based
# ══════════════════════════════════════════════════════

def stealth_click(hwnd: int, x: int, y: int, right: bool = False) -> None:
    """
    Send a non-invasive click to a window via PostMessage.

    The physical cursor is NOT moved. The target window receives
    MOUSEMOVE → BUTTONDOWN → (humanized delay) → BUTTONUP.

    Args:
        hwnd: Target window handle.
        x: Client-relative X coordinate within the target window.
        y: Client-relative Y coordinate within the target window.
        right: If True, send right-click instead of left-click.
    """
    if not is_window_valid(hwnd):
        raise ValueError(f"Invalid window handle: 0x{hwnd:X}")

    lparam = _make_lparam(x, y)

    # MOUSEMOVE first — some apps require this to set internal hover state
    user32.PostMessageW(hwnd, WM_MOUSEMOVE, 0, lparam)
    time.sleep(0.010)  # 10ms settle

    if right:
        user32.PostMessageW(hwnd, WM_RBUTTONDOWN, MK_RBUTTON, lparam)
        time.sleep(random.uniform(0.020, 0.050))  # Humanized hold
        user32.PostMessageW(hwnd, WM_RBUTTONUP, 0, lparam)
    else:
        user32.PostMessageW(hwnd, WM_LBUTTONDOWN, MK_LBUTTON, lparam)
        time.sleep(random.uniform(0.020, 0.050))  # Humanized hold
        user32.PostMessageW(hwnd, WM_LBUTTONUP, 0, lparam)

    logger.debug(
        "Stealth %s-click at (%d, %d) on HWND=0x%X",
        "right" if right else "left", x, y, hwnd,
    )


def stealth_double_click(hwnd: int, x: int, y: int) -> None:
    """Send a stealth double-click via PostMessage."""
    if not is_window_valid(hwnd):
        raise ValueError(f"Invalid window handle: 0x{hwnd:X}")

    lparam = _make_lparam(x, y)

    user32.PostMessageW(hwnd, WM_MOUSEMOVE, 0, lparam)
    time.sleep(0.010)

    # First click
    user32.PostMessageW(hwnd, WM_LBUTTONDOWN, MK_LBUTTON, lparam)
    time.sleep(random.uniform(0.015, 0.030))
    user32.PostMessageW(hwnd, WM_LBUTTONUP, 0, lparam)

    time.sleep(random.uniform(0.030, 0.060))  # Inter-click gap

    # Second click (WM_LBUTTONDBLCLK)
    user32.PostMessageW(hwnd, WM_LBUTTONDBLCLK, MK_LBUTTON, lparam)
    time.sleep(random.uniform(0.015, 0.030))
    user32.PostMessageW(hwnd, WM_LBUTTONUP, 0, lparam)

    logger.debug("Stealth double-click at (%d, %d) on HWND=0x%X", x, y, hwnd)


# ══════════════════════════════════════════════════════
#  Stealth Keyboard — PostMessage-based
# ══════════════════════════════════════════════════════

def stealth_type_text(hwnd: int, text: str, delay_ms: int = 0) -> None:
    """
    Send text to a window via WM_CHAR messages.
    The physical keyboard is NOT touched.

    Args:
        hwnd: Target window handle.
        text: Characters to type.
        delay_ms: Inter-keystroke delay in milliseconds (0 = instant).
    """
    if not is_window_valid(hwnd):
        raise ValueError(f"Invalid window handle: 0x{hwnd:X}")

    for ch in text:
        user32.PostMessageW(hwnd, WM_CHAR, ord(ch), 0)
        if delay_ms > 0:
            time.sleep(delay_ms / 1000.0)

    logger.debug(
        "Stealth typed %d chars on HWND=0x%X (delay=%dms)",
        len(text), hwnd, delay_ms,
    )


def stealth_send_key(hwnd: int, vk_code: int) -> None:
    """Send a virtual key press (KEYDOWN + KEYUP) via PostMessage."""
    if not is_window_valid(hwnd):
        raise ValueError(f"Invalid window handle: 0x{hwnd:X}")

    user32.PostMessageW(hwnd, WM_KEYDOWN, vk_code, 0)
    time.sleep(random.uniform(0.010, 0.030))
    user32.PostMessageW(hwnd, WM_KEYUP, vk_code, 0)

    logger.debug("Stealth key 0x%X on HWND=0x%X", vk_code, hwnd)


# ══════════════════════════════════════════════════════
#  Background Window Capture — PrintWindow
# ══════════════════════════════════════════════════════

def capture_window(hwnd: int) -> NDArray[np.uint8]:
    """
    Capture a window's contents using PrintWindow.

    Works on hidden, minimized, or occluded windows — the target does NOT
    need to be in the foreground. Returns an OpenCV-compatible BGR numpy array.

    Args:
        hwnd: Target window handle.

    Returns:
        BGR numpy array (H, W, 3).

    Raises:
        ValueError: If HWND is invalid.
        RuntimeError: If capture fails.
    """
    if not is_window_valid(hwnd):
        raise ValueError(f"Invalid window handle: 0x{hwnd:X}")

    # Get window dimensions
    rect = wintypes.RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        raise RuntimeError(f"GetWindowRect failed for HWND=0x{hwnd:X}")

    width = rect.right - rect.left
    height = rect.bottom - rect.top
    if width <= 0 or height <= 0:
        raise RuntimeError(
            f"Window has zero size ({width}×{height}) for HWND=0x{hwnd:X}"
        )

    # Create compatible DC and bitmap
    hdc_screen = user32.GetDC(0)
    hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
    hbmp = gdi32.CreateCompatibleBitmap(hdc_screen, width, height)
    old_bmp = gdi32.SelectObject(hdc_mem, hbmp)

    try:
        # PrintWindow with PW_RENDERFULLCONTENT for DWM-composited capture
        ok = user32.PrintWindow(hwnd, hdc_mem, PW_RENDERFULLCONTENT)
        if not ok:
            # Fallback to client-only
            ok = user32.PrintWindow(hwnd, hdc_mem, PW_CLIENTONLY)
        if not ok:
            raise RuntimeError(
                f"PrintWindow failed for HWND=0x{hwnd:X}. "
                "Window may not support this capture method."
            )

        # Extract pixel data via GetDIBits
        bmi = BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = width
        bmi.bmiHeader.biHeight = -height  # Top-down DIB (negative = top-origin)
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32  # BGRA
        bmi.bmiHeader.biCompression = 0  # BI_RGB

        buffer = np.empty((height, width, 4), dtype=np.uint8)
        result = gdi32.GetDIBits(
            hdc_mem, hbmp, 0, height,
            buffer.ctypes.data,
            ctypes.byref(bmi),
            0,  # DIB_RGB_COLORS
        )
        if result == 0:
            raise RuntimeError(f"GetDIBits failed for HWND=0x{hwnd:X}")

        # BGRA → BGR (drop alpha channel)
        bgr = buffer[:, :, :3].copy()
        logger.debug(
            "Captured window HWND=0x%X (%d×%d)", hwnd, width, height,
        )
        return bgr

    finally:
        # Cleanup GDI resources — always release even on error
        gdi32.SelectObject(hdc_mem, old_bmp)
        gdi32.DeleteObject(hbmp)
        gdi32.DeleteDC(hdc_mem)
        user32.ReleaseDC(0, hdc_screen)
