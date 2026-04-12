"""
Memory Manager – Background RAM monitoring and cleanup for 24/7 operation.

Inspired by RetroAuto's MemoryManager. Lightweight singleton that:
- Monitors process memory every 30 seconds
- Triggers gc.collect() when threshold exceeded (200MB default)
- Coordinates cache cleanup via registered callbacks
- Logs memory stats for debugging
"""

import ctypes
import ctypes.wintypes as wintypes
import gc
import logging
import threading
import time
from collections.abc import Callable
from typing import Any

logger = logging.getLogger("MemoryManager")


# ---------------------------------------------------------------------------
# Module-level ctypes constants (created once, not every 30s)
# ---------------------------------------------------------------------------
class _PROCESS_MEMORY_COUNTERS(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("PageFaultCount", wintypes.DWORD),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
    ]


_PMC_SIZE = ctypes.sizeof(_PROCESS_MEMORY_COUNTERS)
_kernel32 = ctypes.windll.kernel32

# Cache K32GetProcessMemoryInfo function pointer
try:
    _k32_get_process_memory_info = _kernel32.K32GetProcessMemoryInfo
    _k32_get_process_memory_info.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(_PROCESS_MEMORY_COUNTERS),
        wintypes.DWORD,
    ]
    _k32_get_process_memory_info.restype = wintypes.BOOL
except (OSError, AttributeError):
    # Fallback to psapi
    _psapi = ctypes.WinDLL("psapi", use_last_error=True)
    _k32_get_process_memory_info = _psapi.GetProcessMemoryInfo
    _k32_get_process_memory_info.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(_PROCESS_MEMORY_COUNTERS),
        wintypes.DWORD,
    ]
    _k32_get_process_memory_info.restype = wintypes.BOOL


class MemoryManager:
    """
    Singleton memory manager for long-running automation.

    Usage:
        mm = MemoryManager.instance()
        mm.register_cleanup(my_cache.clear)
        mm.start()
    """

    _instance = None
    _lock = threading.Lock()

    @classmethod
    def instance(cls) -> "MemoryManager":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def __init__(
        self,
        threshold_mb: int = 200,
        check_interval_s: int = 30,
    ) -> None:
        self._threshold_bytes = threshold_mb * 1024 * 1024
        self._check_interval = check_interval_s
        self._running = False
        self._thread: threading.Thread | None = None
        self._cleanup_callbacks: list[Callable[[], None]] = []
        self._cleanup_count = 0
        self._peak_bytes = 0
        self._baseline_bytes = 0

    def set_threshold(self, threshold_mb: int) -> None:
        """Update the memory threshold (can be called before start)."""
        self._threshold_bytes = max(50, threshold_mb) * 1024 * 1024

    def register_cleanup(self, callback: Callable[[], None]) -> None:
        """Register a function to call during memory cleanup."""
        self._cleanup_callbacks.append(callback)

    def start(self) -> None:
        """Start background monitoring with adaptive threshold."""
        if self._running:
            return

        # P2: Measure baseline RAM and auto-adjust if threshold too low
        self._baseline_bytes = self._get_memory()
        _MB = 1024 * 1024
        margin = 20 * _MB  # 20MB headroom
        if self._threshold_bytes <= self._baseline_bytes + margin:
            old_mb = self._threshold_bytes // _MB
            self._threshold_bytes = self._baseline_bytes + 150 * _MB
            logger.info(
                "Adaptive threshold: %dMB → %dMB (baseline=%dMB + 150MB margin)",
                old_mb,
                self._threshold_bytes // _MB,
                self._baseline_bytes // _MB,
            )

        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True, name="MemoryManager")
        self._thread.start()
        logger.info(
            "Started (threshold=%dMB, interval=%ds)",
            self._threshold_bytes // (1024 * 1024),
            self._check_interval,
        )

    def stop(self) -> None:
        """Stop background monitoring."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None
        logger.info("Stopped (cleanups=%d)", self._cleanup_count)

    def _monitor_loop(self) -> None:
        interval = self._check_interval
        while self._running:
            try:
                mem = self._get_memory()
                if mem > self._peak_bytes:
                    self._peak_bytes = mem
                if mem > self._threshold_bytes:
                    logger.warning(
                        "Threshold exceeded: %.1fMB > %dMB",
                        mem / (1024 * 1024),
                        self._threshold_bytes // (1024 * 1024),
                    )
                    self._do_cleanup()
                    interval = max(15, self._check_interval // 2)
                else:
                    interval = self._check_interval
            except (OSError, ctypes.ArgumentError, MemoryError) as e:
                logger.error("Monitor error: %s", e)
            time.sleep(interval)

    def _get_memory(self) -> int:
        """Get current process RSS (WorkingSetSize) in bytes."""
        try:
            handle = _kernel32.GetCurrentProcess()
            counters = _PROCESS_MEMORY_COUNTERS()
            counters.cb = _PMC_SIZE
            if _k32_get_process_memory_info(handle, ctypes.byref(counters), counters.cb):
                return int(counters.WorkingSetSize)
            return 0
        except (OSError, ctypes.ArgumentError):
            return 0

    def _do_cleanup(self) -> None:
        """Run cleanup callbacks then force GC."""
        before = self._get_memory()
        for cb in self._cleanup_callbacks:
            try:
                cb()
            except Exception as e:
                logger.warning("Cleanup callback error: %s", e)
        gc.collect()
        after = self._get_memory()
        self._cleanup_count += 1
        freed = before - after
        logger.info(
            "Cleanup #%d: freed %.1fMB (%.1f→%.1fMB)",
            self._cleanup_count,
            freed / (1024 * 1024),
            before / (1024 * 1024),
            after / (1024 * 1024),
        )

    def get_stats(self) -> dict[str, Any]:
        """Current memory and performance statistics."""
        current = self._get_memory()
        stats = {
            "current_mb": round(current / (1024 * 1024), 1),
            "peak_mb": round(self._peak_bytes / (1024 * 1024), 1),
            "baseline_mb": round(self._baseline_bytes / (1024 * 1024), 1),
            "threshold_mb": self._threshold_bytes // (1024 * 1024),
            "cleanup_count": self._cleanup_count,
        }
        # Merge ImageFinder perf stats if available
        try:
            from modules.image import ImageFinder
            stats.update(ImageFinder.get_perf_stats())
        except Exception:
            pass
        return stats

    def force_gc(self) -> None:
        """Manual garbage collection trigger."""
        self._do_cleanup()
