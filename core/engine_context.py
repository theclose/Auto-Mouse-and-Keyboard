"""
Thread-local execution context for the macro engine.

Provides speed factor and stop event without modifying Action signatures.
Engine sets speed/stop_event before running; Action.run() and
DelayAction.execute() read via scaled_sleep() which auto-checks stop.
"""

import threading
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.execution_context import ExecutionContext

_ctx = threading.local()


def set_speed(factor: float) -> None:
    """Set playback speed for the current thread (0.1 – 10.0)."""
    _ctx.speed_factor = max(0.1, min(10.0, factor))


def get_speed() -> float:
    """Get current speed factor (default 1.0)."""
    return getattr(_ctx, 'speed_factor', 1.0)


def set_stop_event(event: threading.Event) -> None:
    """Set the stop event for the current thread."""
    _ctx.stop_event = event


def get_stop_event() -> threading.Event | None:
    """Get the stop event (None if not set)."""
    return getattr(_ctx, 'stop_event', None)


def is_stopped() -> bool:
    """Check if engine has requested stop."""
    ev = get_stop_event()
    return ev is not None and ev.is_set()


def set_context(ctx: 'ExecutionContext') -> None:
    """Set execution context for the current thread."""
    _ctx.exec_context = ctx


def get_context() -> 'ExecutionContext | None':
    """Get execution context (None if not set)."""
    return getattr(_ctx, 'exec_context', None)


def scaled_sleep(seconds: float) -> None:
    """Sleep in 50ms chunks, checking stop event between chunks."""
    actual = seconds / get_speed()
    if actual <= 0.001:
        return
    end = time.perf_counter() + actual
    while time.perf_counter() < end:
        ev = get_stop_event()
        if ev is not None and ev.is_set():
            return  # Interrupted by stop
        time.sleep(min(0.05, end - time.perf_counter()))


# -- v3.0: nested step callback for composite actions ----------------------
def set_nested_callback(fn) -> None:
    """Set callback for nested action progress (called by MacroEngine.run)."""
    _ctx.nested_callback = fn


def emit_nested_step(path: list[int], display_name: str) -> None:
    """Called by composite actions to signal child execution.

    Args:
        path: Index path, e.g. [2, 0] = parent action #2 → child #0
        display_name: Human-readable name of the child action
    """
    fn = getattr(_ctx, 'nested_callback', None)
    if fn is not None:
        fn(path, display_name)
