"""
WP3: Performance Benchmarks — using pytest-benchmark.
WP4: AutoSave integration tests.
WP5: Engine stress tests.

Run benchmarks:  python -m pytest tests/test_benchmarks.py --benchmark-only
Run all:         python -m pytest tests/test_benchmarks.py -v
"""

import os
import sys
import time
from pathlib import Path
from typing import Any
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication, QTableWidget
from PyQt6.QtCore import Qt

_app = QApplication.instance() or QApplication([])

import core.action       # noqa: F401
import modules.mouse     # noqa: F401
import modules.keyboard  # noqa: F401
import modules.image     # noqa: F401
import modules.pixel     # noqa: F401
import core.scheduler    # noqa: F401


# ============================================================
# WP3: Performance Benchmarks
# ============================================================

class TestBenchmarks:
    """Performance regression guards using pytest-benchmark."""

    def test_bench_save_100_actions(self, benchmark: Any,
                                    tmp_path: Path) -> None:
        from core.engine import MacroEngine
        from core.action import DelayAction

        actions = [DelayAction(duration_ms=i) for i in range(100)]
        path = str(tmp_path / "bench_save.json")

        benchmark(MacroEngine.save_macro, path, actions)

    def test_bench_load_100_actions(self, benchmark: Any,
                                    tmp_path: Path) -> None:
        from core.engine import MacroEngine
        from core.action import DelayAction

        actions = [DelayAction(duration_ms=i) for i in range(100)]
        path = str(tmp_path / "bench_load.json")
        MacroEngine.save_macro(path, actions)

        benchmark(MacroEngine.load_macro, path)

    def test_bench_serialize_roundtrip_100(self, benchmark: Any) -> None:
        from core.action import Action, DelayAction

        actions = [DelayAction(duration_ms=i) for i in range(100)]
        dicts = [a.to_dict() for a in actions]

        def roundtrip() -> None:
            for d in dicts:
                Action.from_dict(d)

        benchmark(roundtrip)

    def test_bench_refresh_table_100(self, benchmark: Any) -> None:
        from gui.main_window import MainWindow
        from core.action import DelayAction
        from PyQt6.QtWidgets import QLabel, QSpinBox

        with patch.object(MainWindow, '__init__', lambda self: None):
            mw = MainWindow.__new__(MainWindow)
        mw._table = QTableWidget(0, 6)
        mw._actions = [DelayAction(duration_ms=i) for i in range(100)]
        mw._stats_label = QLabel("")
        mw._empty_overlay = QLabel("")
        mw._loop_spin = QSpinBox()
        mw._loop_spin.setValue(1)

        benchmark(mw._refresh_table)

    def test_bench_engine_load_1000(self, benchmark: Any) -> None:
        from core.engine import MacroEngine
        from core.action import DelayAction

        actions = [DelayAction(duration_ms=i) for i in range(1000)]
        engine = MacroEngine()

        benchmark(engine.load_actions, actions)


# ============================================================
# WP4: AutoSave Integration
# ============================================================

class TestAutoSaveIntegration:
    """Test AutoSaveManager dirty/clean lifecycle."""

    def test_mark_dirty_triggers_callback(self) -> None:
        from core.autosave import AutoSaveManager

        called: list[bool] = []

        def save_cb() -> bool:
            called.append(True)
            return True

        mgr = AutoSaveManager(interval_s=0.1, max_backups=1)
        mgr.start(save_callback=save_cb,
                   backup_dir=Path(os.path.join("macros")))
        mgr.mark_dirty()

        # Wait for the timer to fire
        time.sleep(0.3)
        mgr.stop()

        assert len(called) >= 1

    def test_mark_clean_prevents_save(self) -> None:
        from core.autosave import AutoSaveManager

        called: list[bool] = []

        def save_cb() -> bool:
            called.append(True)
            return True

        mgr = AutoSaveManager(interval_s=0.1, max_backups=1)
        mgr.start(save_callback=save_cb,
                   backup_dir=Path(os.path.join("macros")))
        mgr.mark_dirty()
        mgr.mark_clean()  # immediately clean

        time.sleep(0.3)
        mgr.stop()

        assert len(called) == 0

    def test_stop_cancels_timer(self) -> None:
        from core.autosave import AutoSaveManager

        called: list[bool] = []

        def save_cb() -> bool:
            called.append(True)
            return True

        mgr = AutoSaveManager(interval_s=0.1, max_backups=1)
        mgr.start(save_callback=save_cb,
                   backup_dir=Path(os.path.join("macros")))
        mgr.mark_dirty()
        mgr.stop()  # stop immediately

        time.sleep(0.3)
        # Should not have fired after stop
        assert len(called) == 0


# ============================================================
# WP5: Engine Stress Tests
# ============================================================

class TestEngineStress:
    """Verify engine stability under pressure."""

    def test_rapid_3_cycles(self) -> None:
        from core.engine import MacroEngine
        from core.action import DelayAction

        for _ in range(3):
            engine = MacroEngine()
            engine.load_actions([DelayAction(duration_ms=10)])
            engine.set_loop(count=1)
            engine.start()
            engine.wait(5000)
            assert not engine.isRunning()

    def test_exception_in_action_handled(self) -> None:
        from core.engine import MacroEngine
        from core.action import Action

        # Mock action that raises
        boom = MagicMock(spec=Action)
        boom.enabled = True
        boom.repeat_count = 1
        boom.delay_after = 0
        boom.run.side_effect = RuntimeError("BOOM")
        boom.get_display_name.return_value = "BoomAction"

        engine = MacroEngine()
        engine._actions = [boom]
        engine.set_loop(count=1)

        errors: list[str] = []
        engine.error_signal.connect(lambda e: errors.append(e))

        engine.start()
        engine.wait(5000)
        for _ in range(20):
            _app.processEvents()
            time.sleep(0.01)

        assert not engine.isRunning()
        assert len(errors) >= 1

    def test_engine_empty_actions_clean_stop(self) -> None:
        from core.engine import MacroEngine

        engine = MacroEngine()
        engine.load_actions([])
        engine.set_loop(count=1)
        engine.start()
        engine.wait(5000)
        assert not engine.isRunning()

    def test_loop_delay_interruptible(self) -> None:
        from core.engine import MacroEngine
        from core.action import DelayAction

        engine = MacroEngine()
        engine.load_actions([DelayAction(duration_ms=1)])
        engine.set_loop(count=0, delay_ms=5000)  # 5s loop delay, infinite

        engine.start()
        time.sleep(0.2)  # let first loop complete + enter delay
        engine.stop()
        engine.wait(3000)

        assert not engine.isRunning(), "Should interrupt loop delay"
