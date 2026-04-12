"""
Extended test suite for AutoPilot – targeting 80%+ code coverage.
Covers engine (run/pause/stop), recorder, image matching, autosave,
profiler, retry decorator, and keyboard/mouse execute paths.

Run: python -m pytest tests/ -v --cov=core --cov=modules
"""

import json
import os
import sys
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# QApplication singleton needed for engine signals
from PyQt6.QtWidgets import QApplication

_app = QApplication.instance() or QApplication([])


# ============================================================
# Retry decorator
# ============================================================

class TestRetryDecorator:
    """Test the retry utility."""

    def test_success_first_try(self):
        from core.retry import retry

        @retry(max_attempts=3, delay=0.01)
        def always_ok():
            return 42

        assert always_ok() == 42

    def test_retry_then_success(self):
        from core.retry import retry

        counter = {"n": 0}

        @retry(max_attempts=3, delay=0.01)
        def fail_twice():
            counter["n"] += 1
            if counter["n"] < 3:
                raise IOError("transient")
            return "ok"

        assert fail_twice() == "ok"
        assert counter["n"] == 3

    def test_retry_exhausted_raises(self):
        from core.retry import retry

        @retry(max_attempts=2, delay=0.01, exceptions=(ValueError,))
        def always_fail():
            raise ValueError("permanent")

        with pytest.raises(ValueError, match="permanent"):
            always_fail()

    def test_retry_only_catches_specified(self):
        from core.retry import retry

        @retry(max_attempts=3, delay=0.01, exceptions=(IOError,))
        def raise_type_error():
            raise TypeError("wrong type")

        with pytest.raises(TypeError):
            raise_type_error()

    def test_backoff_increases_delay(self):
        from core.retry import retry

        times = []

        @retry(max_attempts=3, delay=0.05, backoff=2.0, exceptions=(IOError,))
        def track_time():
            times.append(time.perf_counter())
            if len(times) < 3:
                raise IOError("fail")
            return "done"

        track_time()
        assert len(times) == 3
        gap1 = times[1] - times[0]
        gap2 = times[2] - times[1]
        assert gap2 > gap1  # backoff should increase delay


# ============================================================
# Engine – run, pause, stop, loop
# ============================================================

class TestEngineExecution:
    """Test MacroEngine execution paths."""

    def test_engine_run_basic(self):
        from core.action import DelayAction
        from core.engine import MacroEngine

        engine = MacroEngine()
        engine.load_actions([DelayAction(duration_ms=10)])
        engine.set_loop(count=1, delay_ms=0)
        engine.start()
        finished = engine.wait(3000)
        assert finished

    def test_engine_stop_mid_execution(self):
        from core.action import DelayAction
        from core.engine import MacroEngine

        engine = MacroEngine()
        engine.load_actions([DelayAction(duration_ms=500)] * 10)
        engine.set_loop(count=0, delay_ms=0)  # infinite

        engine.start()
        time.sleep(0.2)
        engine.stop()
        engine.wait(3000)
        assert not engine.isRunning()

    def test_engine_pause_resume(self):
        from core.action import DelayAction
        from core.engine import MacroEngine

        engine = MacroEngine()
        engine.load_actions([DelayAction(duration_ms=100)] * 20)
        engine.set_loop(count=0, delay_ms=0)

        engine.start()
        time.sleep(0.1)
        engine.pause()
        assert engine.is_paused

        time.sleep(0.2)
        engine.resume()
        time.sleep(0.1)
        engine.stop()
        engine.wait(3000)

    def test_engine_multi_loop(self):
        from core.action import DelayAction
        from core.engine import MacroEngine

        engine = MacroEngine()
        engine.load_actions([DelayAction(duration_ms=5)])
        engine.set_loop(count=3, delay_ms=10)
        engine.start()
        engine.wait(5000)
        # Engine finished (3 loops)
        assert not engine.isRunning()

    def test_engine_stop_on_error(self):
        from core.engine import MacroEngine

        class FailAction:
            ACTION_TYPE = "test_fail"
            delay_after = 0
            repeat_count = 1
            enabled = True
            description = ""
            def run(self):
                return False
            def get_display_name(self):
                return "Fail"

        engine = MacroEngine()
        engine.load_actions([FailAction()])
        engine.set_loop(count=1, delay_ms=0, stop_on_error=True)
        engine.start()
        engine.wait(3000)
        assert not engine.isRunning()

    def test_engine_exception_in_action(self):
        from core.engine import MacroEngine

        class CrashAction:
            ACTION_TYPE = "test_crash"
            delay_after = 0
            repeat_count = 1
            enabled = True
            description = ""
            def run(self):
                raise RuntimeError("boom")
            def get_display_name(self):
                return "Crash"

        engine = MacroEngine()
        engine.load_actions([CrashAction()])
        engine.set_loop(count=1, delay_ms=0, stop_on_error=True)
        engine.start()
        engine.wait(3000)
        assert not engine.isRunning()

    def test_engine_loop_delay(self):
        from core.action import DelayAction
        from core.engine import MacroEngine

        engine = MacroEngine()
        engine.load_actions([DelayAction(duration_ms=1)])
        engine.set_loop(count=2, delay_ms=100)

        t0 = time.perf_counter()
        engine.start()
        engine.wait(3000)
        elapsed = time.perf_counter() - t0
        assert elapsed >= 0.08  # ~100ms delay between loops

    def test_engine_empty_actions(self):
        from core.engine import MacroEngine

        engine = MacroEngine()
        engine.load_actions([])
        engine.set_loop(count=1, delay_ms=0)

        engine.start()
        engine.wait(1000)
        assert not engine.is_running

    def test_engine_check_pause_or_stop(self):
        from core.engine import MacroEngine

        engine = MacroEngine()
        engine._is_stopped = False
        engine._is_paused = False
        assert engine._check_pause_or_stop() is True

        engine._is_stopped = True
        assert engine._check_pause_or_stop() is False

    def test_engine_wait_loop_delay_zero(self):
        from core.engine import MacroEngine

        engine = MacroEngine()
        engine._loop_delay_ms = 0
        assert engine._wait_loop_delay() is True

    def test_engine_wait_loop_delay_stop(self):
        from core.engine import MacroEngine

        engine = MacroEngine()
        engine._loop_delay_ms = 5000
        engine._is_stopped = True
        # Should return quickly since stopped
        t0 = time.perf_counter()
        result = engine._wait_loop_delay()
        elapsed = time.perf_counter() - t0
        assert result is False
        assert elapsed < 1.0  # stopped immediately


# ============================================================
# Macro I/O with versioning
# ============================================================

class TestMacroVersioning:

    def test_save_includes_version(self, tmp_path):
        from core.action import DelayAction
        from core.engine import MacroEngine

        path = str(tmp_path / "v.json")
        MacroEngine.save_macro(path, [DelayAction(duration_ms=100)])
        with open(path) as f:
            data = json.load(f)
        assert data["version"] == "1.1"

    def test_load_v10_macro(self, tmp_path):
        from core.engine import MacroEngine

        path = str(tmp_path / "v10.json")
        data = {
            "version": "1.0",
            "name": "old",
            "actions": [{"type": "delay", "params": {"duration_ms": 500}}],
            "settings": {},
        }
        with open(path, "w") as f:
            json.dump(data, f)

        actions, settings = MacroEngine.load_macro(path)
        assert len(actions) == 1
        assert actions[0].duration_ms == 500

    def test_load_handles_invalid_action(self, tmp_path):
        from core.engine import MacroEngine

        path = str(tmp_path / "bad.json")
        data = {
            "version": "1.1",
            "name": "bad",
            "actions": [
                {"type": "delay", "params": {"duration_ms": 100}},
                {"type": "NONEXISTENT_TYPE", "params": {}},
                {"type": "delay", "params": {"duration_ms": 200}},
            ],
            "settings": {},
        }
        with open(path, "w") as f:
            json.dump(data, f)

        actions, _ = MacroEngine.load_macro(path)
        assert len(actions) == 2  # invalid action skipped
        assert actions[0].duration_ms == 100
        assert actions[1].duration_ms == 200


# ============================================================
# AutoSave Manager
# ============================================================

class TestAutoSave:

    def test_start_stop(self):
        from core.autosave import AutoSaveManager
        asm = AutoSaveManager(interval_s=1)
        asm.start(save_callback=lambda: True, backup_dir=Path(tempfile.mkdtemp()))
        assert asm._running
        asm.stop()
        assert not asm._running

    def test_mark_dirty_clean(self):
        from core.autosave import AutoSaveManager
        asm = AutoSaveManager()
        asm.mark_dirty()
        assert asm._dirty_event.is_set()
        asm.mark_clean()
        assert not asm._dirty_event.is_set()

    def test_set_current_file(self):
        from core.autosave import AutoSaveManager
        asm = AutoSaveManager()
        asm.set_current_file(Path("/some/file.json"))
        assert asm._current_file == Path("/some/file.json")

    def test_create_backup(self, tmp_path):
        from core.autosave import AutoSaveManager

        src = tmp_path / "test.json"
        src.write_text('{"test": true}')

        asm = AutoSaveManager(max_backups=3)
        asm._backup_dir = tmp_path
        asm._current_file = src
        asm._create_backup()

        backups = list((tmp_path / "backups").glob("backup_*.json"))
        assert len(backups) == 1

    def test_backup_rotation(self, tmp_path):
        from core.autosave import AutoSaveManager

        src = tmp_path / "test.json"
        src.write_text('{"test": true}')

        asm = AutoSaveManager(max_backups=2)
        asm._backup_dir = tmp_path
        asm._current_file = src

        for _ in range(4):
            asm._create_backup()
            time.sleep(0.01)

        backups = list((tmp_path / "backups").glob("backup_*.json"))
        assert len(backups) <= 2

    def test_autosave_fires_on_dirty(self, tmp_path):
        from core.autosave import AutoSaveManager

        saved = {"count": 0}

        def cb():
            saved["count"] += 1
            return True

        asm = AutoSaveManager(interval_s=1)
        asm.start(save_callback=cb, backup_dir=tmp_path)
        asm.mark_dirty()
        time.sleep(1.5)
        asm.stop()
        assert saved["count"] >= 1

    def test_no_save_when_clean(self, tmp_path):
        from core.autosave import AutoSaveManager

        saved = {"count": 0}

        def cb():
            saved["count"] += 1
            return True

        asm = AutoSaveManager(interval_s=1)
        asm.start(save_callback=cb, backup_dir=tmp_path)
        # Don't mark dirty
        time.sleep(1.5)
        asm.stop()
        assert saved["count"] == 0

    def test_double_start_ignored(self, tmp_path):
        from core.autosave import AutoSaveManager
        asm = AutoSaveManager(interval_s=1)
        asm.start(save_callback=lambda: True, backup_dir=tmp_path)
        thread1 = asm._thread
        asm.start(save_callback=lambda: True, backup_dir=tmp_path)
        assert asm._thread is thread1
        asm.stop()


# ============================================================
# Recorder – broader exception handling
# ============================================================

class TestRecorderCallbacks:

    def test_on_mouse_click_catches_exception(self):
        from pynput.mouse import Button

        from core.recorder import Recorder
        r = Recorder()
        r._is_recording = True
        r._last_time = time.perf_counter()
        try:
            r._on_click(100, 200, Button.left, True)
        except Exception:
            pytest.fail("_on_click should catch all exceptions")

    def test_on_scroll_catches_exception(self):
        from core.recorder import Recorder
        r = Recorder()
        r._is_recording = True
        try:
            r._on_scroll(100, 200, 0, 3)
        except Exception:
            pytest.fail("_on_scroll should catch all exceptions")

    def test_on_key_press_catches_exception(self):
        from core.recorder import Recorder
        r = Recorder()
        r._is_recording = True
        try:
            r._on_key_press(MagicMock())
        except Exception:
            pytest.fail("_on_key_press should catch all exceptions")

    def test_actions_lock_thread_safety(self):
        from core.recorder import Recorder
        r = Recorder()
        r._is_recording = True

        errors = []

        def trigger():
            try:
                for _ in range(10):
                    with r._actions_lock:
                        r._actions.append({"test": True})
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=trigger) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=3)
        assert len(errors) == 0
        assert len(r._actions) == 50


# ============================================================
# Image matching helpers
# ============================================================

class TestImageHelpers:

    def test_match_template_returns_none_for_no_match(self):
        from modules.image import ImageFinder

        finder = ImageFinder()
        # Random noise screen — specific pattern won't match
        rng = np.random.RandomState(42)
        screen = rng.randint(0, 256, (200, 200), dtype=np.uint8)
        # Very specific template that won't exist in random noise
        template = np.arange(100, dtype=np.uint8).reshape(10, 10)
        result = finder._match_template(screen, template, 0.999, None)
        assert result is None

    def test_match_multi_scale_returns_none(self):
        from modules.image import ImageFinder

        finder = ImageFinder()
        rng = np.random.RandomState(123)
        screen = rng.randint(0, 256, (200, 200), dtype=np.uint8)
        template = np.arange(100, dtype=np.uint8).reshape(10, 10)
        result = finder._match_multi_scale(
            screen, template, 0.999, None, 0.0, (0, 0))
        assert result is None

    def test_clear_cache(self):
        from modules.image import ImageFinder
        ImageFinder._cache["test_key"] = (time.perf_counter(), None)
        assert "test_key" in ImageFinder._cache
        ImageFinder.clear_cache()
        assert len(ImageFinder._cache) == 0


# ============================================================
# Keyboard – execute paths
# ============================================================

class TestKeyboardExecute:

    def test_key_press_execute(self):
        from modules.keyboard import KeyPress
        kp = KeyPress(key="tab")
        with patch('modules.keyboard.pyautogui') as mock_pag:
            assert kp.execute() is True
            mock_pag.press.assert_called_once_with("tab")

    def test_hotkey_execute(self):
        from modules.keyboard import HotKey
        hk = HotKey(keys=["ctrl", "s"])
        with patch('modules.keyboard.pyautogui') as mock_pag:
            assert hk.execute() is True
            mock_pag.hotkey.assert_called_once_with("ctrl", "s")

    def test_key_combo_execute(self):
        from modules.keyboard import KeyCombo
        kc = KeyCombo(keys=["alt", "f4"])
        with patch('modules.keyboard.pyautogui') as mock_pag:
            assert kc.execute() is True
            mock_pag.hotkey.assert_called_once_with("alt", "f4")

    def test_typetext_display_truncation(self):
        from modules.keyboard import TypeText
        long_text = "A" * 200
        tt = TypeText(text=long_text)
        name = tt.get_display_name()
        assert len(name) < 80


# ============================================================
# Mouse – additional execute paths
# ============================================================

class TestMouseExecute:

    def test_mouse_move_execute(self):
        from modules.mouse import MouseMove
        mm = MouseMove(x=500, y=300, duration=0.1)
        with patch('modules.mouse._pyautogui') as mock_pag:
            assert mm.execute() is True

    def test_double_click_execute(self):
        from modules.mouse import MouseDoubleClick
        mdc = MouseDoubleClick(x=100, y=200)
        with patch('modules.mouse._pyautogui') as mock_pag:
            assert mdc.execute() is True

    def test_right_click_execute(self):
        from modules.mouse import MouseRightClick
        mrc = MouseRightClick(x=50, y=75)
        with patch('modules.mouse._pyautogui') as mock_pag:
            assert mrc.execute() is True

    def test_drag_execute(self):
        from modules.mouse import MouseDrag
        md = MouseDrag(x=100, y=200, duration=0.1)
        with patch('modules.mouse._pyautogui') as mock_pag:
            assert md.execute() is True


# ============================================================
# Profiler singleton
# ============================================================

class TestProfiler:

    def test_singleton(self):
        from core.profiler import get_profiler
        p1 = get_profiler()
        p2 = get_profiler()
        assert p1 is p2

    def test_track_context(self):
        from core.profiler import get_profiler
        p = get_profiler()
        with p.track("test_op"):
            time.sleep(0.01)
        report = p.report()
        assert "test_op" in report

    def test_report_empty(self):
        from core.profiler import PerformanceProfiler
        p = PerformanceProfiler()
        report = p.report()
        assert isinstance(report, str)


# ============================================================
# Screen module – additional paths
# ============================================================

class TestScreenAdditional:

    def test_get_screen_size_positive(self):
        from modules.screen import get_screen_size
        w, h = get_screen_size()
        assert w > 0 and h > 0

    def test_capture_region_exact_size(self):
        from modules.screen import capture_region
        img = capture_region(10, 10, 30, 30)
        assert len(img.shape) == 3
        assert img.shape[2] == 3  # BGR

    def test_get_pixel_via_pixel_module(self):
        from modules.pixel import get_pixel_checker
        pc = get_pixel_checker()
        r, g, b = pc.get_pixel(0, 0)
        assert all(0 <= c <= 255 for c in (r, g, b))


# ============================================================
# HotkeyManager – additional parse tests
# ============================================================

class TestHotkeyManagerExtended:

    def test_parse_f1_through_f12(self):
        from core.hotkey_manager import parse_hotkey
        for i in range(1, 13):
            m, v = parse_hotkey(f"F{i}")
            assert v > 0

    def test_parse_ctrl_alt_combo(self):
        from core.hotkey_manager import parse_hotkey
        m, v = parse_hotkey("CTRL+ALT+Q")
        assert (m & 0x0002) != 0  # CTRL
        assert (m & 0x0001) != 0  # ALT
        assert v == ord("Q")
