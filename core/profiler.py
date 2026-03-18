"""
Performance Profiler – Lightweight operation timing tracker.

Usage:
    from core.profiler import get_profiler

    profiler = get_profiler()
    with profiler.track("template_match"):
        # ... do work ...

    print(profiler.report())
"""

import logging
import threading
import time
from contextlib import contextmanager
from collections.abc import Generator
from dataclasses import dataclass

logger = logging.getLogger("Profiler")


@dataclass
class TimingStats:
    """Statistics for a timed operation."""

    name: str
    count: int = 0
    total_ms: float = 0.0
    min_ms: float = float("inf")
    max_ms: float = 0.0

    @property
    def avg_ms(self) -> float:
        return self.total_ms / self.count if self.count > 0 else 0.0

    def record(self, ms: float) -> None:
        self.count += 1
        self.total_ms += ms
        self.min_ms = min(self.min_ms, ms)
        self.max_ms = max(self.max_ms, ms)

    def __str__(self) -> str:
        return (
            f"{self.name}: n={self.count}, "
            f"avg={self.avg_ms:.2f}ms, "
            f"min={self.min_ms:.2f}ms, "
            f"max={self.max_ms:.2f}ms"
        )


class PerformanceProfiler:
    """
    Simple operation timer with contextmanager tracking.

    Thread-safe: uses lock for dict mutations.
    """

    def __init__(self) -> None:
        self._stats: dict[str, TimingStats] = {}
        self._lock = threading.Lock()
        self._enabled = True

    def enable(self) -> None:
        self._enabled = True

    def disable(self) -> None:
        self._enabled = False

    @contextmanager
    def track(self, name: str) -> Generator[None, None, None]:
        """Track execution time of a code block."""
        if not self._enabled:
            yield
            return

        start = time.perf_counter()
        try:
            yield
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000
            with self._lock:
                if name not in self._stats:
                    self._stats[name] = TimingStats(name)
                self._stats[name].record(elapsed_ms)

    def get_stats(self, name: str) -> TimingStats | None:
        with self._lock:
            return self._stats.get(name)

    def reset(self) -> None:
        with self._lock:
            self._stats.clear()

    def report(self) -> str:
        """Generate text report of all operation timings."""
        with self._lock:
            if not self._stats:
                return "No profiling data."
            lines = ["Performance Report", "=" * 50]
            for name in sorted(self._stats.keys()):
                lines.append(str(self._stats[name]))
        return "\n".join(lines)

    def log_report(self) -> None:
        logger.info("\n%s", self.report())


# Thread-safe global singleton
_profiler: PerformanceProfiler | None = None
_profiler_lock = threading.Lock()


def get_profiler() -> PerformanceProfiler:
    global _profiler
    if _profiler is None:
        with _profiler_lock:
            if _profiler is None:
                _profiler = PerformanceProfiler()
    return _profiler
