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
            # Partial match: enumerate all windows
            hwnd = self._find_by_partial(title)

        if not hwnd:
            logger.warning("Window not found: '%s'", title)
            return False

        # Restore if minimized
        if _user32.IsIconic(hwnd):
            _user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        _user32.SetForegroundWindow(hwnd)
        time.sleep(0.1)  # Small delay for window switch
        logger.info("Activated window: '%s' (hwnd=%d)", title, hwnd)
        return True

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
        with open(self.file_path, "a", encoding="utf-8") as f:
            f.write(line)
        logger.info("Logged: %s", msg[:80])
        return True

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
    """Read a specific line from a file into a variable."""

    def __init__(self, file_path: str = "", line_number: str = "1",
                 var_name: str = "line", **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.file_path = file_path
        self.line_number = line_number  # Can be ${var} for dynamic
        self.var_name = var_name

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

        try:
            with open(path, "r", encoding="utf-8") as f:
                lines = f.readlines()
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
        except (OSError, IOError) as e:
            logger.error("Cannot read file: %s", e)
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

        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
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
