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

_VAR_PATTERN = re.compile(r'\$\{(\w+)\}')


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
    def set_image_match(self, template_path: str,
                        bbox: tuple[int, int, int, int]) -> None:
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

    def get_image_match(self, template_path: str = ""
                        ) -> Optional[tuple[int, int, int, int]]:
        """Get last image match bbox. If template_path given, only if it matches."""
        with self._lock:
            if self._last_image_match is None:
                return None
            path, bbox = self._last_image_match
            if template_path and path != template_path:
                return None
            return bbox

    def get_image_center(self, template_path: str = ""
                         ) -> Optional[tuple[int, int]]:
        """Get center (cx, cy) of last image match."""
        bbox = self.get_image_match(template_path)
        if bbox is None:
            return None
        x, y, w, h = bbox
        return x + w // 2, y + h // 2

    # -- Smart ROI -----------------------------------------------------------
    def suggest_roi(self, template_path: str,
                    margin: int = 150) -> Optional[tuple[int, int, int, int]]:
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

    def suggest_roi_cached(self, template_path: str,
                           margin: int = 150) -> Optional[tuple[int, int, int, int]]:
        """Cached version — uses last result if template hasn't changed."""
        cached_key = getattr(self, '_roi_cache_key', None)
        cached_val = getattr(self, '_roi_cache_val', None)
        if cached_key == template_path and cached_val is not None:
            return cached_val
        result = self.suggest_roi(template_path, margin)
        self._roi_cache_key = template_path
        self._roi_cache_val = result
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

    # -- Template interpolation ----------------------------------------------
    def interpolate(self, text: str) -> str:
        """Replace ${var_name} patterns with variable values."""
        def _replace(m: re.Match) -> str:
            name = m.group(1)
            val = self.get_var(name)
            return str(val) if val is not None else m.group(0)
        return _VAR_PATTERN.sub(_replace, text)

