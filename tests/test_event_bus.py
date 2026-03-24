"""
Tests for core.event_bus — AppEventBus singleton and signal forwarding.
"""
import os
import sys
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from unittest.mock import MagicMock
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QObject, pyqtSignal

app = QApplication.instance() or QApplication([])

from core.event_bus import AppEventBus


@pytest.fixture(autouse=True)
def reset_bus():
    """Reset singleton before each test."""
    AppEventBus.reset()
    yield
    AppEventBus.reset()


class TestSingleton:
    def test_instance_returns_same_object(self):
        bus1 = AppEventBus.instance()
        bus2 = AppEventBus.instance()
        assert bus1 is bus2

    def test_reset_clears_instance(self):
        bus1 = AppEventBus.instance()
        AppEventBus.reset()
        bus2 = AppEventBus.instance()
        assert bus1 is not bus2

    def test_instance_type(self):
        bus = AppEventBus.instance()
        assert isinstance(bus, AppEventBus)
        assert isinstance(bus, QObject)


class TestSignals:
    def test_engine_started(self):
        bus = AppEventBus.instance()
        received = []
        bus.engine_started.connect(lambda: received.append("start"))
        bus.engine_started.emit()
        assert received == ["start"]

    def test_engine_stopped(self):
        bus = AppEventBus.instance()
        received = []
        bus.engine_stopped.connect(lambda: received.append("stop"))
        bus.engine_stopped.emit()
        assert received == ["stop"]

    def test_engine_error(self):
        bus = AppEventBus.instance()
        received = []
        bus.engine_error.connect(lambda msg: received.append(msg))
        bus.engine_error.emit("test error")
        assert received == ["test error"]

    def test_engine_progress(self):
        bus = AppEventBus.instance()
        received = []
        bus.engine_progress.connect(lambda c, t: received.append((c, t)))
        bus.engine_progress.emit(5, 10)
        assert received == [(5, 10)]

    def test_engine_action(self):
        bus = AppEventBus.instance()
        received = []
        bus.engine_action.connect(lambda n: received.append(n))
        bus.engine_action.emit("click")
        assert received == ["click"]

    def test_engine_loop(self):
        bus = AppEventBus.instance()
        received = []
        bus.engine_loop.connect(lambda c, t: received.append((c, t)))
        bus.engine_loop.emit(3, 5)
        assert received == [(3, 5)]

    def test_engine_step(self):
        bus = AppEventBus.instance()
        received = []
        bus.engine_step.connect(lambda i, n: received.append((i, n)))
        bus.engine_step.emit(0, "mouse_click")
        assert received == [(0, "mouse_click")]

    def test_macro_loaded(self):
        bus = AppEventBus.instance()
        received = []
        bus.macro_loaded.connect(lambda p: received.append(p))
        bus.macro_loaded.emit("/path/to/macro.json")
        assert received == ["/path/to/macro.json"]

    def test_macro_saved(self):
        bus = AppEventBus.instance()
        received = []
        bus.macro_saved.connect(lambda p: received.append(p))
        bus.macro_saved.emit("/saved.json")
        assert received == ["/saved.json"]

    def test_actions_changed(self):
        bus = AppEventBus.instance()
        received = []
        bus.actions_changed.connect(lambda: received.append(True))
        bus.actions_changed.emit()
        assert received == [True]

    def test_theme_changed(self):
        bus = AppEventBus.instance()
        received = []
        bus.theme_changed.connect(lambda t: received.append(t))
        bus.theme_changed.emit("light")
        assert received == ["light"]


class TestBridgeEngine:
    def _make_mock_engine(self):
        engine = MagicMock()
        engine.started_signal = MockSignal()
        engine.stopped_signal = MockSignal()
        engine.error_signal = MockSignal()
        engine.progress_signal = MockSignal()
        engine.action_signal = MockSignal()
        engine.loop_signal = MockSignal()
        engine.step_signal = MockSignal()
        return engine

    def test_bridge_connects_signals(self):
        bus = AppEventBus.instance()
        engine = self._make_mock_engine()
        bus.bridge_engine(engine)
        # Verify connect was called on each signal
        engine.started_signal.connect.assert_called_once()
        engine.stopped_signal.connect.assert_called_once()
        engine.error_signal.connect.assert_called_once()
        engine.progress_signal.connect.assert_called_once()
        engine.action_signal.connect.assert_called_once()
        engine.loop_signal.connect.assert_called_once()
        engine.step_signal.connect.assert_called_once()


class MockSignal:
    """Minimal signal mock with connect."""
    def __init__(self):
        self.connect = MagicMock()
