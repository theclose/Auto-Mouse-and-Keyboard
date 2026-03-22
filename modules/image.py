"""
Image recognition module using OpenCV template matching.
Provides ImageFinder for locating images on screen and
action wrappers for use in macros.
"""

import logging
import os
import threading
import time
from pathlib import Path
from typing import Any, Optional

import cv2
import numpy as np

from core.action import Action, register_action
from modules.screen import (
    capture_full_screen, capture_full_screen_gray, capture_region,
    capture_region_gray, save_screenshot,
)

logger = logging.getLogger(__name__)


class ImageFinder:
    """
    Finds a template image on the screen using OpenCV matchTemplate.

    Features:
    - Confidence threshold (0.0 – 1.0)
    - Region of interest (ROI) for faster searches
    - Multi-scale matching (optional)
    - Timeout with retry
    """

    # --- Screen cache for rapid sequential calls (50ms TTL) ---
    _cache: dict[str, tuple[float, Any]] = {}
    _cache_lock = threading.Lock()
    _CACHE_TTL = 0.050  # 50 milliseconds

    @classmethod
    def _get_cached_screen(
        cls,
        region: Optional[tuple[int, int, int, int]],
        grayscale: bool,
    ) -> Any:
        """Return cached screen if < 50ms old, else capture fresh."""
        key = f"{region},{grayscale}"
        now = time.perf_counter()
        with cls._cache_lock:
            if key in cls._cache:
                ts, img = cls._cache[key]
                if (now - ts) < cls._CACHE_TTL:
                    return img

        # Capture fresh — use direct grayscale path when possible
        if region:
            if grayscale:
                screen = capture_region_gray(*region)
            else:
                screen: Any = capture_region(*region)
        elif grayscale:
            screen = capture_full_screen_gray()  # BGRA→GRAY direct
        else:
            screen = capture_full_screen()

        with cls._cache_lock:
            if len(cls._cache) > 8:
                cls._cache.clear()
            cls._cache[key] = (now, screen)
        return screen

    @classmethod
    def clear_cache(cls) -> None:
        """Clear screen cache AND template cache (called by MemoryManager)."""
        with cls._cache_lock:
            cls._cache.clear()
        with cls._tpl_lock:
            cls._tpl_cache.clear()

    # --- Template image cache (disk I/O → RAM, mtime invalidation) ---
    _tpl_cache: dict[str, tuple[float, Any]] = {}
    _tpl_lock = threading.Lock()

    @classmethod
    def _load_template(cls, path: str, grayscale: bool) -> Any:
        """Load template from cache or disk. Invalidate on file modification."""
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            return None
        key = f"{path}:{grayscale}"
        with cls._tpl_lock:
            if key in cls._tpl_cache:
                cached_mtime, img = cls._tpl_cache[key]
                if cached_mtime == mtime:
                    return img  # Cache hit
        # Cache miss — read from disk
        img = cv2.imread(path)
        if img is None or img.size == 0:
            return None
        if grayscale:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        with cls._tpl_lock:
            if len(cls._tpl_cache) > 100:
                cls._tpl_cache.clear()  # Prevent unbounded growth
            cls._tpl_cache[key] = (mtime, img)
        return img

    def __init__(self, method: int = cv2.TM_CCOEFF_NORMED) -> None:
        self.method = method

    def find_on_screen(
        self,
        template_path: str,
        confidence: float = 0.8,
        region: Optional[tuple[int, int, int, int]] = None,
        timeout_ms: int = 0,
        grayscale: bool = True,
    ) -> Optional[tuple[int, int, int, int]]:
        """
        Search for a template image on the screen.

        Parameters
        ----------
        template_path : path to the template image file
        confidence    : minimum match confidence (0.0 – 1.0)
        region        : (x, y, w, h) to limit search area, or None
        timeout_ms    : 0 = single try, >0 = retry until found or timeout
        grayscale     : convert to grayscale for faster matching

        Returns
        -------
        (x, y, w, h) bounding box of the best match, or None if not found.
        """
        template = self._load_template(template_path, grayscale)
        if template is None:
            logger.error("Cannot read template image: %s", template_path)
            return None

        deadline = time.perf_counter() + (timeout_ms / 1000.0) \
            if timeout_ms > 0 else 0
        poll_interval = 0.1
        consecutive_misses = 0

        while True:
            screen = self._get_cached_screen(region, grayscale)
            result = self._match_template(screen, template, confidence, region)
            if result is not None:
                return result

            if timeout_ms <= 0 or time.perf_counter() >= deadline:
                break

            consecutive_misses += 1
            poll_interval = (min(poll_interval * 1.5, 0.5)
                             if consecutive_misses > 5 else 0.1)
            time.sleep(poll_interval)

        logger.debug("Image not found: %s (conf < %.3f)",
                     template_path, confidence)
        return None

    def _match_template(
        self,
        screen: Any,
        template: Any,
        confidence: float,
        region: Optional[tuple[int, int, int, int]],
    ) -> Optional[tuple[int, int, int, int]]:
        """Try single-scale then multi-scale matching."""
        t_h, t_w = template.shape[:2]

        # Single-scale match
        result = cv2.matchTemplate(screen, template, self.method)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)
        if max_val >= confidence:
            x, y = max_loc
            if region:
                x += region[0]
                y += region[1]
            logger.debug("Image found at (%d,%d) conf=%.3f", x, y, max_val)
            return (x, y, t_w, t_h)

        # Multi-scale only if "close" (>50% threshold) — skip obvious misses
        if max_val > confidence * 0.5:
            return self._match_multi_scale(
                screen, template, confidence, region, max_val,
                (max_loc[0], max_loc[1]))
        return None

    def _match_multi_scale(
        self,
        screen: Any,
        template: Any,
        confidence: float,
        region: Optional[tuple[int, int, int, int]],
        best_val: float,
        best_loc: tuple[int, int],
    ) -> Optional[tuple[int, int, int, int]]:
        """Try matching at multiple scales for DPI awareness."""
        t_h, t_w = template.shape[:2]
        best_scale = 1.0

        for scale in (0.75, 0.85, 1.15, 1.25):
            sw = max(1, int(t_w * scale))
            sh = max(1, int(t_h * scale))
            if sw >= screen.shape[1] or sh >= screen.shape[0]:
                continue
            scaled_t = cv2.resize(template, (sw, sh),
                                  interpolation=cv2.INTER_AREA)
            res = cv2.matchTemplate(screen, scaled_t, self.method)
            _, mv, _, ml = cv2.minMaxLoc(res)
            if mv > best_val:
                best_val, best_loc, best_scale = mv, (ml[0], ml[1]), scale

        if best_val >= confidence:
            x, y = best_loc
            sw = int(t_w * best_scale)
            sh = int(t_h * best_scale)
            if region:
                x += region[0]
                y += region[1]
            logger.debug("Image found (scale=%.2f) at (%d,%d) conf=%.3f",
                         best_scale, x, y, best_val)
            return (x, y, sw, sh)
        return None

    def find_all_on_screen(
        self,
        template_path: str,
        confidence: float = 0.8,
        region: Optional[tuple[int, int, int, int]] = None,
        grayscale: bool = True,
    ) -> list[tuple[int, int, int, int]]:
        """Find ALL occurrences of a template on screen."""
        template = self._load_template(template_path, grayscale)
        if template is None:
            return []

        t_h, t_w = template.shape[:2]
        screen: Any = capture_region(*region) if region else capture_full_screen()
        if grayscale:
            screen = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY)

        result = cv2.matchTemplate(screen, template, self.method)
        locations = np.where(result >= confidence)

        boxes = []
        for pt in zip(*locations[::-1]):
            x, y = pt
            if region:
                x += region[0]
                y += region[1]
            boxes.append((x, y, t_w, t_h))

        # Remove overlapping boxes (non-max suppression simplified)
        boxes = _nms(boxes, t_w, t_h)
        logger.debug("Found %d instances of %s", len(boxes), template_path)
        return boxes

    def get_center(
        self, bbox: tuple[int, int, int, int]
    ) -> tuple[int, int]:
        """Return the center (x, y) of a bounding box."""
        x, y, w, h = bbox
        return x + w // 2, y + h // 2


# Module-level singleton
_finder_instance: Optional[ImageFinder] = None


def get_image_finder() -> ImageFinder:
    """Return a shared ImageFinder instance (avoids GC churn in 24/7 runs)."""
    global _finder_instance
    if _finder_instance is None:
        _finder_instance = ImageFinder()
    return _finder_instance


def _nms(boxes: list[tuple[int, int, int, int]], t_w: int, t_h: int,
         overlap_thresh: float = 0.3) -> list[tuple[int, int, int, int]]:
    """Simple non-max suppression to remove overlapping detections."""
    if not boxes:
        return []
    dx_thresh = t_w * (1 - overlap_thresh)
    dy_thresh = t_h * (1 - overlap_thresh)
    filtered = [boxes[0]]
    for box in boxes[1:]:
        bx, by = box[0], box[1]
        is_overlap = False
        for existing in filtered:
            if abs(bx - existing[0]) < dx_thresh and \
               abs(by - existing[1]) < dy_thresh:
                is_overlap = True
                break
        if not is_overlap:
            filtered.append(box)
    return filtered


# ---------------------------------------------------------------------------
# Action wrappers for macro usage
# ---------------------------------------------------------------------------

@register_action("wait_for_image")
class WaitForImage(Action):
    """Wait until an image appears on screen (with timeout)."""

    def __init__(self, image_path: str = "", confidence: float = 0.8,
                 timeout_ms: int = 10000, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.image_path = image_path
        self.confidence = confidence
        self.timeout_ms = timeout_ms

    def execute(self) -> bool:
        finder = get_image_finder()
        result = finder.find_on_screen(
            self.image_path,
            confidence=self.confidence,
            timeout_ms=self.timeout_ms,
        )
        if result is None:
            logger.warning("WaitForImage timed out: %s", self.image_path)
            return False
        return True

    def _get_params(self) -> dict[str, Any]:
        return {
            "image_path": self.image_path,
            "confidence": self.confidence,
            "timeout_ms": self.timeout_ms,
        }

    def _set_params(self, params: dict[str, Any]) -> None:
        self.image_path = params.get("image_path", "")
        self.confidence = params.get("confidence", 0.8)
        self.timeout_ms = params.get("timeout_ms", 10000)

    def get_display_name(self) -> str:
        name = Path(self.image_path).name if self.image_path else "?"
        return f"Wait for '{name}' ({self.timeout_ms}ms)"


@register_action("click_on_image")
class ClickOnImage(Action):
    """Find an image on screen and click its center."""

    def __init__(self, image_path: str = "", confidence: float = 0.8,
                 timeout_ms: int = 10000, button: str = "left", **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.image_path = image_path
        self.confidence = confidence
        self.timeout_ms = timeout_ms
        self.button = button

    def execute(self) -> bool:
        import pyautogui
        finder = get_image_finder()
        result = finder.find_on_screen(
            self.image_path,
            confidence=self.confidence,
            timeout_ms=self.timeout_ms,
        )
        if result is None:
            logger.warning("ClickOnImage: image not found: %s",
                           self.image_path)
            return False

        cx, cy = finder.get_center(result)
        pyautogui.click(cx, cy, button=self.button)
        logger.info("Clicked on image at (%d, %d)", cx, cy)
        return True

    def _get_params(self) -> dict[str, Any]:
        return {
            "image_path": self.image_path,
            "confidence": self.confidence,
            "timeout_ms": self.timeout_ms,
            "button": self.button,
        }

    def _set_params(self, params: dict[str, Any]) -> None:
        self.image_path = params.get("image_path", "")
        self.confidence = params.get("confidence", 0.8)
        self.timeout_ms = params.get("timeout_ms", 10000)
        self.button = params.get("button", "left")

    def get_display_name(self) -> str:
        name = Path(self.image_path).name if self.image_path else "?"
        return f"Click on '{name}'"


@register_action("image_exists")
class ImageExists(Action):
    """Check if an image exists on screen (non-blocking)."""

    def __init__(self, image_path: str = "", confidence: float = 0.8, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.image_path = image_path
        self.confidence = confidence
        self._found = False

    def execute(self) -> bool:
        finder = get_image_finder()
        result = finder.find_on_screen(
            self.image_path,
            confidence=self.confidence,
            timeout_ms=0,
        )
        self._found = result is not None
        return True  # always succeeds – just sets the flag

    @property
    def found(self) -> bool:
        return self._found

    def _get_params(self) -> dict[str, Any]:
        return {
            "image_path": self.image_path,
            "confidence": self.confidence,
        }

    def _set_params(self, params: dict[str, Any]) -> None:
        self.image_path = params.get("image_path", "")
        self.confidence = params.get("confidence", 0.8)

    def get_display_name(self) -> str:
        name = Path(self.image_path).name if self.image_path else "?"
        return f"Image exists? '{name}'"


@register_action("take_screenshot")
class TakeScreenshot(Action):
    """Capture a screenshot during macro execution and save to disk."""

    def __init__(self, save_dir: str = "", filename_pattern: str = "",
                 region_x: int = 0, region_y: int = 0,
                 region_w: int = 0, region_h: int = 0,
                 **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.save_dir = save_dir or "macros/screenshots"
        self.filename_pattern = filename_pattern or "screenshot_%Y%m%d_%H%M%S.png"
        self.region_x = region_x
        self.region_y = region_y
        self.region_w = region_w
        self.region_h = region_h

    def execute(self) -> bool:
        import os
        os.makedirs(self.save_dir, exist_ok=True)
        filename = time.strftime(self.filename_pattern)
        filepath = os.path.join(self.save_dir, filename)
        # Avoid collision on same-second captures
        counter = 1
        base, ext = os.path.splitext(filepath)
        while os.path.exists(filepath):
            filepath = f"{base}_{counter}{ext}"
            counter += 1
        region = None
        if self.region_w > 0 and self.region_h > 0:
            region = (self.region_x, self.region_y,
                      self.region_w, self.region_h)
        save_screenshot(filepath, region)
        logger.info("Screenshot saved: %s", filepath)
        return True

    def _get_params(self) -> dict[str, Any]:
        return {
            "save_dir": self.save_dir,
            "filename_pattern": self.filename_pattern,
            "region_x": self.region_x,
            "region_y": self.region_y,
            "region_w": self.region_w,
            "region_h": self.region_h,
        }

    def _set_params(self, params: dict[str, Any]) -> None:
        self.save_dir = params.get("save_dir", "macros/screenshots")
        self.filename_pattern = params.get("filename_pattern",
                                            "screenshot_%Y%m%d_%H%M%S.png")
        self.region_x = params.get("region_x", 0)
        self.region_y = params.get("region_y", 0)
        self.region_w = params.get("region_w", 0)
        self.region_h = params.get("region_h", 0)

    def get_display_name(self) -> str:
        if self.region_w > 0:
            return f"Screenshot ({self.region_w}×{self.region_h})"
        return "Screenshot (Full Screen)"

