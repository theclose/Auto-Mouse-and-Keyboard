"""
Execution Context — shared state between actions during a macro run.

Provides result chaining, variables, and smart ROI history
so actions can communicate with each other.
"""

import logging
import re
import threading
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)

_VAR_PATTERN = re.compile(r"\$\{(\w+)\}")


class ExecutionContext:
    """Thread-safe shared context for a single macro execution."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._variables: dict[str, Any] = {}
        self._last_image_match: Optional[tuple[str, tuple[int, int, int, int]]] = None
        self._last_pixel_color: Optional[tuple[int, int, int, int, int]] = None
        self._roi_history: dict[str, list[tuple[int, int, int, int]]] = {}
        self.iteration_count: int = 0
        self.action_count: int = 0
        self.error_count: int = 0
        self.start_time: float = 0.0
        # ROI cache fields (C3: initialized here, accessed under lock)
        self._roi_cache_key: str | None = None
        self._roi_cache_val: Optional[tuple[int, int, int, int]] = None
        self._roi_cache_time: float = 0.0

    # -- Variables -----------------------------------------------------------
    def set_var(self, name: str, value: Any) -> None:
        with self._lock:
            self._variables[name] = value

    def get_var(self, name: str, default: Any = None) -> Any:
        with self._lock:
            return self._variables.get(name, default)

    def get_all_vars(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._variables)

    # -- Image result chaining -----------------------------------------------
    def set_image_match(self, template_path: str, bbox: tuple[int, int, int, int]) -> None:
        """Store last successful image match result."""
        with self._lock:
            self._last_image_match = (template_path, bbox)
            # Update ROI history for smart search
            if template_path not in self._roi_history:
                self._roi_history[template_path] = []
            history = self._roi_history[template_path]
            history.append(bbox)
            if len(history) > 10:
                history.pop(0)

    def get_image_match(self, template_path: str = "") -> Optional[tuple[int, int, int, int]]:
        """Get last image match bbox. If template_path given, only if it matches."""
        with self._lock:
            if self._last_image_match is None:
                return None
            path, bbox = self._last_image_match
            if template_path and path != template_path:
                return None
            return bbox

    def get_image_center(self, template_path: str = "") -> Optional[tuple[int, int]]:
        """Get center (cx, cy) of last image match."""
        bbox = self.get_image_match(template_path)
        if bbox is None:
            return None
        x, y, w, h = bbox
        return x + w // 2, y + h // 2

    # -- Smart ROI -----------------------------------------------------------
    def suggest_roi(self, template_path: str, margin: int = 150) -> Optional[tuple[int, int, int, int]]:
        """Suggest a search region based on where this template was found before."""
        with self._lock:
            history = self._roi_history.get(template_path)
            if not history or len(history) < 2:
                return None  # Not enough data
            # Average position from last 5 finds
            recent = history[-5:]
            avg_x = sum(b[0] for b in recent) // len(recent)
            avg_y = sum(b[1] for b in recent) // len(recent)
            avg_w = sum(b[2] for b in recent) // len(recent)
            avg_h = sum(b[3] for b in recent) // len(recent)
            # Expand by margin
            roi_x = max(0, avg_x - margin)
            roi_y = max(0, avg_y - margin)
            roi_w = avg_w + margin * 2
            roi_h = avg_h + margin * 2
            return (roi_x, roi_y, roi_w, roi_h)

    def suggest_roi_cached(self, template_path: str, margin: int = 150) -> Optional[tuple[int, int, int, int]]:
        """Cached version — uses last result if template hasn't changed.
        P1-5: TTL of 300s (5 min) to prevent stale ROI in long-running macros.
        """
        with self._lock:
            cached_key = self._roi_cache_key
            cached_val = self._roi_cache_val
            cached_time = self._roi_cache_time
        if (
            cached_key == template_path and cached_val is not None and (time.perf_counter() - cached_time) < 300
        ):  # 5 min TTL
            return cached_val
        result = self.suggest_roi(template_path, margin)
        with self._lock:
            self._roi_cache_key = template_path
            self._roi_cache_val = result
            self._roi_cache_time = time.perf_counter()
        return result

    # -- Pixel result --------------------------------------------------------
    def set_pixel_color(self, x: int, y: int, r: int, g: int, b: int) -> None:
        with self._lock:
            self._last_pixel_color = (x, y, r, g, b)

    def get_pixel_color(self) -> Optional[tuple[int, int, int, int, int]]:
        with self._lock:
            return self._last_pixel_color

    # -- Stats ---------------------------------------------------------------
    def record_action(self, success: bool) -> None:
        with self._lock:
            self.action_count += 1
            if not success:
                self.error_count += 1

    def get_elapsed_seconds(self) -> float:
        if self.start_time:
            return time.perf_counter() - self.start_time
        return 0.0

    # -- Reset ---------------------------------------------------------------
    def reset(self) -> None:
        with self._lock:
            self._variables.clear()
            self._last_image_match = None
            self._last_pixel_color = None
            self._roi_history.clear()
            self.iteration_count = 0
            self.action_count = 0
            self.error_count = 0
            self.start_time = time.perf_counter()
            self._roi_cache_key = None
            self._roi_cache_val = None
            self._roi_cache_time = 0.0

    # -- Checkpoint / Resume (1.1) -------------------------------------------
    def snapshot(self) -> dict:
        """Capture full context state for checkpoint/resume."""
        from core.engine_context import get_speed

        with self._lock:
            return {
                "variables": dict(self._variables),
                "iteration_count": self.iteration_count,
                "action_count": self.action_count,
                "error_count": self.error_count,
                "last_image_match": self._last_image_match,
                "last_pixel_color": self._last_pixel_color,
                "speed_factor": get_speed(),  # P2-1
            }

    def restore(self, snapshot: dict) -> None:
        """Restore context state from a checkpoint."""
        with self._lock:
            self._variables = dict(snapshot.get("variables", {}))
            self._last_image_match = snapshot.get("last_image_match")
            self._last_pixel_color = snapshot.get("last_pixel_color")
        self.iteration_count = snapshot.get("iteration_count", 0)
        self.action_count = snapshot.get("action_count", 0)
        self.error_count = snapshot.get("error_count", 0)
        # P2-1: Restore speed factor
        if "speed_factor" in snapshot:
            from core.engine_context import set_speed

            set_speed(snapshot["speed_factor"])
        logger.info("Context restored from checkpoint (vars=%d, iter=%d)", len(self._variables), self.iteration_count)

    # -- Template interpolation ----------------------------------------------
    def interpolate(self, text: str) -> str:
        """Replace ${var_name} patterns with variable values.

        Built-in system vars: __timestamp__, __iteration__, __action_count__,
        __error_count__, __last_img_x__, __last_img_y__
        """

        def _replace(m: re.Match) -> str:
            name = m.group(1)
            # System variables (computed on demand)
            if name == "__timestamp__":
                return str(int(time.time()))
            elif name == "__iteration__":
                return str(self.iteration_count)
            elif name == "__action_count__":
                return str(self.action_count)
            elif name == "__error_count__":
                return str(self.error_count)
            elif name == "__last_img_x__":
                c = self.get_image_center()
                return str(c[0]) if c else "0"
            elif name == "__last_img_y__":
                c = self.get_image_center()
                return str(c[1]) if c else "0"
            # User variables
            val = self.get_var(name)
            return str(val) if val is not None else m.group(0)

        return _VAR_PATTERN.sub(_replace, text)
