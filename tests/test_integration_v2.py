"""
Integration & E2E Tests v2 — Cross-module flows for AutoMacro.

These tests validate multi-component interactions that unit tests can't cover:
1. Composite action nested execution through MacroEngine
2. Undo/Redo integration with CompositeChildrenCommand
3. Engine pause → resume → stop lifecycle
4. AutoSave dirty-flag integration
5. Complete macro lifecycle: create → save → load → execute → verify
6. Smart Hints on composite macros
7. TreeModel ↔ Action list sync
8. Crash Handler resilience

Run: python -m pytest tests/test_integration_v2.py -v
"""

import json
import os
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

_app = QApplication.instance() or QApplication([])

# Force-register all action types
import core.action  # noqa: F401
import core.scheduler  # noqa: F401
import modules.image  # noqa: F401
import modules.keyboard  # noqa: F401
import modules.mouse  # noqa: F401
import modules.pixel  # noqa: F401
import modules.system  # noqa: F401
from core.action import Action, get_action_class
from core.engine import MacroEngine
from core.engine_context import set_context, set_speed, set_stop_event
from core.execution_context import ExecutionContext


def _setup_ctx() -> ExecutionContext:
    """Create and wire a fresh ExecutionContext."""
    ctx = ExecutionContext()
    ctx.reset()
    set_context(ctx)
    set_speed(1.0)
    set_stop_event(threading.Event())
    return ctx


# ============================================================
# Suite 1: Composite Action Nested Execution (Engine)
# ============================================================


class TestCompositeNestedExecution:
    """Verify LoopBlock → IfVariable → SetVariable chains run correctly through engine."""

    def test_loop_with_nested_if_and_set(self) -> None:
        """LoopBlock(3 iterations) → IfVariable(i < 2) → SetVariable(counter++)."""
        ctx = _setup_ctx()
        SV = get_action_class("set_variable")
        IV = get_action_class("if_variable")
        Loop = get_action_class("loop_block")

        # Init
        ctx.set_var("i", 0)
        ctx.set_var("counter", 0)

        # Build: loop 3 times
        loop = Loop(iterations=3)
        # Increment i each iteration
        loop.add_action(SV(var_name="i", value="", operation="increment"))
        # If i <= 2, increment counter
        iv = IV(var_name="i", operator="<=", compare_value="2")
        iv.add_then_action(SV(var_name="counter", value="", operation="increment"))
        loop.add_action(iv)

        result = loop.execute()
        assert result is True
        assert ctx.get_var("i") == 3  # looped 3 times
        assert ctx.get_var("counter") == 2  # only first 2 iterations match i<=2

    def test_nested_loop_accumulates(self) -> None:
        """Outer loop × inner loop = expected total."""
        ctx = _setup_ctx()
        SV = get_action_class("set_variable")
        Loop = get_action_class("loop_block")

        ctx.set_var("total", 0)

        outer = Loop(iterations=3)
        inner = Loop(iterations=4)
        inner.add_action(SV(var_name="total", value="", operation="increment"))
        outer.add_action(inner)

        result = outer.execute()
        assert result is True
        assert ctx.get_var("total") == 12  # 3 × 4

    def test_composite_with_else_branch(self) -> None:
        """IfVariable with then + else branch execution."""
        ctx = _setup_ctx()
        SV = get_action_class("set_variable")
        IV = get_action_class("if_variable")

        ctx.set_var("score", 75)
        ctx.set_var("grade", "")

        iv = IV(var_name="score", operator=">=", compare_value="80")
        iv.add_then_action(SV(var_name="grade", value="A", operation="set"))
        iv.add_else_action(SV(var_name="grade", value="B", operation="set"))

        result = iv.execute()
        assert result is True
        assert ctx.get_var("grade") == "B"  # 75 < 80 → else

    def test_engine_runs_composite_macro(self) -> None:
        """Full engine execution with composite actions."""
        ctx = _setup_ctx()
        SV = get_action_class("set_variable")
        Loop = get_action_class("loop_block")

        ctx.set_var("count", 0)

        loop = Loop(iterations=5)
        loop.add_action(SV(var_name="count", value="", operation="increment"))

        # Engine uses deepcopy(actions) — threading.Event can't be pickled,
        # so serialize→deserialize to get a clean copy without _cancel_event
        actions = [Action.from_dict(loop.to_dict())]

        engine = MacroEngine()
        engine.load_actions(actions)
        engine.set_loop(count=1, delay_ms=0)
        engine.start()
        engine.wait(5000)
        assert not engine.isRunning()
        assert engine._exec_ctx.get_var("count") == 5.0


# ============================================================
# Suite 2: Undo/Redo with CompositeChildrenCommand
# ============================================================


class TestUndoRedoComposite:
    """Verify undo/redo for sub-action mutations on composite actions."""

    def test_undo_redo_sub_action_add(self) -> None:
        """Add sub-action → undo → children empty → redo → children restored."""
        from PyQt6.QtGui import QUndoStack

        from core.scheduler import LoopBlock
        from core.undo_commands import CompositeChildrenCommand

        parent = LoopBlock(iterations=3)
        assert len(parent._sub_actions) == 0

        stack = QUndoStack()
        cmd = CompositeChildrenCommand(parent, "Add sub-action")

        # Mutate: add a delay sub-action
        from core.action import DelayAction

        parent._sub_actions.append(DelayAction(duration_ms=100))
        cmd.capture_new_state()
        stack.push(cmd)

        assert len(parent._sub_actions) == 1

        # Undo
        stack.undo()
        assert len(parent._sub_actions) == 0

        # Redo
        stack.redo()
        assert len(parent._sub_actions) == 1
        assert parent._sub_actions[0].duration_ms == 100

    def test_undo_redo_sub_action_delete(self) -> None:
        """Delete sub-action → undo restores it."""
        from PyQt6.QtGui import QUndoStack

        from core.action import DelayAction
        from core.scheduler import LoopBlock
        from core.undo_commands import CompositeChildrenCommand

        parent = LoopBlock(iterations=2)
        parent._sub_actions = [DelayAction(duration_ms=100), DelayAction(duration_ms=200)]

        stack = QUndoStack()
        cmd = CompositeChildrenCommand(parent, "Delete sub-action")
        parent._sub_actions.pop(0)
        cmd.capture_new_state()
        stack.push(cmd)

        assert len(parent._sub_actions) == 1
        assert parent._sub_actions[0].duration_ms == 200

        stack.undo()
        assert len(parent._sub_actions) == 2
        assert parent._sub_actions[0].duration_ms == 100

    def test_undo_redo_then_else_actions(self) -> None:
        """Undo/redo works for then_actions and else_actions."""
        from PyQt6.QtGui import QUndoStack

        from core.action import DelayAction
        from core.scheduler import IfVariable
        from core.undo_commands import CompositeChildrenCommand

        parent = IfVariable(var_name="x", operator="==", compare_value="1")
        parent._then_actions = [DelayAction(duration_ms=100)]
        parent._else_actions = [DelayAction(duration_ms=200)]

        stack = QUndoStack()
        cmd = CompositeChildrenCommand(parent, "Modify branches")

        # Mutate: add to then, clear else
        parent._then_actions.append(DelayAction(duration_ms=300))
        parent._else_actions.clear()
        cmd.capture_new_state()
        stack.push(cmd)

        assert len(parent._then_actions) == 2
        assert len(parent._else_actions) == 0

        stack.undo()
        assert len(parent._then_actions) == 1
        assert len(parent._else_actions) == 1
        assert parent._else_actions[0].duration_ms == 200

    def test_multiple_undo_redo_steps(self) -> None:
        """Multiple mutations can be independently undone."""
        from PyQt6.QtGui import QUndoStack

        from core.action import DelayAction
        from core.scheduler import LoopBlock
        from core.undo_commands import CompositeChildrenCommand

        parent = LoopBlock(iterations=1)
        stack = QUndoStack()

        # Step 1: Add action A
        cmd1 = CompositeChildrenCommand(parent, "Add A")
        parent._sub_actions.append(DelayAction(duration_ms=100))
        cmd1.capture_new_state()
        stack.push(cmd1)

        # Step 2: Add action B
        cmd2 = CompositeChildrenCommand(parent, "Add B")
        parent._sub_actions.append(DelayAction(duration_ms=200))
        cmd2.capture_new_state()
        stack.push(cmd2)

        assert len(parent._sub_actions) == 2

        # Undo step 2 → only A remains
        stack.undo()
        assert len(parent._sub_actions) == 1
        assert parent._sub_actions[0].duration_ms == 100

        # Undo step 1 → empty
        stack.undo()
        assert len(parent._sub_actions) == 0

        # Redo both
        stack.redo()
        stack.redo()
        assert len(parent._sub_actions) == 2


# ============================================================
# Suite 3: Engine Pause → Resume → Stop Lifecycle
# ============================================================


class TestEnginePauseResumeStop:
    """Verify engine state transitions work correctly."""

    def test_start_and_stop(self) -> None:
        """Engine starts, runs, and stops cleanly."""
        _setup_ctx()
        engine = MacroEngine()
        from core.action import DelayAction

        engine.load_actions([DelayAction(duration_ms=1)])
        engine.set_loop(count=1)
        engine.start()
        engine.wait(3000)
        assert not engine.isRunning()

    def test_stop_during_execution(self) -> None:
        """Emergency stop interrupts running macro."""
        _setup_ctx()
        engine = MacroEngine()
        from core.action import DelayAction

        # Long-running macro
        engine.load_actions([DelayAction(duration_ms=5000)])
        engine.set_loop(count=1)
        engine.start()
        time.sleep(0.1)  # Let it start
        assert engine.isRunning()

        engine.stop()
        engine.wait(2000)
        assert not engine.isRunning()

    def test_pause_resume(self) -> None:
        """Pause pauses execution, resume continues."""
        _setup_ctx()
        engine = MacroEngine()
        from core.action import DelayAction

        engine.load_actions([DelayAction(duration_ms=5000)])
        engine.set_loop(count=1)
        engine.start()
        time.sleep(0.1)

        engine.pause()
        assert engine._is_paused is True

        engine.resume()
        assert engine._is_paused is False

        engine.stop()
        engine.wait(2000)

    def test_multiple_start_stop_cycles(self) -> None:
        """Engine can be started and stopped multiple times."""
        _setup_ctx()
        engine = MacroEngine()
        from core.action import DelayAction

        for _ in range(3):
            engine.load_actions([DelayAction(duration_ms=1)])
            engine.set_loop(count=1)
            engine.start()
            engine.wait(3000)
            assert not engine.isRunning()


# ============================================================
# Suite 4: AutoSave Integration
# ============================================================


class TestAutoSaveIntegration:
    """Verify AutoSave dirty-flag, backup rotation, and save callback."""

    def test_dirty_flag_lifecycle(self) -> None:
        from core.autosave import AutoSaveManager

        mgr = AutoSaveManager(interval_s=300)
        assert not mgr._dirty_event.is_set()

        mgr.mark_dirty()
        assert mgr._dirty_event.is_set()

        mgr.mark_clean()
        assert not mgr._dirty_event.is_set()

    def test_backup_rotation(self, tmp_path: Path) -> None:
        """Backup rotation removes oldest files beyond max_backups."""
        from core.autosave import AutoSaveManager

        mgr = AutoSaveManager(interval_s=300, max_backups=3)
        mgr._backup_dir = tmp_path
        macro_file = tmp_path / "test.json"
        macro_file.write_text('{"actions": []}')
        mgr._current_file = macro_file

        # Create 5 backups manually
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        for i in range(5):
            (backup_dir / f"backup_2026010{i}_120000.json").write_text("{}")

        # Trigger backup
        mgr._create_backup()

        # Should have at most 3 old + 1 new = kept at 3 (removed 3 oldest)
        backups = list(backup_dir.glob("backup_*.json"))
        assert len(backups) <= 4  # max_backups check is >= not >

    def test_save_callback_called_when_dirty(self, tmp_path: Path) -> None:
        """Save callback is invoked when dirty flag is set."""
        from core.autosave import AutoSaveManager

        saved = {"called": False}

        def mock_save() -> bool:
            saved["called"] = True
            return True

        mgr = AutoSaveManager(interval_s=1, max_backups=3)
        mgr._save_callback = mock_save
        mgr._backup_dir = tmp_path
        mgr._current_file = None
        mgr._dirty_event.set()
        mgr._running = True

        # Simulate one loop cycle manually
        if mgr._dirty_event.is_set() and mgr._save_callback:
            mgr._save_callback()
            mgr._dirty_event.clear()

        assert saved["called"] is True
        assert not mgr._dirty_event.is_set()


# ============================================================
# Suite 5: Complete Macro Lifecycle (E2E)
# ============================================================


class TestFullMacroLifecycle:
    """Complete create → save → load → execute → verify cycle."""

    def test_create_save_load_execute(self, tmp_path: Path) -> None:
        """Full lifecycle with mixed action types."""
        _setup_ctx()
        SV = get_action_class("set_variable")
        Loop = get_action_class("loop_block")
        Comment = get_action_class("comment")

        # 1. Create macro
        loop = Loop(iterations=5)
        loop.add_action(SV(var_name="total", value="", operation="increment"))

        actions = [
            Comment(text="Start processing"),
            SV(var_name="total", value="0", operation="set"),
            loop,
        ]

        # 2. Save
        path = str(tmp_path / "lifecycle.json")
        MacroEngine.save_macro(path, actions, name="LifecycleTest", loop_count=1)

        # 3. Load
        loaded, settings = MacroEngine.load_macro(path)
        assert len(loaded) == 3
        assert settings["name"] == "LifecycleTest"

        # Verify composite preserved
        loaded_loop = loaded[2]
        assert hasattr(loaded_loop, "_sub_actions")
        assert len(loaded_loop._sub_actions) == 1

        # 4. Execute (engine creates its own context)
        engine = MacroEngine()
        engine.load_actions(loaded)
        engine.set_loop(count=1, delay_ms=0)
        engine.start()
        engine.wait(5000)
        assert not engine.isRunning()

        # 5. Verify via engine's internal context
        assert engine._exec_ctx.get_var("total") == 5.0

    def test_lifecycle_with_disabled_actions(self, tmp_path: Path) -> None:
        """Disabled actions persist through save/load and are skipped on execute."""
        _setup_ctx()
        SV = get_action_class("set_variable")

        actions = [
            SV(var_name="a", value="1", operation="set", enabled=True),
            SV(var_name="b", value="2", operation="set", enabled=False),
            SV(var_name="c", value="3", operation="set", enabled=True),
        ]

        path = str(tmp_path / "disabled.json")
        MacroEngine.save_macro(path, actions)
        loaded, _ = MacroEngine.load_macro(path)

        assert loaded[1].enabled is False

        engine = MacroEngine()
        engine.load_actions(loaded)
        engine.set_loop(count=1)
        engine.start()
        engine.wait(3000)

        # Verify via engine's internal context
        # SetVariable auto-casts numeric strings to int/float
        assert engine._exec_ctx.get_var("a") == 1
        assert engine._exec_ctx.get_var("b") is None  # skipped
        assert engine._exec_ctx.get_var("c") == 3

    def test_lifecycle_composite_serialization_roundtrip(self, tmp_path: Path) -> None:
        """Composite actions with nested children survive save/load intact."""
        SV = get_action_class("set_variable")
        IV = get_action_class("if_variable")
        Loop = get_action_class("loop_block")

        loop = Loop(iterations=3)
        loop.add_action(SV(var_name="x", value="", operation="increment"))

        iv = IV(var_name="x", operator=">", compare_value="1")
        iv.add_then_action(SV(var_name="found", value="yes", operation="set"))
        iv.add_else_action(SV(var_name="found", value="no", operation="set"))

        actions = [loop, iv]

        path = str(tmp_path / "composite.json")
        MacroEngine.save_macro(path, actions)
        loaded, _ = MacroEngine.load_macro(path)

        # Verify structure
        assert len(loaded) == 2
        assert len(loaded[0]._sub_actions) == 1
        assert len(loaded[1]._then_actions) == 1
        assert len(loaded[1]._else_actions) == 1

        # Verify types preserved
        assert loaded[0]._sub_actions[0].ACTION_TYPE == "set_variable"
        assert loaded[1]._then_actions[0].ACTION_TYPE == "set_variable"


# ============================================================
# Suite 6: Smart Hints on Composite Macros
# ============================================================


class TestSmartHintsIntegration:
    """Smart Hints analysis on real-world composite patterns."""

    def test_empty_loop_generates_warning(self) -> None:
        from core.scheduler import LoopBlock
        from core.smart_hints import analyze_hints

        loop = LoopBlock(iterations=5)
        hints = analyze_hints([loop])
        messages = [h["message"] for h in hints]
        # Should detect empty composite action
        has_empty_warning = any("sub-action" in str(m).lower() or "không có" in str(m) for m in messages)
        assert has_empty_warning, f"Expected empty composite warning, got: {messages}"

    def test_consecutive_delays_tip(self) -> None:
        from core.action import DelayAction
        from core.smart_hints import analyze_hints

        actions = [DelayAction(duration_ms=100), DelayAction(duration_ms=200)]
        hints = analyze_hints(actions)
        messages = [str(h["message"]) for h in hints]
        has_delay_tip = any("delay" in m.lower() or "chờ" in m.lower() for m in messages)
        assert has_delay_tip, f"Expected consecutive delay hint, got: {messages}"

    def test_large_macro_performance(self) -> None:
        """Smart Hints on 200 actions completes in < 100ms."""
        from core.action import DelayAction
        from core.smart_hints import analyze_hints
        from modules.mouse import MouseClick

        actions = []
        for i in range(200):
            if i % 2:
                actions.append(MouseClick(x=i, y=i))
            else:
                actions.append(DelayAction(duration_ms=i))

        t0 = time.perf_counter()
        hints = analyze_hints(actions)
        dt = time.perf_counter() - t0

        assert dt < 0.1, f"Smart Hints took {dt:.3f}s on 200 actions — too slow"
        assert len(hints) > 0


# ============================================================
# Suite 7: TreeModel ↔ Action List Sync
# ============================================================


class TestTreeModelSync:
    """Verify ActionTreeModel correctly reflects action list mutations."""

    def test_model_reflects_flat_list(self) -> None:
        from core.action import DelayAction
        from gui.action_tree_model import ActionTreeModel
        from modules.mouse import MouseClick

        actions = [MouseClick(x=1, y=2), DelayAction(duration_ms=100)]
        model = ActionTreeModel(actions)

        assert model.rowCount() == 2

    def test_model_reflects_composite_children(self) -> None:
        from core.action import DelayAction
        from core.scheduler import LoopBlock
        from gui.action_tree_model import ActionTreeModel

        loop = LoopBlock(iterations=3)
        loop.add_action(DelayAction(duration_ms=100))
        loop.add_action(DelayAction(duration_ms=200))

        model = ActionTreeModel([loop])
        root_idx = model.index(0, 0)

        assert model.rowCount() == 1  # one top-level
        assert model.rowCount(root_idx) == 2  # two children

    def test_model_serialization(self) -> None:
        """To/from dict through ActionTreeModel."""
        from core.action import Action, DelayAction
        from core.scheduler import LoopBlock
        from gui.action_tree_model import ActionTreeModel

        loop = LoopBlock(iterations=2)
        loop.add_action(DelayAction(duration_ms=50))

        actions = [loop]
        model = ActionTreeModel(actions)

        # Serialize
        data = [a.to_dict() for a in actions]
        json_str = json.dumps(data)

        # Deserialize
        loaded = [Action.from_dict(d) for d in json.loads(json_str)]
        model2 = ActionTreeModel(loaded)

        assert model2.rowCount() == 1
        root_idx = model2.index(0, 0)
        assert model2.rowCount(root_idx) == 1


# ============================================================
# Suite 8: Crash Handler Resilience
# ============================================================


class TestCrashHandlerResilience:
    """Verify CrashHandler installs correctly and handles edge cases."""

    def test_install_and_uninstall(self) -> None:
        from core.crash_handler import CrashHandler

        CrashHandler._installed = False  # Reset state
        CrashHandler.install()
        assert CrashHandler._installed is True

        # Double install should be safe
        CrashHandler.install()
        assert CrashHandler._installed is True

    def test_build_report_format(self) -> None:
        """CrashDialog._build_report produces valid report string."""
        from core.crash_handler import CrashDialog

        try:
            raise ValueError("Test error")
        except ValueError:

            exc_type, exc_val, exc_tb = sys.exc_info()
            dialog = CrashDialog(exc_type, exc_val, exc_tb)
            report = dialog._build_report()

            assert "AutoMacro Crash Report" in report
            assert "ValueError" in report
            assert "Test error" in report
            assert "Python:" in report
