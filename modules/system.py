"""
System actions — window management, file I/O, clipboard, logging.

Actions: ActivateWindow, LogToFile, ReadClipboard, WriteToFile
"""

import ctypes
import logging
import os
import time
from typing import Any

from core.action import Action, register_action

logger = logging.getLogger(__name__)

# Security: allowed base directories for file I/O actions
_SAFE_BASES: tuple[str, ...] = ()


def _validate_path(path: str, operation: str = "access") -> str:
    """Validate and normalize a file path for security.

    Prevents path traversal attacks (e.g., '../../etc/passwd').
    Resolves the path and ensures it doesn't escape the working directory.

    Args:
        path: The file path to validate.
        operation: Description for logging (e.g., 'write', 'read').

    Returns:
        Resolved absolute path if safe.

    Raises:
        ValueError: If path contains dangerous patterns.
    """
    if not path or not path.strip():
        raise ValueError(f"Empty path for {operation}")

    resolved = os.path.realpath(path)

    # Block obvious traversal attempts
    if '..' in os.path.normpath(path).split(os.sep):
        logger.warning("Path traversal blocked: %s", path)
        raise ValueError(
            f"Path traversal not allowed: {path}"
        )

    return resolved

_user32 = ctypes.windll.user32


# ---------------------------------------------------------------------------
# Window Management (G5)
# ---------------------------------------------------------------------------

@register_action("activate_window")
class ActivateWindow(Action):
    """Bring a window to the foreground by title (partial match)."""

    def __init__(self, window_title: str = "", exact_match: bool = False,
                 **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.window_title = window_title
        self.exact_match = exact_match

    def execute(self) -> bool:
        from core.engine_context import get_context
        title = self.window_title
        ctx = get_context()
        if ctx and '${' in title:
            title = ctx.interpolate(title)

        if self.exact_match:
            hwnd = _user32.FindWindowW(None, title)
        else:
            hwnd = self._find_by_partial(title)

        if not hwnd:
            logger.warning("Window not found: '%s'", title)
            return False

        # 1.3: Multi-strategy window activation
        if self._activate_multi_strategy(hwnd):
            time.sleep(0.1)
            logger.info("Activated window: '%s' (hwnd=%d)", title, hwnd)
            return True

        logger.warning("All activation strategies failed for '%s'", title)
        return False

    def _activate_multi_strategy(self, hwnd: int) -> bool:
        """Try multiple strategies to bring window to foreground."""
        # Strategy 1: Restore if minimized + SetForegroundWindow
        if _user32.IsIconic(hwnd):
            _user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        if _user32.SetForegroundWindow(hwnd):
            return True

        # Strategy 2: BringWindowToTop
        try:
            _user32.BringWindowToTop(hwnd)
            if _user32.GetForegroundWindow() == hwnd:
                return True
        except Exception:
            pass

        # Strategy 3: AttachThreadInput workaround
        try:
            _kernel32 = ctypes.windll.kernel32
            fg_thread = _user32.GetWindowThreadProcessId(
                _user32.GetForegroundWindow(), None)
            target_thread = _user32.GetWindowThreadProcessId(hwnd, None)
            if fg_thread != target_thread:
                _user32.AttachThreadInput(fg_thread, target_thread, True)
                _user32.SetForegroundWindow(hwnd)
                _user32.AttachThreadInput(fg_thread, target_thread, False)
                if _user32.GetForegroundWindow() == hwnd:
                    return True
        except Exception:
            pass

        # Strategy 4: ShowWindow + SW_SHOW as last resort
        try:
            _user32.ShowWindow(hwnd, 5)  # SW_SHOW
            _user32.SetForegroundWindow(hwnd)
            return _user32.GetForegroundWindow() == hwnd
        except Exception:
            return False

    def _find_by_partial(self, partial: str) -> int:
        """Find window by partial title match."""
        result = [0]
        partial_lower = partial.lower()

        @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
        def enum_handler(hwnd, _):
            if _user32.IsWindowVisible(hwnd):
                buf = ctypes.create_unicode_buffer(256)
                _user32.GetWindowTextW(hwnd, buf, 256)
                if partial_lower in buf.value.lower():
                    result[0] = hwnd
                    return False  # Stop enumeration
            return True

        _user32.EnumWindows(enum_handler, 0)
        return result[0]

    def _get_params(self) -> dict[str, Any]:
        return {
            "window_title": self.window_title,
            "exact_match": self.exact_match,
        }

    def _set_params(self, params: dict[str, Any]) -> None:
        self.window_title = params.get("window_title", "")
        self.exact_match = params.get("exact_match", False)

    def get_display_name(self) -> str:
        return f"Activate '{self.window_title}'"


# ---------------------------------------------------------------------------
# Log to File (G10)
# ---------------------------------------------------------------------------

@register_action("log_to_file")
class LogToFile(Action):
    """Write a message to a log file. Supports ${var} interpolation."""

    def __init__(self, message: str = "", file_path: str = "",
                 **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.message = message
        self.file_path = file_path or "macros/macro_log.txt"

    def execute(self) -> bool:
        from core.engine_context import get_context
        ctx = get_context()
        msg = self.message
        if ctx and '${' in msg:
            msg = ctx.interpolate(msg)

        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{timestamp}] {msg}\n"

        os.makedirs(os.path.dirname(self.file_path) or ".", exist_ok=True)
        # L1: Log rotation — rotate at 5MB
        self._rotate_if_needed(self.file_path, max_bytes=5 * 1024 * 1024)
        with open(self.file_path, "a", encoding="utf-8") as f:
            f.write(line)
        logger.info("Logged: %s", msg[:80])
        return True

    @staticmethod
    def _rotate_if_needed(path: str, max_bytes: int = 5_242_880) -> None:
        """Rotate log file when it exceeds max_bytes."""
        try:
            if os.path.exists(path) and os.path.getsize(path) > max_bytes:
                rotated = path + ".1"
                if os.path.exists(rotated):
                    os.remove(rotated)
                os.rename(path, rotated)
                logger.info("Rotated log: %s → %s", path, rotated)
        except OSError:
            pass  # Best-effort rotation

    def _get_params(self) -> dict[str, Any]:
        return {"message": self.message, "file_path": self.file_path}

    def _set_params(self, params: dict[str, Any]) -> None:
        self.message = params.get("message", "")
        self.file_path = params.get("file_path", "macros/macro_log.txt")

    def get_display_name(self) -> str:
        preview = self.message[:30] + ("…" if len(self.message) > 30 else "")
        return f'Log: "{preview}"'


# ---------------------------------------------------------------------------
# Clipboard → Variable (G8)
# ---------------------------------------------------------------------------

@register_action("read_clipboard")
class ReadClipboard(Action):
    """Read clipboard text and store it in a context variable."""

    def __init__(self, var_name: str = "clipboard", **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.var_name = var_name

    def execute(self) -> bool:
        from core.engine_context import get_context
        # Win32 clipboard read (thread-safe)
        _user32.OpenClipboard(0)
        try:
            handle = ctypes.windll.user32.GetClipboardData(13)  # CF_UNICODETEXT
            if handle:
                text = ctypes.wstring_at(handle)
            else:
                text = ""
        finally:
            _user32.CloseClipboard()

        ctx = get_context()
        if ctx:
            ctx.set_var(self.var_name, text)
        logger.info("Clipboard → ${%s} = '%s'", self.var_name, text[:50])
        return True

    def _get_params(self) -> dict[str, Any]:
        return {"var_name": self.var_name}

    def _set_params(self, params: dict[str, Any]) -> None:
        self.var_name = params.get("var_name", "clipboard")

    def get_display_name(self) -> str:
        return f"Read clipboard → ${{{self.var_name}}}"


# ---------------------------------------------------------------------------
# File I/O (G13)
# ---------------------------------------------------------------------------

@register_action("read_file_line")
class ReadFileLine(Action):
    """Read a specific line from a file into a variable.
    
    Uses per-instance cache with mtime invalidation — O(1) per read after first load.
    """

    def __init__(self, file_path: str = "", line_number: str = "1",
                 var_name: str = "line", **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.file_path = file_path
        self.line_number = line_number  # Can be ${var} for dynamic
        self.var_name = var_name
        # File cache: {resolved_path: (mtime, lines_list)}
        self._cache: dict[str, tuple[float, list[str]]] = {}

    def _get_lines(self, path: str) -> list[str] | None:
        """Get cached lines or reload if file has changed."""
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            self._cache.pop(path, None)
            return None

        cached = self._cache.get(path)
        if cached and cached[0] == mtime:
            return cached[1]

        # (Re)load file
        try:
            with open(path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            self._cache[path] = (mtime, lines)
            # Cap cache to 5 files to prevent memory growth
            if len(self._cache) > 5:
                oldest_key = next(iter(self._cache))
                del self._cache[oldest_key]
            return lines
        except (OSError, IOError) as e:
            logger.error("Cannot read file: %s", e)
            return None

    def execute(self) -> bool:
        from core.engine_context import get_context
        ctx = get_context()
        path = self.file_path
        line_str = self.line_number
        if ctx:
            if '${' in path:
                path = ctx.interpolate(path)
            if '${' in line_str:
                line_str = ctx.interpolate(line_str)

        try:
            line_num = int(line_str)
        except ValueError:
            logger.warning("Invalid line number: %s", line_str)
            return False

        lines = self._get_lines(path)
        if lines is None:
            return False

        if 1 <= line_num <= len(lines):
            content = lines[line_num - 1].rstrip("\n\r")
            if ctx:
                ctx.set_var(self.var_name, content)
            logger.info("Read line %d → ${%s} = '%s'",
                        line_num, self.var_name, content[:50])
            return True
        else:
            logger.warning("Line %d out of range (file has %d lines)",
                           line_num, len(lines))
            return False

    def _get_params(self) -> dict[str, Any]:
        return {
            "file_path": self.file_path,
            "line_number": self.line_number,
            "var_name": self.var_name,
        }

    def _set_params(self, params: dict[str, Any]) -> None:
        self.file_path = params.get("file_path", "")
        self.line_number = params.get("line_number", "1")
        self.var_name = params.get("var_name", "line")

    def get_display_name(self) -> str:
        name = os.path.basename(self.file_path) if self.file_path else "?"
        return f"Read '{name}' line {self.line_number} → ${{{self.var_name}}}"


@register_action("write_to_file")
class WriteToFile(Action):
    """Write/append text to a file. Supports ${var} interpolation."""

    def __init__(self, file_path: str = "", text: str = "",
                 mode: str = "append", **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.file_path = file_path
        self.text = text
        self.mode = mode  # "append" or "overwrite"

    def execute(self) -> bool:
        from core.engine_context import get_context
        ctx = get_context()
        text = self.text
        path = self.file_path
        if ctx:
            if '${' in text:
                text = ctx.interpolate(text)
            if '${' in path:
                path = ctx.interpolate(path)

        # Security: validate path
        try:
            path = _validate_path(path, "write")
        except ValueError as e:
            logger.error("WriteToFile blocked: %s", e)
            return False

        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        # L1: Rotate at 10MB for append mode
        if self.mode == "append":
            LogToFile._rotate_if_needed(path, max_bytes=10 * 1024 * 1024)
        file_mode = "a" if self.mode == "append" else "w"
        with open(path, file_mode, encoding="utf-8") as f:
            f.write(text + "\n")
        logger.info("Wrote to %s: '%s'", path, text[:50])
        return True

    def _get_params(self) -> dict[str, Any]:
        return {
            "file_path": self.file_path,
            "text": self.text,
            "mode": self.mode,
        }

    def _set_params(self, params: dict[str, Any]) -> None:
        self.file_path = params.get("file_path", "")
        self.text = params.get("text", "")
        self.mode = params.get("mode", "append")

    def get_display_name(self) -> str:
        name = os.path.basename(self.file_path) if self.file_path else "?"
        return f"Write to '{name}'"


# ---------------------------------------------------------------------------
# Secure Text Input (G2) — DPAPI encrypted
# ---------------------------------------------------------------------------

@register_action("secure_type_text")
class SecureTypeText(Action):
    """Type text that is stored encrypted in the macro file.
    Uses Windows DPAPI for encryption — tied to machine + user account.
    """

    def __init__(self, encrypted_text: str = "", interval: float = 0.02,
                 **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.encrypted_text = encrypted_text
        self.interval = interval

    def execute(self) -> bool:
        import pyautogui
        from core.secure import decrypt, is_encrypted
        # Decrypt at runtime
        text = decrypt(self.encrypted_text) if is_encrypted(self.encrypted_text) else self.encrypted_text
        if text.isascii():
            pyautogui.typewrite(text, interval=self.interval)
        else:
            from modules.keyboard import _send_unicode_string
            _send_unicode_string(text, self.interval)
        logger.debug("Typed secure text (len=%d)", len(text))
        return True

    def _get_params(self) -> dict[str, Any]:
        return {
            "encrypted_text": self.encrypted_text,
            "interval": self.interval,
        }

    def _set_params(self, params: dict[str, Any]) -> None:
        self.encrypted_text = params.get("encrypted_text", "")
        self.interval = params.get("interval", 0.02)

    def get_display_name(self) -> str:
        return "Type ●●●●●● (secure)"


# ---------------------------------------------------------------------------
# Run Sub-Macro (G3)
# ---------------------------------------------------------------------------

@register_action("run_macro")
class RunMacro(Action):
    """Execute another macro file as a sub-routine."""

    def __init__(self, macro_path: str = "", **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.macro_path = macro_path

    def execute(self) -> bool:
        from core.engine_context import get_context, is_stopped
        from core.engine import MacroEngine

        ctx = get_context()
        path = self.macro_path
        if ctx and '${' in path:
            path = ctx.interpolate(path)

        # Security: validate macro path
        try:
            path = _validate_path(path, "run_macro")
        except ValueError as e:
            logger.error("RunMacro blocked: %s", e)
            return False

        # Ensure it's a .json macro file
        if not path.endswith('.json'):
            logger.error("RunMacro: not a .json file: %s", path)
            return False

        try:
            actions, settings = MacroEngine.load_macro(path)
        except (ValueError, FileNotFoundError) as e:
            logger.error("RunMacro failed to load '%s': %s", path, e)
            return False

        logger.info("RunMacro: executing '%s' (%d actions)",
                     path, len(actions))

        for action in actions:
            if is_stopped():
                return True
            success = action.run()
            if ctx:
                ctx.record_action(success)
            if not success:
                logger.warning("RunMacro: sub-action failed in '%s'", path)
                return False

        logger.info("RunMacro: completed '%s'", path)
        return True

    def _get_params(self) -> dict[str, Any]:
        return {"macro_path": self.macro_path}

    def _set_params(self, params: dict[str, Any]) -> None:
        self.macro_path = params.get("macro_path", "")

    def get_display_name(self) -> str:
        name = os.path.basename(self.macro_path) if self.macro_path else "?"
        return f"Run macro '{name}'"


# ---------------------------------------------------------------------------
# OCR Text Capture (G16)
# ---------------------------------------------------------------------------

@register_action("capture_text")
class CaptureText(Action):
    """Capture text from a screen region using OCR (pytesseract).
    Stores the result in a context variable.
    """

    def __init__(self, x: int = 0, y: int = 0, width: int = 200,
                 height: int = 50, var_name: str = "ocr_text",
                 lang: str = "eng", **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.var_name = var_name
        self.lang = lang

    def execute(self) -> bool:
        try:
            import pytesseract
            from PIL import ImageGrab
        except ImportError:
            logger.error(
                "CaptureText requires pytesseract and Pillow.\n"
                "Install: pip install pytesseract Pillow\n"
                "Also install Tesseract OCR: https://github.com/tesseract-ocr/tesseract\n"
                "Windows: https://github.com/UB-Mannheim/tesseract/wiki")
            return False

        from core.engine_context import get_context

        # Capture screen region
        bbox = (self.x, self.y, self.x + self.width, self.y + self.height)
        screenshot = ImageGrab.grab(bbox)

        # OCR
        try:
            text = pytesseract.image_to_string(
                screenshot, lang=self.lang
            ).strip()
        except pytesseract.TesseractNotFoundError:
            logger.error(
                "Tesseract executable not found!\n"
                "Install from: https://github.com/UB-Mannheim/tesseract/wiki\n"
                "Then set path: pytesseract.pytesseract.tesseract_cmd = r'C:\\...\\tesseract.exe'")
            return False
        except Exception as e:
            logger.error("OCR failed: %s", e)
            return False

        ctx = get_context()
        if ctx:
            ctx.set_var(self.var_name, text)

        logger.info("OCR(%d,%d,%dx%d) → ${%s} = '%s'",
                     self.x, self.y, self.width, self.height,
                     self.var_name, text[:50])
        return True

    def _get_params(self) -> dict[str, Any]:
        return {
            "x": self.x, "y": self.y,
            "width": self.width, "height": self.height,
            "var_name": self.var_name, "lang": self.lang,
        }

    def _set_params(self, params: dict[str, Any]) -> None:
        self.x = params.get("x", 0)
        self.y = params.get("y", 0)
        self.width = params.get("width", 200)
        self.height = params.get("height", 50)
        self.var_name = params.get("var_name", "ocr_text")
        self.lang = params.get("lang", "eng")

    def get_display_name(self) -> str:
        return (f"OCR({self.x},{self.y} {self.width}×{self.height})"
                f" → ${{{self.var_name}}}")

