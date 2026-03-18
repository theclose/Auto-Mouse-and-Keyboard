"""
Thread-local execution context for the macro engine.

Provides speed factor control without modifying Action signatures.
Engine sets the speed factor before running; Action.run() and
DelayAction.execute() read it via scaled_sleep().
"""

import threading
import time

_ctx = threading.local()


def set_speed(factor: float) -> None:
    """Set playback speed for the current thread (0.1 – 10.0)."""
    _ctx.speed_factor = max(0.1, min(10.0, factor))


def get_speed() -> float:
    """Get current speed factor (default 1.0)."""
    return getattr(_ctx, 'speed_factor', 1.0)


def scaled_sleep(seconds: float) -> None:
    """Sleep adjusted by the current thread's speed factor."""
    actual = seconds / get_speed()
    if actual > 0.001:  # skip negligible sleeps
        time.sleep(actual)
