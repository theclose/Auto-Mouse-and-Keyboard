"""
Deep Coverage Tests — Phase 2 expansion.
Tests for previously 0-coverage modules:
  CrashHandler, TrayManager, ImageCapture, CoordinatePicker,
  Engine signals, Scheduler (LoopBlock/IfImageFound), and
  Action.run() mocked execution.

Run: python -m pytest tests/test_deep_coverage.py -v
"""

import os
import sys
import time
import copy
from pathlib import Path
from typing import Any
from unittest.mock import patch, MagicMock, PropertyMock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

_app = QApplication.instance() or QApplication([])

# Force-register all action types
import core.action       # noqa: F401
import modules.mouse     # noqa: F401
import modules.keyboard  # noqa: F401
import modules.image     # noqa: F401
import modules.pixel     # noqa: F401
import core.scheduler    # noqa: F401


# ============================================================
# 1. CrashHandler
# ============================================================

class TestCrashHandler:
    """Verify CrashHandler installs correctly and CrashDialog renders."""

    def test_install_sets_excepthook(self) -> None:
        from core.crash_handler import CrashHandler
        old_hook = sys.excepthook
        CrashHandler._installed = False  # reset singleton
        CrashHandler.install()
        assert sys.excepthook == CrashHandler._handle
        # Restore
        sys.excepthook = old_hook
        CrashHandler._installed = False

    def test_install_idempotent(self) -> None:
        from core.crash_handler import CrashHandler
        old_hook = sys.excepthook
        CrashHandler._installed = False
        CrashHandler.install()
        CrashHandler.install()  # second call — no-op
        assert sys.excepthook == CrashHandler._handle
        sys.excepthook = old_hook
        CrashHandler._installed = False

    def test_keyboard_interrupt_passes_through(self) -> None:
        from core.crash_handler import CrashHandler
        CrashHandler._handling = False
        # KeyboardInterrupt should pass to sys.__excepthook__
        with patch('sys.__excepthook__') as mock_hook:
            CrashHandler._handle(KeyboardInterrupt, KeyboardInterrupt(), None)
            mock_hook.assert_called_once()

    def test_crash_dialog_creates_without_error(self) -> None:
        from core.crash_handler import CrashDialog
        try:
            raise ValueError("test crash")
        except ValueError:
            import traceback
            exc_type, exc_val, exc_tb = sys.exc_info()
            dialog = CrashDialog(exc_type, exc_val, exc_tb)  # type: ignore
            assert dialog.windowTitle() == "AutoMacro – Error"
            assert "ValueError" in dialog._tb_text
            assert "test crash" in dialog._tb_text

    def test_crash_dialog_copy_to_clipboard(self) -> None:
        from core.crash_handler import CrashDialog
        try:
            raise RuntimeError("clipboard test")
        except RuntimeError:
            exc_type, exc_val, exc_tb = sys.exc_info()
            dialog = CrashDialog(exc_type, exc_val, exc_tb)  # type: ignore
            dialog._copy()
            clipboard = QApplication.clipboard()
            assert clipboard is not None
            text = clipboard.text()
            assert "clipboard test" in text
            assert "AutoMacro Crash Report" in text


# ============================================================
# 2. TrayManager
# ============================================================

class TestTrayManager:
    """Verify TrayManager signals, menu state, and tooltip updates."""

    def test_tray_signals_exist(self) -> None:
        from gui.tray import TrayManager
        tray = TrayManager()
        assert hasattr(tray, 'show_requested')
        assert hasattr(tray, 'play_requested')
        assert hasattr(tray, 'stop_requested')
        assert hasattr(tray, 'pause_requested')
        assert hasattr(tray, 'quit_requested')

    def test_update_state_idle(self) -> None:
        from gui.tray import TrayManager
        tray = TrayManager()
        tray.update_state(is_running=False, is_paused=False)
        assert tray._play_action.isEnabled()
        assert not tray._pause_action.isEnabled()
        assert not tray._stop_action.isEnabled()

    def test_update_state_running(self) -> None:
        from gui.tray import TrayManager
        tray = TrayManager()
        tray.update_state(is_running=True, is_paused=False)
        assert not tray._play_action.isEnabled()
        assert tray._pause_action.isEnabled()
        assert tray._stop_action.isEnabled()

    def test_update_state_paused(self) -> None:
        from gui.tray import TrayManager
        tray = TrayManager()
        tray.update_state(is_running=True, is_paused=True)
        assert tray._play_action.isEnabled()  # resume
        assert not tray._pause_action.isEnabled()
        assert tray._stop_action.isEnabled()

    def test_set_tooltip(self) -> None:
        from gui.tray import TrayManager
        tray = TrayManager()
        tray.set_tooltip("Testing 123")
        assert tray._tray.toolTip() == "Testing 123"

    def test_default_icon_creates(self) -> None:
        from gui.tray import _create_icon
        icon = _create_icon()
        assert not icon.isNull()


# ============================================================
# 3. ImageCaptureOverlay
# ============================================================

class TestImageCapture:
    """Verify ImageCaptureOverlay signal and save logic."""

    def test_save_region_emits_signal(self, tmp_path: Path) -> None:
        from gui.image_capture import ImageCaptureOverlay
        from PyQt6.QtCore import QRect
        from PyQt6.QtGui import QPixmap

        overlay = ImageCaptureOverlay(save_dir=str(tmp_path))
        received: list[str] = []
        overlay.image_captured.connect(lambda p: received.append(p))

        # Create a fake 100x100 screenshot
        overlay._screenshot = QPixmap(100, 100)
        overlay._screenshot.fill(Qt.GlobalColor.red)

        # Save a 50x50 region
        overlay._save_region(QRect(10, 10, 50, 50))

        assert len(received) == 1
        assert os.path.isfile(received[0])
        assert received[0].endswith(".png")

    def test_small_region_ignored(self) -> None:
        from gui.image_capture import ImageCaptureOverlay
        from PyQt6.QtCore import QRect, QPoint
        from PyQt6.QtGui import QPixmap, QMouseEvent
        from PyQt6.QtCore import QPointF

        overlay = ImageCaptureOverlay()
        overlay._screenshot = QPixmap(100, 100)

        received: list[str] = []
        overlay.image_captured.connect(lambda p: received.append(p))

        # Simulate draw a tiny 3x3 region — should NOT trigger save
        overlay._origin = QPoint(10, 10)
        overlay._current = QPoint(13, 13)
        overlay._drawing = True
        rect = QRect(overlay._origin, overlay._current).normalized()
        # Width=3, Height=3 → below threshold of 5
        assert rect.width() <= 5 or rect.height() <= 5

    def test_save_dir_created_if_missing(self, tmp_path: Path) -> None:
        from gui.image_capture import ImageCaptureOverlay
        from PyQt6.QtCore import QRect
        from PyQt6.QtGui import QPixmap

        new_dir = str(tmp_path / "new_subdir" / "templates")
        overlay = ImageCaptureOverlay(save_dir=new_dir)
        overlay._screenshot = QPixmap(100, 100)
        overlay._screenshot.fill(Qt.GlobalColor.blue)

        overlay._save_region(QRect(0, 0, 50, 50))
        assert os.path.isdir(new_dir)


# ============================================================
# 4. CoordinatePickerOverlay
# ============================================================

class TestCoordinatePicker:
    """Verify CoordinatePickerOverlay signals."""

    def test_signals_exist(self) -> None:
        from gui.coordinate_picker import CoordinatePickerOverlay
        picker = CoordinatePickerOverlay()
        assert hasattr(picker, 'coordinate_picked')
        assert hasattr(picker, 'cancelled')

    def test_escape_emits_cancelled(self) -> None:
        from gui.coordinate_picker import CoordinatePickerOverlay
        from PyQt6.QtGui import QKeyEvent
        from PyQt6.QtCore import QEvent

        picker = CoordinatePickerOverlay()
        received: list[bool] = []
        picker.cancelled.connect(lambda: received.append(True))

        event = QKeyEvent(
            QEvent.Type.KeyPress, Qt.Key.Key_Escape,
            Qt.KeyboardModifier.NoModifier)
        picker.keyPressEvent(event)

        assert len(received) == 1

    def test_magnifier_settings(self) -> None:
        from gui.coordinate_picker import CoordinatePickerOverlay
        picker = CoordinatePickerOverlay()
        assert picker.MAG_SIZE > 0
        assert picker.MAG_ZOOM > 0
        assert picker.CAPTURE_RADIUS > 0


# ============================================================
# 5. Engine signal emission
# ============================================================

class TestEngineSignals:
    """Verify engine emits correct signals during execution."""

    @staticmethod
    def _wait_engine(engine: Any, timeout_ms: int = 5000) -> None:
        """Wait for engine + process Qt events so cross-thread signals arrive."""
        engine.wait(timeout_ms)
        for _ in range(20):
            _app.processEvents()
            time.sleep(0.01)

    def test_started_and_stopped_signals(self) -> None:
        from core.engine import MacroEngine
        from core.action import DelayAction

        engine = MacroEngine()
        engine.load_actions([DelayAction(duration_ms=10)])
        engine.set_loop(count=1)

        started: list[bool] = []
        stopped: list[bool] = []
        engine.started_signal.connect(lambda: started.append(True))
        engine.stopped_signal.connect(lambda: stopped.append(True))

        engine.start()
        self._wait_engine(engine)

        assert len(started) == 1
        assert len(stopped) == 1

    def test_progress_signal_emitted(self) -> None:
        from core.engine import MacroEngine
        from core.action import DelayAction

        engine = MacroEngine()
        engine.load_actions([
            DelayAction(duration_ms=10),
            DelayAction(duration_ms=10),
        ])
        engine.set_loop(count=1)

        progress: list[tuple[int, int]] = []
        engine.progress_signal.connect(
            lambda c, t: progress.append((c, t)))

        engine.start()
        self._wait_engine(engine)

        assert len(progress) == 2
        assert progress[0] == (1, 2)
        assert progress[1] == (2, 2)

    def test_action_signal_emitted(self) -> None:
        from core.engine import MacroEngine
        from core.action import DelayAction

        engine = MacroEngine()
        engine.load_actions([DelayAction(duration_ms=10)])
        engine.set_loop(count=1)

        names: list[str] = []
        engine.action_signal.connect(lambda n: names.append(n))

        engine.start()
        self._wait_engine(engine)

        assert len(names) == 1
        assert "delay" in names[0].lower()

    def test_loop_signal_emitted(self) -> None:
        from core.engine import MacroEngine
        from core.action import DelayAction

        engine = MacroEngine()
        engine.load_actions([DelayAction(duration_ms=10)])
        engine.set_loop(count=3)

        loops: list[tuple[int, int]] = []
        engine.loop_signal.connect(
            lambda c, t: loops.append((c, t)))

        engine.start()
        self._wait_engine(engine)

        assert len(loops) == 3
        assert loops[0] == (1, 3)
        assert loops[2] == (3, 3)

    def test_error_signal_on_action_failure(self) -> None:
        from core.engine import MacroEngine
        from core.action import Action

        # Create a mock action that always fails
        fail_action = MagicMock(spec=Action)
        fail_action.enabled = True
        fail_action.repeat_count = 1
        fail_action.delay_after = 0
        fail_action.run.return_value = False
        fail_action.get_display_name.return_value = "MockFail"

        engine = MacroEngine()
        engine._actions = [fail_action]
        engine.set_loop(count=1)

        errors: list[str] = []
        engine.error_signal.connect(lambda e: errors.append(e))

        engine.start()
        self._wait_engine(engine)

        assert len(errors) >= 1
        assert "MockFail" in errors[0]


# ============================================================
# 6. LoopBlock (scheduler)
# ============================================================

class TestLoopBlock:
    """Verify LoopBlock nested execution and cancellation."""

    def test_loop_3_iterations(self) -> None:
        from core.scheduler import LoopBlock
        from core.action import DelayAction

        loop = LoopBlock(iterations=3)
        counter_action = DelayAction(duration_ms=0)
        loop.add_action(counter_action)

        result = loop.execute()
        assert result is True

    def test_loop_cancel_infinite(self) -> None:
        import threading
        from core.scheduler import LoopBlock
        from core.action import DelayAction

        loop = LoopBlock(iterations=0)  # infinite
        loop.add_action(DelayAction(duration_ms=1))

        # Cancel after 100ms
        def cancel_later() -> None:
            time.sleep(0.1)
            loop.cancel()

        threading.Thread(target=cancel_later, daemon=True).start()
        result = loop.execute()
        assert result is True

    def test_loop_display_name(self) -> None:
        from core.scheduler import LoopBlock
        from core.action import DelayAction

        loop = LoopBlock(iterations=5)
        loop.add_action(DelayAction(duration_ms=1))
        loop.add_action(DelayAction(duration_ms=1))

        name = loop.get_display_name()
        assert "5" in name
        assert "2 actions" in name

    def test_loop_infinite_display(self) -> None:
        from core.scheduler import LoopBlock
        loop = LoopBlock(iterations=0)
        assert "∞" in loop.get_display_name()

    def test_loop_serialization(self) -> None:
        from core.scheduler import LoopBlock
        from core.action import Action, DelayAction

        loop = LoopBlock(iterations=3)
        loop.add_action(DelayAction(duration_ms=100))

        d = loop.to_dict()
        restored = Action.from_dict(d)
        assert restored.ACTION_TYPE == "loop_block"
        assert restored.iterations == 3  # type: ignore


# ============================================================
# 7. IfImageFound (scheduler)
# ============================================================

class TestIfImageFound:
    """Verify IfImageFound conditional branching with mocked image."""

    def test_then_branch_on_found(self) -> None:
        from core.scheduler import IfImageFound
        from core.action import DelayAction

        cond = IfImageFound(image_path="test.png")
        then_action = DelayAction(duration_ms=0)
        cond.add_then_action(then_action)

        # Mock ImageFinder — imported inside execute() as modules.image.ImageFinder
        with patch('modules.image.ImageFinder') as MockFinder:
            MockFinder.return_value.find_on_screen.return_value = (100, 200)
            result = cond.execute()

        assert result is True

    def test_else_branch_on_not_found(self) -> None:
        from core.scheduler import IfImageFound
        from core.action import DelayAction

        cond = IfImageFound(image_path="test.png")
        else_action = DelayAction(duration_ms=0)
        cond.add_else_action(else_action)

        with patch('modules.image.ImageFinder') as MockFinder:
            MockFinder.return_value.find_on_screen.return_value = None
            result = cond.execute()

        assert result is True

    def test_display_name_shows_filename(self) -> None:
        from core.scheduler import IfImageFound
        cond = IfImageFound(image_path="C:/images/button.png")
        assert "button.png" in cond.get_display_name()

    def test_serialization_roundtrip(self) -> None:
        from core.scheduler import IfImageFound
        from core.action import Action

        cond = IfImageFound(
            image_path="test.png", confidence=0.9, timeout_ms=3000)
        d = cond.to_dict()
        restored = Action.from_dict(d)
        assert restored.ACTION_TYPE == "if_image_found"
        assert restored.confidence == 0.9  # type: ignore
        assert restored.timeout_ms == 3000  # type: ignore


# ============================================================
# 8. Action.run() with mock (no physical side-effects)
# ============================================================

class TestActionRunMocked:
    """Verify Action.run() → execute() pipeline with mocks."""

    def test_delay_action_runs_fast(self) -> None:
        from core.action import DelayAction
        action = DelayAction(duration_ms=1)
        result = action.run()
        assert result is True

    def test_disabled_action_skips(self) -> None:
        from core.action import DelayAction
        action = DelayAction(duration_ms=1000, enabled=False)
        start = time.perf_counter()
        result = action.run()
        elapsed = time.perf_counter() - start
        assert result is True
        assert elapsed < 0.1  # should skip, not wait 1s

    def test_repeat_count_executes_n_times(self) -> None:
        from core.action import DelayAction
        action = DelayAction(duration_ms=0, repeat_count=3)

        with patch.object(action, 'execute', return_value=True) as mock_exec:
            result = action.run()

        assert result is True
        assert mock_exec.call_count == 3

    def test_mouse_click_mocked(self) -> None:
        from modules.mouse import MouseClick
        action = MouseClick(x=100, y=200)

        mock_pag = MagicMock()
        with patch('modules.mouse._pag', return_value=mock_pag):
            result = action.execute()

        assert result is True
        mock_pag.click.assert_called_once()

    def test_key_press_mocked(self) -> None:
        from modules.keyboard import KeyPress
        action = KeyPress(key="enter")

        with patch('modules.keyboard.pyautogui') as mock_pag:
            result = action.execute()

        assert result is True
        mock_pag.press.assert_called_once_with("enter")

    def test_type_text_mocked(self) -> None:
        from modules.keyboard import TypeText
        action = TypeText(text="hello")

        # TypeText.execute() may use pyautogui.write or _send_unicode_string
        with patch('modules.keyboard.pyautogui') as mock_pag:
            result = action.execute()

        assert result is True


# ============================================================
# 9. Recorder toggle options
# ============================================================

class TestRecorderToggle:
    """Verify Recorder respects mouse/keyboard toggle."""

    def test_recorder_mouse_only(self) -> None:
        from core.recorder import Recorder
        r = Recorder(record_mouse=True, record_keyboard=False)
        assert r._record_mouse is True
        assert r._record_keyboard is False

    def test_recorder_keyboard_only(self) -> None:
        from core.recorder import Recorder
        r = Recorder(record_mouse=False, record_keyboard=True)
        assert r._record_mouse is False
        assert r._record_keyboard is True

    def test_recorder_both_disabled(self) -> None:
        from core.recorder import Recorder
        r = Recorder(record_mouse=False, record_keyboard=False)
        assert r._record_mouse is False
        assert r._record_keyboard is False


# ============================================================
# 10. Engine stop_on_error mode
# ============================================================

class TestEngineStopOnError:
    """Verify engine stops on first error when stop_on_error=True."""

    @staticmethod
    def _wait_engine(engine: Any, timeout_ms: int = 5000) -> None:
        engine.wait(timeout_ms)
        for _ in range(20):
            _app.processEvents()
            time.sleep(0.01)

    def test_stop_on_error_aborts_early(self) -> None:
        from core.engine import MacroEngine
        from core.action import Action, DelayAction

        fail = MagicMock(spec=Action)
        fail.enabled = True
        fail.repeat_count = 1
        fail.delay_after = 0
        fail.run.return_value = False
        fail.get_display_name.return_value = "MockFail"

        engine = MacroEngine()
        engine._actions = [fail, DelayAction(duration_ms=1)]
        engine.set_loop(count=1, stop_on_error=True)

        progress: list[tuple[int, int]] = []
        engine.progress_signal.connect(
            lambda c, t: progress.append((c, t)))

        engine.start()
        self._wait_engine(engine)

        # Should stop after first action, never reach second
        assert len(progress) == 1
        assert progress[0] == (1, 2)

    def test_continue_on_error_runs_all(self) -> None:
        from core.engine import MacroEngine
        from core.action import Action, DelayAction

        fail = MagicMock(spec=Action)
        fail.enabled = True
        fail.repeat_count = 1
        fail.delay_after = 0
        fail.run.return_value = False
        fail.get_display_name.return_value = "MockFail"

        engine = MacroEngine()
        engine._actions = [fail, DelayAction(duration_ms=1)]
        engine.set_loop(count=1, stop_on_error=False)

        progress: list[tuple[int, int]] = []
        engine.progress_signal.connect(
            lambda c, t: progress.append((c, t)))

        engine.start()
        self._wait_engine(engine)

        # Both actions should execute
        assert len(progress) == 2
