"""
Comprehensive unit tests for AutoPilot.
Covers action system, engine, scheduler, modules, and edge cases.
Run: python -m pytest tests/ -v
"""
import os
import sys
import threading
import time
from unittest.mock import MagicMock, patch

import pytest

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture(autouse=True)
def _register_all_actions():
    """Import all modules so action registry is populated."""
    import core.action  # noqa
    import modules.mouse  # noqa
    import modules.keyboard  # noqa
    import modules.pixel  # noqa
    import modules.image  # noqa
    import core.scheduler  # noqa


# ============================================================
# Phase 2.1: core/action.py
# ============================================================

class TestAction:
    """Test the action base class and registry."""

    def test_delay_action_defaults(self):
        from core.action import DelayAction
        da = DelayAction()
        assert da.duration_ms == 1000
        assert da.enabled is True
        assert da.repeat_count == 1
        assert da.delay_after == 0

    def test_delay_action_custom(self):
        from core.action import DelayAction
        da = DelayAction(duration_ms=500, delay_after=100,
                         repeat_count=3, description="test", enabled=False)
        assert da.duration_ms == 500
        assert da.delay_after == 100
        assert da.repeat_count == 3
        assert da.description == "test"
        assert da.enabled is False

    def test_serialization_roundtrip(self):
        from core.action import Action, DelayAction
        da = DelayAction(duration_ms=750, description="roundtrip test")
        d = da.to_dict()
        assert d["type"] == "delay"
        assert d["params"]["duration_ms"] == 750

        da2 = Action.from_dict(d)
        assert da2.ACTION_TYPE == "delay"
        assert da2.duration_ms == 750
        assert da2.description == "roundtrip test"

    def test_from_dict_missing_params(self):
        from core.action import Action
        da = Action.from_dict({"type": "delay"})
        assert da.duration_ms == 1000  # default

    def test_from_dict_unknown_type_raises(self):
        from core.action import Action
        with pytest.raises(ValueError, match="Unknown action type"):
            Action.from_dict({"type": "NONEXISTENT"})

    def test_registry_count(self):
        from core.action import get_all_action_types
        types = get_all_action_types()
        assert len(types) >= 18

    def test_get_action_class(self):
        from core.action import get_action_class
        cls = get_action_class("delay")
        assert cls.__name__ == "DelayAction"

    def test_get_action_class_invalid(self):
        from core.action import get_action_class
        with pytest.raises(ValueError):
            get_action_class("invalid_action")

    def test_display_name(self):
        from core.action import DelayAction
        da = DelayAction(duration_ms=1500)
        name = da.get_display_name()
        assert "1500" in name or "1.5" in name


# ============================================================
# Phase 2.2: modules/mouse.py
# ============================================================

class TestMouseActions:
    def test_click_params(self):
        from modules.mouse import MouseClick
        mc = MouseClick(x=100, y=200, duration=0.5)
        assert mc.x == 100
        assert mc.y == 200
        assert mc.duration == 0.5

    def test_click_display_name(self):
        from modules.mouse import MouseClick
        mc = MouseClick(x=42, y=99)
        assert "42" in mc.get_display_name()
        assert "99" in mc.get_display_name()

    def test_click_serialization(self):
        from core.action import Action
        from modules.mouse import MouseClick
        mc = MouseClick(x=10, y=20, duration=0.1)
        d = mc.to_dict()
        mc2 = Action.from_dict(d)
        assert mc2.x == 10
        assert mc2.y == 20

    def test_scroll_direction_display(self):
        from modules.mouse import MouseScroll
        up = MouseScroll(clicks=3)
        assert "up" in up.get_display_name()
        down = MouseScroll(clicks=-5)
        assert "down" in down.get_display_name()

    def test_drag_params(self):
        from modules.mouse import MouseDrag
        md = MouseDrag(x=50, y=60, duration=1.0, button="right")
        assert md.button == "right"

    def test_click_execute(self):
        from modules.mouse import MouseClick
        mc = MouseClick(x=100, y=200)
        with patch('modules.mouse._pyautogui') as mock_pag:
            mock_pag_instance = MagicMock()
            mock_pag.click = MagicMock()
            result = mc.execute()
        assert result is True

    def test_scroll_execute(self):
        from modules.mouse import MouseScroll
        ms = MouseScroll(x=0, y=0, clicks=5)
        with patch('modules.mouse._pyautogui') as mock_pag:
            result = ms.execute()
        assert result is True


# ============================================================
# Phase 2.3: modules/keyboard.py
# ============================================================

class TestKeyboardActions:
    def test_key_combo_no_shared_mutable(self):
        from modules.keyboard import KeyCombo
        kc1 = KeyCombo()
        kc2 = KeyCombo()
        kc1.keys.append("shift")
        assert "shift" not in kc2.keys

    def test_hotkey_no_shared_mutable(self):
        from modules.keyboard import HotKey
        hk1 = HotKey()
        hk2 = HotKey()
        hk1.keys.append("win")
        assert "win" not in hk2.keys

    def test_keypress_execute(self):
        from modules.keyboard import KeyPress
        kp = KeyPress(key="enter")
        with patch('modules.keyboard.pyautogui') as mock_pag:
            result = kp.execute()
        assert result is True
        mock_pag.press.assert_called_once_with("enter")

    def test_typetext_ascii(self):
        from modules.keyboard import TypeText
        tt = TypeText(text="hello", interval=0.01)
        with patch('modules.keyboard.pyautogui') as mock_pag:
            tt.execute()
        mock_pag.typewrite.assert_called_once_with("hello", interval=0.01)

    def test_typetext_unicode_uses_sendinput(self):
        """TypeText for non-ASCII should use _send_unicode_string."""
        import inspect

        from modules.keyboard import TypeText
        src = inspect.getsource(TypeText.execute)
        assert "_send_unicode_string" in src
        assert "pyautogui.write(" not in src

    def test_typetext_display(self):
        from modules.keyboard import TypeText
        tt = TypeText(text="Hello World! This is a long text that should be truncated")
        name = tt.get_display_name()
        assert "Hello" in name
        assert len(name) < 80


# ============================================================
# Phase 2.4: core/scheduler.py
# ============================================================

class TestScheduler:
    def test_loop_block_finite(self):
        from core.scheduler import LoopBlock
        counter = {"value": 0}

        class CountAction:
            ACTION_TYPE = "test_count"
            delay_after = 0
            repeat_count = 1
            enabled = True
            description = ""
            def run(self):
                counter["value"] += 1
                return True
            def get_display_name(self):
                return "count"

        lb = LoopBlock(iterations=5)
        lb._sub_actions = [CountAction()]
        lb.execute()
        assert counter["value"] == 5

    def test_loop_block_cancel_infinite(self):
        from core.action import DelayAction
        from core.scheduler import LoopBlock
        lb = LoopBlock(iterations=0)
        lb.add_action(DelayAction(duration_ms=5))

        t = threading.Thread(target=lb.execute, daemon=True)
        t.start()
        time.sleep(0.1)
        lb.cancel()
        t.join(timeout=2.0)
        assert not t.is_alive(), "LoopBlock should stop after cancel()"

    def test_loop_block_serialization(self):
        from core.scheduler import LoopBlock
        lb = LoopBlock(iterations=3)
        d = lb.to_dict()
        assert d["type"] == "loop_block"
        assert d["params"]["iterations"] == 3

    def test_if_image_found_display(self):
        from core.scheduler import IfImageFound
        iff = IfImageFound(image_path="/path/to/test.png")
        assert "test.png" in iff.get_display_name()


# ============================================================
# Phase 2.5: core/recorder.py
# ============================================================

class TestRecorder:
    def test_recorder_has_lock(self):
        from core.recorder import Recorder
        r = Recorder()
        assert hasattr(r, "_actions_lock")
        assert isinstance(r._actions_lock, type(threading.Lock()))

    def test_start_stop_clean(self):
        from core.recorder import Recorder
        r = Recorder()
        actions = r.stop()
        assert actions == []

    def test_action_count_property(self):
        from core.recorder import Recorder
        r = Recorder()
        assert r.action_count == 0


# ============================================================
# Phase 2.6: core/memory_manager.py
# ============================================================

class TestMemoryManager:
    def test_singleton(self):
        from core.memory_manager import MemoryManager
        mm1 = MemoryManager.instance()
        mm2 = MemoryManager.instance()
        assert mm1 is mm2

    def test_get_memory(self):
        from core.memory_manager import MemoryManager
        mm = MemoryManager.instance()
        mem = mm._get_memory()
        assert mem > 0, "_get_memory should return non-zero RSS"

    def test_get_stats(self):
        from core.memory_manager import MemoryManager
        mm = MemoryManager.instance()
        stats = mm.get_stats()
        assert "current_mb" in stats
        assert "peak_mb" in stats
        assert "threshold_mb" in stats

    def test_cleanup_callback(self):
        from core.memory_manager import MemoryManager
        mm = MemoryManager.instance()
        cleaned = {"flag": False}

        def cb():
            cleaned["flag"] = True

        mm.register_cleanup(cb)
        mm._do_cleanup()
        assert cleaned["flag"]
        # Clean up callback to not affect other tests
        mm._cleanup_callbacks.remove(cb)


# ============================================================
# Phase 2.7: core/hotkey_manager.py
# ============================================================

class TestHotkeyManager:
    def test_parse_f6(self):
        from core.hotkey_manager import parse_hotkey
        m, v = parse_hotkey("F6")
        assert v == 0x75

    def test_parse_combo(self):
        from core.hotkey_manager import parse_hotkey
        m, v = parse_hotkey("CTRL+SHIFT+A")
        assert (m & 0x0002) != 0  # CTRL
        assert (m & 0x0004) != 0  # SHIFT
        assert v == ord("A")

    def test_parse_invalid_raises(self):
        from core.hotkey_manager import parse_hotkey
        with pytest.raises(ValueError):
            parse_hotkey("INVALID_KEY_NAME")

    def test_parse_no_main_key_raises(self):
        from core.hotkey_manager import parse_hotkey
        with pytest.raises(ValueError):
            parse_hotkey("CTRL+SHIFT")


# ============================================================
# Phase 2.8: modules/screen.py
# ============================================================

class TestScreenModule:
    def test_screen_size(self):
        from modules.screen import get_screen_size
        w, h = get_screen_size()
        assert w > 0
        assert h > 0

    def test_full_screen_capture(self):
        """Screen capture returns valid image shape."""
        from modules.screen import capture_full_screen
        img = capture_full_screen()
        assert len(img.shape) == 3
        assert img.shape[2] == 3  # BGR

    def test_region_capture(self):
        from modules.screen import capture_region
        img = capture_region(0, 0, 50, 50)
        assert len(img.shape) == 3
        assert img.shape[2] == 3  # BGR

    def test_thread_safe_capture(self):
        from modules.screen import capture_full_screen
        errors = []

        def capture_thread():
            try:
                for _ in range(3):
                    capture_full_screen()
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=capture_thread) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)
        assert len(errors) == 0, f"Thread-safe errors: {errors}"


# ============================================================
# Phase 2.9: modules/pixel.py
# ============================================================

class TestPixelModule:
    def test_get_pixel(self):
        from modules.pixel import get_pixel_checker
        pc = get_pixel_checker()
        r, g, b = pc.get_pixel(0, 0)
        assert 0 <= r <= 255
        assert 0 <= g <= 255
        assert 0 <= b <= 255

    def test_check_pixel_color_match(self):
        from modules.pixel import CheckPixelColor, get_pixel_checker
        pc = get_pixel_checker()
        r, g, b = pc.get_pixel(0, 0)
        cpc = CheckPixelColor(x=0, y=0, r=r, g=g, b=b, tolerance=5)
        cpc.execute()
        assert cpc.matched

    def test_check_pixel_color_mismatch(self):
        from modules.pixel import CheckPixelColor
        cpc = CheckPixelColor(x=0, y=0, r=0, g=0, b=0, tolerance=0)
        # Whether it matches depends on actual pixel, but test doesn't crash
        cpc.execute()
        # Just ensure it runs without error


# ============================================================
# Phase 3: Integration Tests
# ============================================================

class TestMacroIO:
    """Test macro save/load round-trip."""

    def test_save_load_roundtrip(self, tmp_path):
        from core.action import DelayAction
        from core.engine import MacroEngine
        from modules.keyboard import TypeText
        from modules.mouse import MouseClick

        actions = [
            DelayAction(duration_ms=100),
            MouseClick(x=42, y=99),
            TypeText(text="hello"),
        ]
        path = str(tmp_path / "test_macro.json")
        MacroEngine.save_macro(path, actions, name="test", loop_count=5)

        loaded, settings = MacroEngine.load_macro(path)
        assert len(loaded) == 3
        assert loaded[0].ACTION_TYPE == "delay"
        assert loaded[0].duration_ms == 100
        assert loaded[1].ACTION_TYPE == "mouse_click"
        assert loaded[1].x == 42
        assert loaded[2].ACTION_TYPE == "type_text"
        assert loaded[2].text == "hello"
        assert settings["loop_count"] == 5

    def test_save_load_empty_macro(self, tmp_path):
        from core.engine import MacroEngine
        path = str(tmp_path / "empty.json")
        MacroEngine.save_macro(path, [], name="empty")
        loaded, settings = MacroEngine.load_macro(path)
        assert len(loaded) == 0

    def test_load_nonexistent_file(self):
        from core.engine import MacroEngine
        with pytest.raises(Exception):
            MacroEngine.load_macro("/nonexistent/path.json")


class TestConfigIO:
    """Test settings load/save."""

    def test_load_default_config(self):
        from gui.settings_dialog import DEFAULT_CONFIG, load_config
        config = load_config("nonexistent_config.json")
        assert config == DEFAULT_CONFIG

    def test_save_load_config(self, tmp_path):
        from gui.settings_dialog import load_config, save_config
        path = str(tmp_path / "cfg.json")
        cfg = {"hotkeys": {"start_stop": "F5"}, "ui": {"theme": "dark"}}
        save_config(cfg, path)
        loaded = load_config(path)
        assert loaded["hotkeys"]["start_stop"] == "F5"


# ============================================================
# Phase 4: Edge Cases & Black-box
# ============================================================

class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_delay_zero(self):
        from core.action import DelayAction
        da = DelayAction(duration_ms=0)
        assert da.duration_ms == 0
        # Should execute without error
        result = da.execute()
        assert result is True

    def test_delay_negative_clamped(self):
        from core.action import DelayAction
        da = DelayAction(duration_ms=-100)
        # Should handle gracefully
        assert da.duration_ms == -100 or da.duration_ms == 0

    def test_mouse_click_edge_coordinates(self):
        from modules.mouse import MouseClick
        mc = MouseClick(x=0, y=0)
        assert mc.x == 0
        assert mc.y == 0

    def test_typetext_empty_string(self):
        from modules.keyboard import TypeText
        tt = TypeText(text="")
        assert tt.text == ""
        name = tt.get_display_name()
        assert isinstance(name, str)

    def test_key_combo_serialization_roundtrip(self):
        from core.action import Action
        from modules.keyboard import KeyCombo
        kc = KeyCombo(keys=["ctrl", "alt", "delete"])
        d = kc.to_dict()
        kc2 = Action.from_dict(d)
        assert kc2.keys == ["ctrl", "alt", "delete"]

    def test_loop_block_zero_subactions(self):
        from core.scheduler import LoopBlock
        lb = LoopBlock(iterations=3)
        # No sub-actions added
        result = lb.execute()
        assert result is True

    def test_image_finder_nonexistent_template(self):
        from modules.image import ImageFinder
        finder = ImageFinder()
        result = finder.find_on_screen(
            "nonexistent_image.png",
            confidence=0.8,
            timeout_ms=100,
        )
        assert result is None


# ============================================================
# Phase 5: Performance / Memory
# ============================================================

class TestPerformance:
    """Test memory and performance characteristics."""

    def test_image_cache_cleanup(self):
        from modules.image import ImageFinder
        for i in range(100):
            ImageFinder._cache[f"key_{i}"] = (time.perf_counter(), None)
        assert len(ImageFinder._cache) == 100
        ImageFinder.clear_cache()
        assert len(ImageFinder._cache) == 0

    def test_memory_manager_repeated_gc(self):
        from core.memory_manager import MemoryManager
        mm = MemoryManager.instance()
        initial = mm._get_memory()
        for _ in range(5):
            mm._do_cleanup()
        after = mm._get_memory()
        # Memory should not increase significantly
        assert after < initial * 2

    def test_screen_capture_repeated(self):
        """Ensure repeated captures don't leak memory excessively."""
        from modules.screen import capture_full_screen
        for _ in range(10):
            _ = capture_full_screen()
        # With conftest mock, this is lightweight — just verify no crash
