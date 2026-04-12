"""
Thread-Safety Regression Tests — Prevents reintroduction of audit findings.

Each test corresponds to a specific bug found during the Extreme Audit:
    C1: ExecutionContext.record_action() race condition
    C2: ExecutionContext.reset() partial lock
    C3: ROI cache cross-thread access
    H1: AutoSave dirty flag race
    H4: EventBus connection leak
    L1: QMutex deadlock on exception

Run: python -m pytest tests/test_thread_safety.py -v
"""

import threading
import time

# QApplication singleton
from PyQt6.QtWidgets import QApplication

_app = QApplication.instance() or QApplication([])


class TestExecutionContextThreadSafety:
    """C1-C3: ExecutionContext must be thread-safe."""

    def test_concurrent_record_action(self):
        """C1: Concurrent record_action calls must not lose counts."""
        from core.execution_context import ExecutionContext

        ctx = ExecutionContext()
        errors = []
        n_per_thread = 500

        def worker():
            try:
                for _ in range(n_per_thread):
                    ctx.record_action(True)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert len(errors) == 0, f"Errors: {errors}"
        assert ctx.action_count == n_per_thread * 4

    def test_concurrent_record_with_failures(self):
        """C1: error_count must be accurate under concurrency."""
        from core.execution_context import ExecutionContext

        ctx = ExecutionContext()

        def worker_fail():
            for _ in range(200):
                ctx.record_action(False)

        def worker_success():
            for _ in range(200):
                ctx.record_action(True)

        threads = [
            threading.Thread(target=worker_fail),
            threading.Thread(target=worker_fail),
            threading.Thread(target=worker_success),
            threading.Thread(target=worker_success),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert ctx.action_count == 800
        assert ctx.error_count == 400

    def test_reset_clears_all_state(self):
        """C2: reset() must atomically clear all fields."""
        from core.execution_context import ExecutionContext

        ctx = ExecutionContext()
        ctx.record_action(True)
        ctx.record_action(False)
        ctx.set_var("test", 42)
        ctx.iteration_count = 5

        ctx.reset()

        assert ctx.action_count == 0
        assert ctx.error_count == 0
        assert ctx.iteration_count == 0
        assert ctx.get_var("test") is None
        assert ctx.start_time > 0  # Should be set to current time

    def test_roi_cache_fields_initialized(self):
        """C3: ROI cache fields must exist from init, not lazy getattr."""
        from core.execution_context import ExecutionContext

        ctx = ExecutionContext()
        assert hasattr(ctx, "_roi_cache_key")
        assert hasattr(ctx, "_roi_cache_val")
        assert hasattr(ctx, "_roi_cache_time")
        assert ctx._roi_cache_key is None
        assert ctx._roi_cache_time == 0.0

    def test_roi_cache_reset(self):
        """C3: reset() must clear ROI cache."""
        from core.execution_context import ExecutionContext

        ctx = ExecutionContext()
        # Simulate cached state
        with ctx._lock:
            ctx._roi_cache_key = "test_path"
            ctx._roi_cache_val = (0, 0, 100, 100)
            ctx._roi_cache_time = time.perf_counter()

        ctx.reset()

        assert ctx._roi_cache_key is None
        assert ctx._roi_cache_val is None
        assert ctx._roi_cache_time == 0.0


class TestAutoSaveThreadSafety:
    """H1: AutoSave dirty flag must be thread-safe."""

    def test_dirty_event_is_threading_event(self):
        """H1: _dirty must be threading.Event, not bool."""
        from core.autosave import AutoSaveManager

        mgr = AutoSaveManager()
        assert isinstance(mgr._dirty_event, threading.Event)

    def test_mark_dirty_clean_cycle(self):
        """H1: mark_dirty/mark_clean via Event API."""
        from core.autosave import AutoSaveManager

        mgr = AutoSaveManager()
        assert not mgr._dirty_event.is_set()

        mgr.mark_dirty()
        assert mgr._dirty_event.is_set()

        mgr.mark_clean()
        assert not mgr._dirty_event.is_set()

    def test_concurrent_mark_dirty(self):
        """H1: Concurrent mark_dirty must not crash."""
        from core.autosave import AutoSaveManager

        mgr = AutoSaveManager()
        errors = []

        def worker():
            try:
                for _ in range(100):
                    mgr.mark_dirty()
                    mgr.mark_clean()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)
        assert len(errors) == 0


class TestEventBusConnectionLeak:
    """H4: EventBus must not accumulate duplicate connections."""

    def test_bridge_engine_disconnects_previous(self):
        """H4: Calling bridge_engine twice must not double signals."""
        from PyQt6.QtWidgets import QApplication

        from core.engine import MacroEngine
        from core.event_bus import AppEventBus

        bus = AppEventBus()
        engine1 = MacroEngine()
        engine2 = MacroEngine()

        call_count = {"n": 0}

        def counter():
            call_count["n"] += 1

        bus.engine_started.connect(counter)

        bus.bridge_engine(engine1)
        bus.bridge_engine(engine2)  # Should disconnect engine1

        # Emit from engine2 — should fire counter exactly once
        engine2.started_signal.emit()
        QApplication.processEvents()
        assert call_count["n"] == 1

        # Emit from engine1 — should NOT reach bus (disconnected)
        engine1.started_signal.emit()
        QApplication.processEvents()
        assert call_count["n"] == 1  # Still 1, not 2

    def test_bridge_engine_first_call_no_error(self):
        """H4: First bridge_engine call must work without old engine."""
        from core.engine import MacroEngine
        from core.event_bus import AppEventBus

        bus = AppEventBus()
        engine = MacroEngine()
        bus.bridge_engine(engine)  # Should not raise


class TestEngineMutexSafety:
    """L1: Engine must use QMutexLocker, not manual lock/unlock."""

    def test_pause_resume_no_deadlock(self):
        """L1: Pause/resume must not deadlock even if rapid."""
        from core.action import DelayAction
        from core.engine import MacroEngine

        engine = MacroEngine()
        engine.load_actions([DelayAction(duration_ms=50)] * 20)
        engine.set_loop(count=0, delay_ms=0)
        engine.start()

        # Rapid pause/resume cycles
        for _ in range(10):
            engine.pause()
            time.sleep(0.01)
            engine.resume()
            time.sleep(0.01)

        engine.stop()
        engine.wait(3000)
        assert not engine.isRunning()

    def test_stop_during_pause_no_deadlock(self):
        """L1: Stop while paused must not deadlock."""
        from core.action import DelayAction
        from core.engine import MacroEngine

        engine = MacroEngine()
        engine.load_actions([DelayAction(duration_ms=100)] * 20)
        engine.set_loop(count=0, delay_ms=0)
        engine.start()
        time.sleep(0.05)

        engine.pause()
        time.sleep(0.05)
        engine.stop()  # Must not deadlock
        finished = engine.wait(3000)
        assert finished


class TestEngineContextReset:
    """L6: Global state must be resettable for test isolation."""

    def test_reset_globals_exists(self):
        """L6: reset_globals() function must exist."""
        from core.engine_context import reset_globals
        assert callable(reset_globals)

    def test_reset_globals_resets_speed(self):
        """L6: reset_globals() must reset global speed to 1.0."""
        from core.engine_context import get_speed, reset_globals, set_speed

        set_speed(2.5)
        assert get_speed() == 2.5

        reset_globals()
        assert get_speed() == 1.0
