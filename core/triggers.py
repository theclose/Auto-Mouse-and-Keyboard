"""
Trigger types for automated macro execution.

Each trigger evaluates a condition and returns True when the macro should fire.
"""

import ctypes
import ctypes.wintypes
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class TriggerConfig:
    """Configuration for a single trigger."""

    id: str = ""
    trigger_type: str = ""  # "schedule" | "window_focus"
    enabled: bool = True
    macro_file: str = ""  # Path to .json macro file
    cooldown_ms: int = 5000
    params: dict[str, Any] = field(default_factory=dict)
    # Runtime state (not serialized)
    _last_fired: float = field(default=0.0, repr=False)


# ---------------------------------------------------------------------------
# Schedule Trigger
# ---------------------------------------------------------------------------
class ScheduleTrigger:
    """Fires at interval, daily time, or weekday schedule.

    Modes:
        interval — every N minutes
        daily    — once per day at HH:MM
        weekday  — on specified weekdays at HH:MM

    Params:
        mode: str — "interval" | "daily" | "weekday"
        interval_min: int — minutes between fires (interval mode)
        time: str — "HH:MM" (daily/weekday mode)
        weekdays: list[int] — 0=Mon..6=Sun (weekday mode)
    """

    @staticmethod
    def should_fire(config: TriggerConfig) -> bool:
        """Check if schedule condition is met."""
        params = config.params
        mode = params.get("mode", "interval")
        now = datetime.now()

        if mode == "interval":
            interval_min = params.get("interval_min", 5)
            elapsed = time.time() - config._last_fired
            return elapsed >= interval_min * 60

        if mode == "daily":
            target_time = params.get("time", "08:00")
            return _time_matches(now, target_time, config._last_fired)

        if mode == "weekday":
            target_time = params.get("time", "08:00")
            weekdays = params.get("weekdays", [0, 1, 2, 3, 4])  # Mon-Fri
            if now.weekday() not in weekdays:
                return False
            return _time_matches(now, target_time, config._last_fired)

        return False


def _time_matches(now: datetime, target: str, last_fired: float) -> bool:
    """Check if current time matches HH:MM and hasn't fired today."""
    try:
        hour, minute = map(int, target.split(":"))
    except (ValueError, AttributeError):
        return False
    if now.hour == hour and now.minute == minute:
        # Only fire once per minute window
        if time.time() - last_fired > 90:
            return True
    return False


# ---------------------------------------------------------------------------
# Window Focus Trigger
# ---------------------------------------------------------------------------
class WindowFocusTrigger:
    """Fires when target window becomes the foreground window.

    Params:
        match_type: str — "process" | "title_contains" | "title_regex"
        match_value: str — process name or title pattern
    """

    # Track previous state to detect transitions (fire on first match only)
    _was_matched: dict[str, bool] = {}

    @classmethod
    def should_fire(cls, config: TriggerConfig) -> bool:
        """Check if foreground window matches trigger condition."""
        params = config.params
        match_type = params.get("match_type", "title_contains")
        match_value = params.get("match_value", "")
        if not match_value:
            return False

        title, process = get_foreground_window_info()

        matched = False
        if match_type == "process":
            matched = match_value.lower() in process.lower()
        elif match_type == "title_contains":
            matched = match_value.lower() in title.lower()
        elif match_type == "title_regex":
            try:
                matched = bool(re.search(match_value, title, re.IGNORECASE))
            except re.error:
                matched = False

        # Detect rising edge: only fire when transitioning from not-matched → matched
        was = cls._was_matched.get(config.id, False)
        cls._was_matched[config.id] = matched

        if matched and not was:
            return True
        return False

    @classmethod
    def reset(cls) -> None:
        """Reset all edge-detection state."""
        cls._was_matched.clear()


# ---------------------------------------------------------------------------
# Win32 helpers
# ---------------------------------------------------------------------------
def get_foreground_window_info() -> tuple[str, str]:
    """Get (window_title, process_name) of foreground window. Win32 only."""
    try:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return ("", "")

        # Window title
        length = user32.GetWindowTextLengthW(hwnd) + 1
        buf = ctypes.create_unicode_buffer(length)
        user32.GetWindowTextW(hwnd, buf, length)
        title = buf.value

        # Process name
        pid = ctypes.wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
        process_name = ""
        if handle:
            try:
                exe_buf = ctypes.create_unicode_buffer(260)
                exe_size = ctypes.wintypes.DWORD(260)
                kernel32.QueryFullProcessImageNameW(handle, 0, exe_buf, ctypes.byref(exe_size))
                # Extract just the filename
                full_path = exe_buf.value
                process_name = full_path.rsplit("\\", 1)[-1] if full_path else ""
            finally:
                kernel32.CloseHandle(handle)

        return (title, process_name)
    except Exception:
        logger.debug("Failed to get foreground window info", exc_info=True)
        return ("", "")
