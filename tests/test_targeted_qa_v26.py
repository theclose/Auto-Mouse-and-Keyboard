"""
Targeted QA Tests — v2.5.0 / v2.6.0 Changes

Covers all 3 tiers:
  Tier 1: Engine checkpoint, resume, schema validation
  Tier 2: Window activation, safe eval, narrowed exceptions
  Tier 3: Step debug, variable inspector, IfImageFound builder

Run: python -m pytest tests/test_targeted_qa_v26.py -v
"""

import json
import os
import sys
import tempfile
import threading
from pathlib import Path
from typing import Any
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

_app = QApplication.instance() or QApplication([])

import modules.mouse      # noqa: F401
import modules.keyboard   # noqa: F401
import modules.image      # noqa: F401
import modules.pixel      # noqa: F401
import modules.system     # noqa: F401
import core.scheduler      # noqa: F401

from core.action import Action, get_action_class
from core.execution_context import ExecutionContext


# ============================================================
# TIER 1: Engine Checkpoint / Resume
# ============================================================

class TestCheckpointRestore:
    """1.1: ExecutionContext snapshot/restore roundtrip."""

    def test_snapshot_captures_variables(self) -> None:
        ctx = ExecutionContext()
        ctx.reset()
        ctx.set_var("counter", 42)
        ctx.set_var("name", "hello")
        ctx.iteration_count = 5
        ctx.action_count = 10
        ctx.error_count = 2

        snap = ctx.snapshot()
        assert snap["variables"]["counter"] == 42
        assert snap["variables"]["name"] == "hello"
        assert snap["iteration_count"] == 5
        assert snap["action_count"] == 10
        assert snap["error_count"] == 2

    def test_restore_overwrites_state(self) -> None:
        ctx = ExecutionContext()
        ctx.reset()
        ctx.set_var("old_var", "should_be_gone")

        snap = {
            "variables": {"restored": "yes", "count": 99},
            "iteration_count": 7,
            "action_count": 20,
            "error_count": 1,
            "last_image_match": None,
            "last_pixel_color": None,
        }
        ctx.restore(snap)

        assert ctx.get_var("restored") == "yes"
        assert ctx.get_var("count") == 99
        assert ctx.get_var("old_var") is None  # overwritten
        assert ctx.iteration_count == 7
        assert ctx.action_count == 20

    def test_snapshot_restore_roundtrip(self) -> None:
        ctx = ExecutionContext()
        ctx.reset()
        ctx.set_var("x", 3.14)
        ctx.set_var("flag", True)
        ctx.iteration_count = 100

        snap = ctx.snapshot()
        ctx.reset()  # wipe
        assert ctx.get_var("x") is None

        ctx.restore(snap)
        assert ctx.get_var("x") == 3.14
        assert ctx.get_var("flag") is True
        assert ctx.iteration_count == 100

    def test_snapshot_is_independent_copy(self) -> None:
        """Modifying snapshot dict should not affect context."""
        ctx = ExecutionContext()
        ctx.reset()
        ctx.set_var("a", 1)
        snap = ctx.snapshot()
        snap["variables"]["a"] = 999  # mutate snapshot
        assert ctx.get_var("a") == 1  # original unchanged

    def test_restore_with_empty_snapshot(self) -> None:
        ctx = ExecutionContext()
        ctx.reset()
        ctx.set_var("keep", "this")
        ctx.restore({})  # empty snapshot
        assert ctx.get_var("keep") is None  # variables cleared
        assert ctx.iteration_count == 0


class TestEngineResume:
    """1.2: Engine resume skips actions before resume index."""

    def test_engine_has_checkpoint_methods(self) -> None:
        from core.engine import MacroEngine
        engine = MacroEngine()
        assert hasattr(engine, 'get_last_checkpoint')
        assert hasattr(engine, 'resume_from_checkpoint')
        assert callable(engine.get_last_checkpoint)
        assert callable(engine.resume_from_checkpoint)

    def test_resume_from_checkpoint_sets_index(self) -> None:
        from core.engine import MacroEngine
        engine = MacroEngine()
        engine._exec_ctx = ExecutionContext()
        engine._last_checkpoint = {
            "action_idx": 5,
            "context": {"variables": {"x": 10}, "iteration_count": 3,
                        "action_count": 5, "error_count": 0},
        }
        engine.resume_from_checkpoint()
        assert engine._resume_from_idx == 5

    def test_resume_without_checkpoint_resets(self) -> None:
        from core.engine import MacroEngine
        engine = MacroEngine()
        engine._last_checkpoint = None
        engine.resume_from_checkpoint()
        assert engine._resume_from_idx == 0


# ============================================================
# TIER 1: Schema Validation
# ============================================================

class TestSchemaValidation:
    """1.3: Macro load validates structure."""

    def test_load_valid_macro(self, tmp_path: Path) -> None:
        from core.engine import MacroEngine
        macro = {
            "name": "Test",
            "version": "2.6",
            "settings": {"loop_count": 1},
            "actions": [
                {"type": "delay", "params": {"duration_ms": 100}},
            ]
        }
        fp = tmp_path / "test.json"
        fp.write_text(json.dumps(macro), encoding="utf-8")
        actions, settings = MacroEngine.load_macro(str(fp))
        assert len(actions) == 1
        assert settings["name"] == "Test"

    def test_load_missing_actions_key(self, tmp_path: Path) -> None:
        from core.engine import MacroEngine
        fp = tmp_path / "bad.json"
        fp.write_text('{"name":"Bad"}', encoding="utf-8")
        with pytest.raises(ValueError, match="missing 'actions'"):
            MacroEngine.load_macro(str(fp))

    def test_load_actions_not_list(self, tmp_path: Path) -> None:
        from core.engine import MacroEngine
        fp = tmp_path / "bad2.json"
        fp.write_text('{"actions":"not a list"}', encoding="utf-8")
        with pytest.raises(ValueError, match="must be a list"):
            MacroEngine.load_macro(str(fp))

    def test_load_skips_action_without_type(self, tmp_path: Path) -> None:
        from core.engine import MacroEngine
        macro = {
            "actions": [
                {"params": {"duration_ms": 100}},  # missing type
                {"type": "delay", "params": {"duration_ms": 200}},
            ]
        }
        fp = tmp_path / "partial.json"
        fp.write_text(json.dumps(macro), encoding="utf-8")
        actions, _ = MacroEngine.load_macro(str(fp))
        assert len(actions) == 1  # only valid one

    def test_load_skips_non_dict_action(self, tmp_path: Path) -> None:
        from core.engine import MacroEngine
        macro = {"actions": ["not a dict", {"type": "delay", "params": {"duration_ms": 50}}]}
        fp = tmp_path / "mixed.json"
        fp.write_text(json.dumps(macro), encoding="utf-8")
        actions, _ = MacroEngine.load_macro(str(fp))
        assert len(actions) == 1

    def test_load_invalid_settings_defaults(self, tmp_path: Path) -> None:
        from core.engine import MacroEngine
        macro = {"settings": "broken", "actions": []}
        fp = tmp_path / "bad_settings.json"
        fp.write_text(json.dumps(macro), encoding="utf-8")
        actions, settings = MacroEngine.load_macro(str(fp))
        assert isinstance(settings, dict)  # defaults to {}


# ============================================================
# TIER 2: Safe Eval Expression
# ============================================================

class TestSafeEval:
    """2.2: SetVariable eval operation — AST-based math."""

    def _eval(self, expr: str) -> float:
        cls = get_action_class("set_variable")
        return cls._safe_eval(expr)

    def test_basic_arithmetic(self) -> None:
        assert self._eval("2 + 3") == 5.0
        assert self._eval("10 - 4") == 6.0
        assert self._eval("3 * 7") == 21.0
        assert self._eval("15 / 4") == 3.75

    def test_parentheses(self) -> None:
        assert self._eval("(2 + 3) * 4") == 20.0
        assert self._eval("2 * (3 + 4)") == 14.0

    def test_power_and_modulo(self) -> None:
        assert self._eval("2 ** 10") == 1024.0
        assert self._eval("17 % 5") == 2.0

    def test_floor_division(self) -> None:
        assert self._eval("17 // 3") == 5.0

    def test_negative_numbers(self) -> None:
        assert self._eval("-5") == -5.0
        assert self._eval("-(3 + 2)") == -5.0

    def test_complex_expression(self) -> None:
        result = self._eval("(100 - 20) * 3 / 4 + 5")
        assert abs(result - 65.0) < 0.001

    def test_rejects_function_calls(self) -> None:
        with pytest.raises((ValueError, SyntaxError)):
            self._eval("__import__('os').system('ls')")

    def test_supports_string_literals(self) -> None:
        """v2: String literals are now supported."""
        assert self._eval("'hello'") == "hello"
        assert self._eval("'abc' + 'def'") == "abcdef"

    def test_rejects_variable_names(self) -> None:
        with pytest.raises(ValueError):
            self._eval("x + 1")

    def test_division_by_zero(self) -> None:
        with pytest.raises(ZeroDivisionError):
            self._eval("1 / 0")

    def test_eval_operation_in_context(self) -> None:
        """Test eval operation through full SetVariable.execute()."""
        from core.engine_context import set_context
        ctx = ExecutionContext()
        ctx.reset()
        ctx.set_var("a", "10")
        ctx.set_var("b", "5")
        set_context(ctx)

        cls = get_action_class("set_variable")
        action = cls(var_name="result", value="${a} + ${b} * 2",
                     operation="eval")
        action.execute()
        # ${a}=10, ${b}=5 → "10 + 5 * 2" → 20.0
        assert ctx.get_var("result") == 20.0


# ============================================================
# TIER 2: Multi-Strategy Window Activation
# ============================================================

class TestMultiStrategyWindow:
    """2.1: ActivateWindow uses multiple strategies."""

    def test_has_multi_strategy_method(self) -> None:
        cls = get_action_class("activate_window")
        action = cls(window_title="Test")
        assert hasattr(action, '_activate_multi_strategy')

    def test_strategy1_succeeds(self) -> None:
        """If SetForegroundWindow returns True, stop early."""
        cls = get_action_class("activate_window")
        action = cls(window_title="Notepad")
        with patch("modules.system._user32") as mock_user:
            mock_user.IsIconic.return_value = False
            mock_user.SetForegroundWindow.return_value = True
            result = action._activate_multi_strategy(12345)
        assert result is True
        mock_user.BringWindowToTop.assert_not_called()

    def test_fallback_to_strategy2(self) -> None:
        """If SetForegroundWindow fails, try BringWindowToTop."""
        cls = get_action_class("activate_window")
        action = cls(window_title="Test")
        with patch("modules.system._user32") as mock_user:
            mock_user.IsIconic.return_value = False
            mock_user.SetForegroundWindow.return_value = False
            mock_user.BringWindowToTop.return_value = True
            mock_user.GetForegroundWindow.return_value = 12345
            result = action._activate_multi_strategy(12345)
        assert result is True


# ============================================================
# TIER 2: Narrowed Exceptions in Recorder
# ============================================================

class TestNarrowedExceptions:
    """2.3: Recorder uses specific exceptions, not broad 'except Exception'."""

    def test_click_handler_uses_specific_exceptions(self) -> None:
        """Verify _on_click handler doesn't use broad 'except Exception'."""
        import inspect
        from core.recorder import Recorder
        source = inspect.getsource(Recorder._on_click)
        assert "except Exception" not in source, \
            "_on_click still uses broad 'except Exception'"
        assert "TypeError" in source or "ValueError" in source, \
            "_on_click should catch specific exception types"

    def test_scroll_handler_uses_specific_exceptions(self) -> None:
        """Verify _on_scroll handler doesn't use broad 'except Exception'."""
        import inspect
        from core.recorder import Recorder
        source = inspect.getsource(Recorder._on_scroll)
        assert "except Exception" not in source, \
            "_on_scroll still uses broad 'except Exception'"

    def test_key_handler_uses_specific_exceptions(self) -> None:
        """Verify _on_key_press handler doesn't use broad 'except Exception'."""
        import inspect
        from core.recorder import Recorder
        source = inspect.getsource(Recorder._on_key_press)
        assert "except Exception" not in source, \
            "_on_key_press still uses broad 'except Exception'"

    def test_context_capture_uses_specific_exceptions(self) -> None:
        """Verify _capture_click_context uses specific exceptions."""
        import inspect
        from core.recorder import Recorder
        source = inspect.getsource(Recorder._capture_click_context)
        assert "except Exception" not in source, \
            "_capture_click_context still uses broad 'except Exception'"


# ============================================================
# TIER 3: Step Debug Signals
# ============================================================

class TestStepDebug:
    """3.1: Engine step mode API exists and works."""

    def test_engine_step_mode_api(self) -> None:
        from core.engine import MacroEngine
        engine = MacroEngine()
        assert hasattr(engine, 'set_step_mode')
        assert hasattr(engine, 'step_next')
        assert hasattr(engine, 'step_signal')

    def test_step_mode_toggle(self) -> None:
        from core.engine import MacroEngine
        engine = MacroEngine()
        engine.set_step_mode(True)
        assert engine._step_mode is True
        engine.set_step_mode(False)
        assert engine._step_mode is False


# ============================================================
# TIER 3: IfImageFound Builder
# ============================================================

class TestIfImageFoundBuilder:
    """3.3: IfImageFound editor has all expected param widgets."""

    def test_has_image_path_widget(self) -> None:
        from gui.action_editor import ActionEditorDialog
        dialog = ActionEditorDialog()
        for i in range(dialog._type_combo.count()):
            if dialog._type_combo.itemData(
                    i, Qt.ItemDataRole.UserRole) == "if_image_found":
                dialog._type_combo.setCurrentIndex(i)
                break
        assert "image_path" in dialog._param_widgets, \
            "IfImageFound missing image_path widget"

    def test_has_confidence_widget(self) -> None:
        from gui.action_editor import ActionEditorDialog
        dialog = ActionEditorDialog()
        for i in range(dialog._type_combo.count()):
            if dialog._type_combo.itemData(
                    i, Qt.ItemDataRole.UserRole) == "if_image_found":
                dialog._type_combo.setCurrentIndex(i)
                break
        assert "confidence" in dialog._param_widgets, \
            "IfImageFound missing confidence widget"

    def test_has_timeout_widget(self) -> None:
        from gui.action_editor import ActionEditorDialog
        dialog = ActionEditorDialog()
        for i in range(dialog._type_combo.count()):
            if dialog._type_combo.itemData(
                    i, Qt.ItemDataRole.UserRole) == "if_image_found":
                dialog._type_combo.setCurrentIndex(i)
                break
        assert "timeout_ms" in dialog._param_widgets, \
            "IfImageFound missing timeout_ms widget"

    def test_has_else_action_widget(self) -> None:
        from gui.action_editor import ActionEditorDialog
        dialog = ActionEditorDialog()
        for i in range(dialog._type_combo.count()):
            if dialog._type_combo.itemData(
                    i, Qt.ItemDataRole.UserRole) == "if_image_found":
                dialog._type_combo.setCurrentIndex(i)
                break
        assert "else_action_json" in dialog._param_widgets, \
            "IfImageFound missing else_action_json widget"


class TestLoopBlockBuilder:
    """3.3: LoopBlock editor has iterations widget."""

    def test_has_iterations_widget(self) -> None:
        from gui.action_editor import ActionEditorDialog
        dialog = ActionEditorDialog()
        for i in range(dialog._type_combo.count()):
            if dialog._type_combo.itemData(
                    i, Qt.ItemDataRole.UserRole) == "loop_block":
                dialog._type_combo.setCurrentIndex(i)
                break
        assert "iterations" in dialog._param_widgets, \
            "LoopBlock missing iterations widget"


# ============================================================
# TIER 3: IfVariable ELSE Editor
# ============================================================

class TestIfVariableElseEditor:
    """3.1 ELSE: IfVariable editor has else_action_json widget."""

    def test_has_else_field(self) -> None:
        from gui.action_editor import ActionEditorDialog
        dialog = ActionEditorDialog()
        for i in range(dialog._type_combo.count()):
            if dialog._type_combo.itemData(
                    i, Qt.ItemDataRole.UserRole) == "if_variable":
                dialog._type_combo.setCurrentIndex(i)
                break
        assert "else_action_json" in dialog._param_widgets, \
            "IfVariable missing else_action_json widget"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
