"""Tests for Speed Multiplier and Visual Context Click."""

import time
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from PyQt6.QtWidgets import QApplication

_app = QApplication.instance() or QApplication([])

# Force-register all action types
import core.action       # noqa: F401
import modules.mouse     # noqa: F401
import modules.keyboard  # noqa: F401


# ═════════════════════════════════════════════════════════════════
# Speed Multiplier Tests
# ═════════════════════════════════════════════════════════════════

class TestEngineContext:
    """Tests for core/engine_context.py."""

    def test_default_speed_is_1(self) -> None:
        from core.engine_context import get_speed
        # In a fresh thread, default should be 1.0
        import threading
        result = [0.0]
        def check():
            result[0] = get_speed()
        t = threading.Thread(target=check)
        t.start()
        t.join()
        assert result[0] == 1.0

    def test_set_speed(self) -> None:
        from core.engine_context import set_speed, get_speed
        set_speed(2.0)
        assert get_speed() == 2.0
        set_speed(1.0)  # reset

    def test_speed_clamped_min(self) -> None:
        from core.engine_context import set_speed, get_speed
        set_speed(0.01)
        assert get_speed() == 0.1
        set_speed(1.0)  # reset

    def test_speed_clamped_max(self) -> None:
        from core.engine_context import set_speed, get_speed
        set_speed(99.0)
        assert get_speed() == 10.0
        set_speed(1.0)  # reset

    def test_scaled_sleep_2x(self) -> None:
        from core.engine_context import set_speed, scaled_sleep
        set_speed(2.0)
        t0 = time.perf_counter()
        scaled_sleep(0.2)  # should sleep ~0.1s
        elapsed = time.perf_counter() - t0
        assert 0.05 < elapsed < 0.2
        set_speed(1.0)  # reset

    def test_scaled_sleep_half(self) -> None:
        from core.engine_context import set_speed, scaled_sleep
        set_speed(0.5)
        t0 = time.perf_counter()
        scaled_sleep(0.1)  # should sleep ~0.2s
        elapsed = time.perf_counter() - t0
        assert 0.15 < elapsed < 0.4
        set_speed(1.0)  # reset


class TestDelayActionScaling:
    """Tests that DelayAction respects speed factor."""

    def test_delay_action_uses_scaled_sleep(self) -> None:
        from core.action import DelayAction
        from core.engine_context import set_speed
        set_speed(5.0)
        t0 = time.perf_counter()
        action = DelayAction(duration_ms=500)
        action.execute()
        elapsed = time.perf_counter() - t0
        # 500ms at 5× speed = 100ms
        assert elapsed < 0.25
        set_speed(1.0)  # reset

    def test_action_delay_after_scaled(self) -> None:
        from core.action import DelayAction
        from core.engine_context import set_speed
        set_speed(5.0)
        action = DelayAction(duration_ms=100, delay_after=500)
        t0 = time.perf_counter()
        action.run()
        elapsed = time.perf_counter() - t0
        # (100 + 500)ms at 5× = 120ms
        assert elapsed < 0.3
        set_speed(1.0)  # reset


class TestEngineSpeedFactor:
    """Tests for MacroEngine.set_speed_factor."""

    def test_set_speed_factor(self) -> None:
        from core.engine import MacroEngine
        engine = MacroEngine()
        engine.set_speed_factor(3.0)
        assert engine._speed_factor == 3.0

    def test_set_speed_factor_clamped(self) -> None:
        from core.engine import MacroEngine
        engine = MacroEngine()
        engine.set_speed_factor(0.01)
        assert engine._speed_factor == 0.1
        engine.set_speed_factor(99.0)
        assert engine._speed_factor == 10.0


# ═════════════════════════════════════════════════════════════════
# Visual Context Click Tests
# ═════════════════════════════════════════════════════════════════

class TestMouseClickContext:
    """Tests for context_image in MouseClick classes."""

    def test_click_without_context(self) -> None:
        """Backward compatible: no context_image = existing behavior."""
        from modules.mouse import MouseClick
        action = MouseClick(x=100, y=200)
        assert action.context_image == ""
        params = action._get_params()
        assert "context_image" not in params

    def test_click_with_context_serialization(self) -> None:
        """context_image round-trips through to_dict/from_dict."""
        from modules.mouse import MouseClick
        from core.action import Action
        action = MouseClick(x=100, y=200, context_image="test.png")
        d = action.to_dict()
        restored = Action.from_dict(d)
        assert restored.context_image == "test.png"  # type: ignore
        assert restored.x == 100  # type: ignore

    def test_display_name_with_context(self) -> None:
        from modules.mouse import MouseClick
        action = MouseClick(x=10, y=20, context_image="img.png")
        assert "📷" in action.get_display_name()

    def test_display_name_without_context(self) -> None:
        from modules.mouse import MouseClick
        action = MouseClick(x=10, y=20)
        assert "📷" not in action.get_display_name()

    def test_resolve_visual_fallback(self) -> None:
        """When context_image doesn't exist, use coordinate fallback."""
        from modules.mouse import _resolve_visual
        x, y = _resolve_visual("nonexistent.png", 100, 200)
        assert (x, y) == (100, 200)

    def test_resolve_visual_empty_string(self) -> None:
        from modules.mouse import _resolve_visual
        x, y = _resolve_visual("", 100, 200)
        assert (x, y) == (100, 200)

    def test_double_click_context(self) -> None:
        from modules.mouse import MouseDoubleClick
        action = MouseDoubleClick(x=50, y=60, context_image="ctx.png")
        assert action.context_image == "ctx.png"
        assert "📷" in action.get_display_name()

    def test_right_click_context(self) -> None:
        from modules.mouse import MouseRightClick
        action = MouseRightClick(x=50, y=60, context_image="ctx.png")
        assert action.context_image == "ctx.png"
        assert "📷" in action.get_display_name()


class TestRecorderContextCapture:
    """Tests for Recorder._capture_click_context."""

    def test_capture_disabled_returns_none(self) -> None:
        from core.recorder import Recorder
        rec = Recorder(capture_context=False)
        result = rec._capture_click_context(100, 200)
        assert result is None

    def test_capture_enabled_saves_file(self) -> None:
        from core.recorder import Recorder
        with tempfile.TemporaryDirectory() as tmpdir:
            rec = Recorder(capture_context=True, macro_dir=tmpdir)
            with patch('pyautogui.screenshot') as mock_screenshot:
                mock_img = MagicMock()
                mock_screenshot.return_value = mock_img
                result = rec._capture_click_context(500, 300)

                assert result is not None
                assert "ctx_" in result
                mock_img.save.assert_called_once()
                # Check contexts dir was created
                assert (Path(tmpdir) / "contexts").exists()
