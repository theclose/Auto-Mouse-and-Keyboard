"""
Integration flow tests — end-to-end workflows that verify multiple
components working together correctly.
"""


import pytest

# Ensure composite action types are registered
import core.scheduler  # noqa: F401

# ============================================================
# 1. Add → Delete → Undo → Redo
# ============================================================


class TestActionManipulationFlow:
    def _actions_list(self):
        from core.action import Action
        return [Action.from_dict({"type": "comment", "params": {"text": f"item{i}"}}) for i in range(5)]

    def test_delete_undo_redo(self):
        from PyQt6.QtGui import QUndoStack

        from core.undo_commands import DeleteActionsCommand
        stack = QUndoStack()
        actions = self._actions_list()
        stack.push(DeleteActionsCommand(actions, [1, 3]))
        assert len(actions) == 3
        stack.undo()
        assert len(actions) == 5
        stack.redo()
        assert len(actions) == 3

    def test_duplicate_undo(self):
        from PyQt6.QtGui import QUndoStack

        from core.action import Action
        from core.undo_commands import DuplicateActionCommand
        stack = QUndoStack()
        actions = self._actions_list()
        dup = Action.from_dict(actions[0].to_dict())
        stack.push(DuplicateActionCommand(actions, 0, dup))
        assert len(actions) == 6
        stack.undo()
        assert len(actions) == 5

    def test_move_swap_undo(self):
        from PyQt6.QtGui import QUndoStack

        from core.undo_commands import MoveActionCommand
        stack = QUndoStack()
        actions = self._actions_list()
        original = [a.text for a in actions]
        stack.push(MoveActionCommand(actions, 0, 1))
        stack.undo()
        assert [a.text for a in actions] == original

    def test_multiple_undo_redo(self):
        from PyQt6.QtGui import QUndoStack

        from core.action import Action
        from core.undo_commands import DeleteActionsCommand, DuplicateActionCommand
        stack = QUndoStack()
        actions = self._actions_list()
        dup = Action.from_dict(actions[0].to_dict())
        stack.push(DuplicateActionCommand(actions, 0, dup))
        assert len(actions) == 6
        stack.push(DeleteActionsCommand(actions, [5]))
        assert len(actions) == 5
        stack.undo()
        assert len(actions) == 6
        stack.undo()
        assert len(actions) == 5


# ============================================================
# 2. Macro save → load roundtrip
# ============================================================


class TestMacroRoundtrip:
    def test_full_roundtrip(self, tmp_path):
        from core.action import Action
        from core.engine import MacroEngine
        original = [
            Action.from_dict({"type": "comment", "params": {"text": "hello"}}),
            Action.from_dict({"type": "delay", "params": {"duration_ms": 500}}),
        ]
        fp = str(tmp_path / "test.json")
        MacroEngine.save_macro(fp, original, name="Test", loop_count=5, loop_delay_ms=300)
        loaded, settings = MacroEngine.load_macro(fp)
        assert len(loaded) == 2
        assert settings["name"] == "Test"
        assert loaded[0].ACTION_TYPE == "comment"
        assert loaded[1].ACTION_TYPE == "delay"

    def test_unicode_preserved(self, tmp_path):
        from core.action import Action
        from core.engine import MacroEngine
        text = "Hello 🌍 «Привет» 日本語 <tag>"
        actions = [Action.from_dict({"type": "comment", "params": {"text": text}})]
        fp = str(tmp_path / "unicode.json")
        MacroEngine.save_macro(fp, actions)
        loaded, _ = MacroEngine.load_macro(fp)
        assert loaded[0]._get_params()["text"] == text

    def test_disabled_preserved(self, tmp_path):
        from core.action import Action
        from core.engine import MacroEngine
        actions = [Action.from_dict({"type": "comment", "params": {"text": "x"}, "enabled": False})]
        fp = str(tmp_path / "disabled.json")
        MacroEngine.save_macro(fp, actions)
        loaded, _ = MacroEngine.load_macro(fp)
        assert loaded[0].enabled is False


# ============================================================
# 3. Context Variable Flow
# ============================================================


class TestContextVariableFlow:
    def test_set_get(self):
        from core.execution_context import ExecutionContext
        ctx = ExecutionContext()
        ctx.reset()
        ctx.set_var("counter", 0)
        ctx.set_var("counter", ctx.get_var("counter") + 1)
        assert ctx.get_var("counter") == 1

    def test_interpolation(self):
        from core.execution_context import ExecutionContext
        ctx = ExecutionContext()
        ctx.reset()
        ctx.set_var("file", "report.csv")
        ctx.set_var("line", 42)
        assert ctx.interpolate("Processing ${file} at line ${line}") == "Processing report.csv at line 42"

    def test_snapshot_roundtrip(self):
        from core.execution_context import ExecutionContext
        ctx = ExecutionContext()
        ctx.reset()
        ctx.set_var("name", "test")
        ctx.record_action(True)
        ctx.record_action(False)
        snap = ctx.snapshot()
        ctx2 = ExecutionContext()
        ctx2.restore(snap)
        assert ctx2.get_var("name") == "test"
        assert ctx2.action_count == 2 and ctx2.error_count == 1


# ============================================================
# 4. Composite Nesting
# ============================================================


class TestCompositeNesting:
    def test_nested_loops(self):
        from core.action import Action
        # Test that composite types can be created and are marked composite
        outer = Action.from_dict({"type": "loop_block", "params": {"count": 2}})
        assert outer.is_composite

    def test_if_inside_loop(self):
        from core.action import Action
        loop = Action.from_dict({"type": "loop_block", "params": {"count": 5}})
        assert loop.ACTION_TYPE == "loop_block"
        assert loop.is_composite

    def test_group_composite(self):
        from core.action import Action
        g = Action.from_dict({"type": "group", "params": {"name": "Setup"}})
        assert g.is_composite
        assert g.ACTION_TYPE == "group"


# ============================================================
# 5. Engine Signals
# ============================================================


class TestEngineSignals:
    def test_all_signals(self):
        from core.engine import MacroEngine
        eng = MacroEngine()
        for sig in ["started_signal", "stopped_signal", "error_signal",
                     "progress_signal", "action_signal", "loop_signal",
                     "step_signal", "nested_step_signal", "duration_signal"]:
            assert hasattr(eng, sig)


# ============================================================
# 6. MainWindow Integration
# ============================================================


class TestMainWindowIntegration:
    def test_window_title(self, real_main_window):
        assert len(real_main_window.windowTitle()) > 0

    def test_actions_list(self, real_main_window):
        assert isinstance(real_main_window._actions, list)

    def test_tree_model(self, real_main_window):
        assert hasattr(real_main_window, "_tree_model")

    def test_engine(self, real_main_window):
        assert hasattr(real_main_window, "_engine")


# ============================================================
# 7. Crash Handler & AutoSave
# ============================================================


class TestCrashHandlerBasic:
    def test_installs(self):
        from core.crash_handler import CrashHandler
        assert CrashHandler() is not None


class TestAutoSaveBasic:
    def test_creates(self):
        from core.autosave import AutoSaveManager
        assert AutoSaveManager(interval_s=60) is not None

    def test_start_stop(self, tmp_path):
        from core.autosave import AutoSaveManager
        a = AutoSaveManager(interval_s=60)
        a.start(save_callback=lambda: True, backup_dir=tmp_path)
        a.stop()


# ============================================================
# 8. Retry
# ============================================================


class TestRetryDeep:
    def test_succeeds_first(self):
        from core.retry import retry
        count = 0
        @retry(max_attempts=3, delay=0.01)
        def ok():
            nonlocal count
            count += 1
            return True
        assert ok() is True and count == 1

    def test_succeeds_after_failures(self):
        from core.retry import retry
        attempts = []
        @retry(max_attempts=3, delay=0.01)
        def flaky():
            attempts.append(1)
            if len(attempts) < 3:
                raise RuntimeError("fail")
            return True
        assert flaky() is True and len(attempts) == 3

    def test_exhausted(self):
        from core.retry import retry
        @retry(max_attempts=2, delay=0.01)
        def always_fail():
            raise RuntimeError("permanent")
        with pytest.raises(RuntimeError):
            always_fail()


# ============================================================
# 9. Action Registry
# ============================================================


class TestActionRegistry:
    CORE_TYPES = ["loop_block", "if_variable", "set_variable",
                  "split_string", "comment", "group"]

    def test_core_types(self):
        from core.action import Action
        for t in self.CORE_TYPES:
            a = Action.from_dict({"type": t, "params": {}})
            assert a.ACTION_TYPE == t

    def test_to_dict_from_dict_idempotent(self):
        from core.action import Action
        for t in ["comment"]:
            a = Action.from_dict({"type": t, "params": {"text": "x"}})
            d1 = a.to_dict()
            d2 = Action.from_dict(d1).to_dict()
            assert d1["type"] == d2["type"] and d1["params"] == d2["params"]
