"""Tests for Multi-Run Dashboard — EngineSlot management and concurrent execution."""

import threading
import time

import pytest

from gui.panels.multi_run_panel import MAX_SLOTS, EngineSlot


class TestEngineSlot:
    """Test EngineSlot dataclass."""

    def test_defaults(self):
        slot = EngineSlot()
        assert slot.status == "idle"
        assert slot.progress == (0, 0)
        assert slot.loop_info == (0, 0)
        assert slot.macro_name == ""
        assert slot.engine is None

    def test_with_data(self):
        slot = EngineSlot(macro_name="login", macro_path="/test.json")
        assert slot.macro_name == "login"
        assert slot.macro_path == "/test.json"


class TestMultiRunPanel:
    """Test MultiRunPanel logic (mocked Qt)."""

    def test_max_slots_constant(self):
        assert MAX_SLOTS == 4


class TestEngineContextIsolation:
    """Verify engine_context is thread-local (multi-engine safe)."""

    def test_speed_isolation(self):
        """Two threads setting different speeds don't interfere."""
        from core.engine_context import get_speed, reset_globals, set_speed

        results = {}

        def _thread_a():
            set_speed(2.0)
            time.sleep(0.05)
            results["a"] = get_speed()

        def _thread_b():
            set_speed(5.0)
            time.sleep(0.05)
            results["b"] = get_speed()

        t1 = threading.Thread(target=_thread_a)
        t2 = threading.Thread(target=_thread_b)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # Each thread should see its own speed
        assert results["a"] == 2.0
        assert results["b"] == 5.0

        # Main thread should see default (unless set)
        reset_globals()
        assert get_speed() == 1.0

    def test_jitter_isolation(self):
        """Two threads setting different jitters don't interfere."""
        from core.engine_context import get_jitter, reset_globals, set_jitter

        results = {}

        def _thread_a():
            set_jitter(0.1)
            time.sleep(0.05)
            results["a"] = get_jitter()

        def _thread_b():
            set_jitter(0.4)
            time.sleep(0.05)
            results["b"] = get_jitter()

        t1 = threading.Thread(target=_thread_a)
        t2 = threading.Thread(target=_thread_b)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert results["a"] == pytest.approx(0.1)
        assert results["b"] == pytest.approx(0.4)

        reset_globals()
        assert get_jitter() == 0.0

    def test_stop_event_isolation(self):
        """Each thread has its own stop event."""
        from core.engine_context import is_stopped, reset_globals, set_stop_event

        results = {}
        evt_a = threading.Event()
        evt_b = threading.Event()

        def _thread_a():
            set_stop_event(evt_a)
            time.sleep(0.05)
            results["a"] = is_stopped()

        def _thread_b():
            set_stop_event(evt_b)
            evt_b.set()  # Only B is stopped
            time.sleep(0.05)
            results["b"] = is_stopped()

        t1 = threading.Thread(target=_thread_a)
        t2 = threading.Thread(target=_thread_b)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert results["a"] is False  # A not stopped
        assert results["b"] is True   # B stopped

        reset_globals()

    def test_context_isolation(self):
        """Each thread has its own ExecutionContext."""
        from core.engine_context import get_context, reset_globals, set_context
        from core.execution_context import ExecutionContext

        results = {}

        def _thread_a():
            ctx = ExecutionContext()
            ctx.set_var("thread", "a")
            set_context(ctx)
            time.sleep(0.05)
            results["a"] = get_context().get_var("thread")

        def _thread_b():
            ctx = ExecutionContext()
            ctx.set_var("thread", "b")
            set_context(ctx)
            time.sleep(0.05)
            results["b"] = get_context().get_var("thread")

        t1 = threading.Thread(target=_thread_a)
        t2 = threading.Thread(target=_thread_b)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert results["a"] == "a"
        assert results["b"] == "b"

        reset_globals()

    def test_reset_clears_all(self):
        """reset_globals clears speed, jitter, and context."""
        from core.engine_context import (
            get_jitter,
            get_speed,
            reset_globals,
            set_jitter,
            set_speed,
        )

        set_speed(3.0)
        set_jitter(0.3)
        assert get_speed() == 3.0
        assert get_jitter() == pytest.approx(0.3)

        reset_globals()
        assert get_speed() == 1.0
        assert get_jitter() == 0.0


class TestVersionCompat:
    """Verify engine_context API compatibility with existing code."""

    def test_scaled_sleep_respects_speed(self):
        """scaled_sleep divides by speed factor."""
        from core.engine_context import reset_globals, scaled_sleep, set_speed

        set_speed(10.0)  # 10x speed → 100ms becomes 10ms
        t0 = time.perf_counter()
        scaled_sleep(0.1)  # Should be ~10ms
        elapsed = time.perf_counter() - t0

        assert elapsed < 0.05  # Much less than 100ms

        reset_globals()

    def test_scaled_sleep_respects_stop(self):
        """scaled_sleep returns early when stop event set."""
        from core.engine_context import reset_globals, scaled_sleep, set_stop_event

        evt = threading.Event()
        set_stop_event(evt)
        evt.set()

        t0 = time.perf_counter()
        scaled_sleep(10.0)  # Would take 10s without stop
        elapsed = time.perf_counter() - t0

        assert elapsed < 0.1

        reset_globals()
