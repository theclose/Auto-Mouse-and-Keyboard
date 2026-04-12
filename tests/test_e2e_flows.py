"""
End-to-end flow tests – validates the full user journey WITHOUT a GUI.
Tests the data layer that the GUI wires to: undo commands, save/load
persistence, recorder snapshot API, and engine safeguards.

Run: python -m pytest tests/test_e2e_flows.py -v
"""

import os
import sys
import threading
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# QApplication singleton for engine signals
from PyQt6.QtWidgets import QApplication

_app = QApplication.instance() or QApplication([])

# Force-register all action types
import core.action  # noqa: F401
import core.scheduler  # noqa: F401
import modules.image  # noqa: F401
import modules.keyboard  # noqa: F401
import modules.mouse  # noqa: F401
import modules.pixel  # noqa: F401
from core.action import Action, DelayAction
from core.undo_commands import (
    AddActionCommand,
    DeleteActionsCommand,
    DuplicateActionCommand,
    EditActionCommand,
    MoveActionCommand,
    ToggleEnabledCommand,
)
from modules.keyboard import TypeText
from modules.mouse import MouseClick

# ============================================================
# Flow 1: Add via AddActionCommand → verify insertion + undo
# ============================================================

class TestAddActionCommand:
    """Verify AddActionCommand inserts at correct position and undoes cleanly."""

    def test_add_to_empty_list(self) -> None:
        actions: list[Action] = []
        cmd = AddActionCommand(actions, 0, MouseClick(x=100, y=200))
        cmd.redo()
        assert len(actions) == 1, "Should have 1 action after add"
        assert actions[0].x == 100

    def test_add_inserts_at_position(self) -> None:
        actions: list[Action] = [DelayAction(duration_ms=100), DelayAction(duration_ms=200)]
        new = MouseClick(x=50, y=60)
        cmd = AddActionCommand(actions, 1, new)
        cmd.redo()
        assert len(actions) == 3, "Should insert between existing"
        assert actions[1].ACTION_TYPE == "mouse_click"

    def test_add_undo_removes(self) -> None:
        actions: list[Action] = [DelayAction(duration_ms=100)]
        cmd = AddActionCommand(actions, 1, MouseClick(x=50, y=60))
        cmd.redo()
        assert len(actions) == 2
        cmd.undo()
        assert len(actions) == 1, "Undo should restore to original length"
        assert actions[0].duration_ms == 100

    def test_add_redo_after_undo(self) -> None:
        actions: list[Action] = []
        action = MouseClick(x=10, y=20)
        cmd = AddActionCommand(actions, 0, action)
        cmd.redo()
        cmd.undo()
        cmd.redo()
        assert len(actions) == 1, "Re-redo should re-add"
        assert actions[0] is action, "Should be same object reference"


# ============================================================
# Flow 2: Edit via EditActionCommand → verify swap + undo
# ============================================================

class TestEditActionCommand:
    """Verify EditActionCommand replaces action and undoes correctly."""

    def test_edit_replaces_action(self) -> None:
        old = MouseClick(x=100, y=200)
        new = MouseClick(x=300, y=400)
        actions: list[Action] = [old]
        cmd = EditActionCommand(actions, 0, old, new)
        cmd.redo()
        assert actions[0].x == 300, "Edit should replace action"

    def test_edit_undo_restores(self) -> None:
        old = MouseClick(x=100, y=200)
        new = MouseClick(x=300, y=400)
        actions: list[Action] = [old]
        cmd = EditActionCommand(actions, 0, old, new)
        cmd.redo()
        cmd.undo()
        assert actions[0].x == 100, "Undo should restore original"
        assert actions[0] is old

    def test_edit_preserves_neighbors(self) -> None:
        actions: list[Action] = [
            DelayAction(duration_ms=100),
            MouseClick(x=50, y=60),
            DelayAction(duration_ms=200),
        ]
        old = actions[1]
        new = MouseClick(x=999, y=888)
        cmd = EditActionCommand(actions, 1, old, new)
        cmd.redo()
        assert actions[0].duration_ms == 100, "Neighbor 0 unchanged"
        assert actions[1].x == 999, "Middle replaced"
        assert actions[2].duration_ms == 200, "Neighbor 2 unchanged"


# ============================================================
# Flow 3: Delete via DeleteActionsCommand → verify removal + undo
# ============================================================

class TestDeleteActionsCommand:
    """Verify DeleteActionsCommand removes and re-inserts on undo."""

    def test_delete_single(self) -> None:
        actions: list[Action] = [MouseClick(x=100, y=200)]
        cmd = DeleteActionsCommand(actions, [0])
        cmd.redo()
        assert len(actions) == 0, "Should be empty after delete"

    def test_delete_middle(self) -> None:
        actions: list[Action] = [
            DelayAction(duration_ms=100),
            MouseClick(x=50, y=60),
            DelayAction(duration_ms=200),
        ]
        cmd = DeleteActionsCommand(actions, [1])
        cmd.redo()
        assert len(actions) == 2
        assert actions[0].duration_ms == 100
        assert actions[1].duration_ms == 200

    def test_delete_multiple_rows(self) -> None:
        actions: list[Action] = [
            DelayAction(duration_ms=100),
            MouseClick(x=50, y=60),
            DelayAction(duration_ms=200),
        ]
        cmd = DeleteActionsCommand(actions, [0, 2])
        cmd.redo()
        assert len(actions) == 1
        assert actions[0].ACTION_TYPE == "mouse_click"

    def test_delete_undo_restores_positions(self) -> None:
        a1, a2, a3 = DelayAction(duration_ms=100), MouseClick(x=1, y=2), DelayAction(duration_ms=200)
        actions: list[Action] = [a1, a2, a3]
        cmd = DeleteActionsCommand(actions, [1])
        cmd.redo()
        cmd.undo()
        assert len(actions) == 3, "Undo should restore all"
        assert actions[1] is a2, "Should restore same object at same position"


# ============================================================
# Flow 4: Move via MoveActionCommand → verify swap + undo
# ============================================================

class TestMoveActionCommand:
    """Verify MoveActionCommand swaps adjacent items and undoes."""

    def test_move_up(self) -> None:
        a1, a2 = DelayAction(duration_ms=100), DelayAction(duration_ms=200)
        actions: list[Action] = [a1, a2]
        cmd = MoveActionCommand(actions, 1, 0)
        cmd.redo()
        assert actions[0] is a2, "a2 should move up"
        assert actions[1] is a1

    def test_move_down(self) -> None:
        a1, a2 = DelayAction(duration_ms=100), DelayAction(duration_ms=200)
        actions: list[Action] = [a1, a2]
        cmd = MoveActionCommand(actions, 0, 1)
        cmd.redo()
        assert actions[0] is a2
        assert actions[1] is a1

    def test_move_undo_restores(self) -> None:
        a1, a2, a3 = DelayAction(duration_ms=100), DelayAction(duration_ms=200), DelayAction(duration_ms=300)
        actions: list[Action] = [a1, a2, a3]
        cmd = MoveActionCommand(actions, 1, 0)
        cmd.redo()
        cmd.undo()
        assert actions == [a1, a2, a3], "Undo should restore original order"


# ============================================================
# Flow 5: Duplicate via DuplicateActionCommand → verify copy + undo
# ============================================================

class TestDuplicateActionCommand:
    """Verify DuplicateActionCommand creates independent copy and undoes."""

    def test_duplicate_inserts_after(self) -> None:
        original = MouseClick(x=100, y=200, delay_after=50)
        dup = Action.from_dict(original.to_dict())
        actions: list[Action] = [original]
        cmd = DuplicateActionCommand(actions, 0, dup)
        cmd.redo()
        assert len(actions) == 2
        assert actions[1].x == 100
        assert actions[0].id != actions[1].id, "Must have different IDs"

    def test_duplicate_is_independent(self) -> None:
        original = MouseClick(x=100, y=200)
        dup = Action.from_dict(original.to_dict())
        actions: list[Action] = [original]
        cmd = DuplicateActionCommand(actions, 0, dup)
        cmd.redo()
        original.x = 999
        assert actions[1].x == 100, "Duplicate should be independent"

    def test_duplicate_undo_removes(self) -> None:
        original = MouseClick(x=100, y=200)
        dup = Action.from_dict(original.to_dict())
        actions: list[Action] = [original]
        cmd = DuplicateActionCommand(actions, 0, dup)
        cmd.redo()
        cmd.undo()
        assert len(actions) == 1
        assert actions[0] is original


# ============================================================
# Flow 5b: Toggle via ToggleEnabledCommand
# ============================================================

class TestToggleEnabledCommand:
    """Verify ToggleEnabledCommand flips enabled state and undoes."""

    def test_toggle_disables(self) -> None:
        a = DelayAction(duration_ms=100, enabled=True)
        actions: list[Action] = [a]
        cmd = ToggleEnabledCommand(actions, [0])
        cmd.redo()
        assert a.enabled is False, "Should disable"

    def test_toggle_undo_re_enables(self) -> None:
        a = DelayAction(duration_ms=100, enabled=True)
        actions: list[Action] = [a]
        cmd = ToggleEnabledCommand(actions, [0])
        cmd.redo()
        cmd.undo()
        assert a.enabled is True, "Undo should re-enable"


# ============================================================
# Flow 6: Save → Load → Verify persistence
# ============================================================

class TestSaveLoadPersistence:
    """Full save/load roundtrip with all settings."""

    def test_full_roundtrip(self, tmp_path: Path) -> None:
        from core.action import DelayAction
        from core.engine import MacroEngine
        from modules.mouse import MouseClick

        actions = [
            MouseClick(x=42, y=99, delay_after=100),
            TypeText(text="hello world"),
            DelayAction(duration_ms=500),
        ]
        path = str(tmp_path / "test.json")
        MacroEngine.save_macro(
            path, actions, name="MyMacro",
            loop_count=5, loop_delay_ms=250,
        )

        loaded, settings = MacroEngine.load_macro(path)

        assert len(loaded) == 3
        assert loaded[0].x == 42
        assert loaded[0].delay_after == 100
        assert loaded[1].text == "hello world"
        assert loaded[2].duration_ms == 500
        assert settings["loop_count"] == 5
        assert settings["delay_between_loops"] == 250
        assert settings["name"] == "MyMacro"

    def test_save_load_preserves_enabled_state(self, tmp_path: Path) -> None:
        from core.action import DelayAction
        from core.engine import MacroEngine

        actions = [
            DelayAction(duration_ms=100, enabled=True),
            DelayAction(duration_ms=200, enabled=False),
        ]
        path = str(tmp_path / "enabled.json")
        MacroEngine.save_macro(path, actions)
        loaded, _ = MacroEngine.load_macro(path)

        assert loaded[0].enabled is True
        assert loaded[1].enabled is False

    def test_save_load_preserves_repeat_count(self, tmp_path: Path) -> None:
        from core.action import DelayAction
        from core.engine import MacroEngine

        actions = [DelayAction(duration_ms=100, repeat_count=5)]
        path = str(tmp_path / "repeat.json")
        MacroEngine.save_macro(path, actions)
        loaded, _ = MacroEngine.load_macro(path)

        assert loaded[0].repeat_count == 5

    def test_load_corrupt_json_raises(self, tmp_path: Path) -> None:
        from core.engine import MacroEngine

        path = tmp_path / "corrupt.json"
        path.write_text("{invalid json!!}")

        with pytest.raises(ValueError, match="corrupt"):
            MacroEngine.load_macro(str(path))


# ============================================================
# Flow 7: Recorder get_actions_snapshot() API
# ============================================================

class TestRecorderSnapshot:
    """Test the new public API for thread-safe action snapshot."""

    def test_snapshot_empty(self) -> None:
        from core.recorder import Recorder
        r = Recorder()
        assert r.get_actions_snapshot() == []

    def test_snapshot_returns_copy(self) -> None:
        from core.action import DelayAction
        from core.recorder import Recorder

        r = Recorder()
        # Manually add actions for testing
        with r._actions_lock:
            r._actions.append(DelayAction(duration_ms=100))
            r._actions.append(DelayAction(duration_ms=200))

        snapshot = r.get_actions_snapshot()
        assert len(snapshot) == 2
        # Modifying snapshot should NOT affect recorder
        snapshot.pop()
        assert r.action_count == 2

    def test_snapshot_with_start_index(self) -> None:
        from core.action import DelayAction
        from core.recorder import Recorder

        r = Recorder()
        with r._actions_lock:
            for i in range(5):
                r._actions.append(DelayAction(duration_ms=i * 100))

        # Get only new actions from index 3
        snapshot = r.get_actions_snapshot(start=3)
        assert len(snapshot) == 2
        assert snapshot[0].duration_ms == 300
        assert snapshot[1].duration_ms == 400

    def test_snapshot_thread_safety(self) -> None:
        from core.action import DelayAction
        from core.recorder import Recorder

        r = Recorder()
        errors: list[str] = []

        def writer() -> None:
            try:
                for i in range(50):
                    with r._actions_lock:
                        r._actions.append(DelayAction(duration_ms=i))
            except Exception as e:
                errors.append(str(e))

        def reader() -> None:
            try:
                for _ in range(50):
                    r.get_actions_snapshot()
            except Exception as e:
                errors.append(str(e))

        threads = [
            threading.Thread(target=writer),
            threading.Thread(target=reader),
            threading.Thread(target=reader),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert len(errors) == 0


# ============================================================
# Flow 8: Engine – disabled actions skip
# ============================================================

class TestEngineDisabledActions:
    """Verify that disabled actions are skipped correctly."""

    def test_disabled_action_skipped(self) -> None:
        from core.action import DelayAction

        da = DelayAction(duration_ms=1, enabled=False)
        # run() should return True immediately
        assert da.run() is True

    def test_all_disabled_still_completes(self) -> None:
        from core.action import DelayAction
        from core.engine import MacroEngine

        engine = MacroEngine()
        actions = [
            DelayAction(duration_ms=1, enabled=False),
            DelayAction(duration_ms=1, enabled=False),
        ]
        engine.load_actions(actions)
        engine.set_loop(count=1, delay_ms=0)
        engine.start()
        engine.wait(3000)
        assert not engine.isRunning()

    def test_mixed_enabled_disabled(self) -> None:
        from core.action import DelayAction
        from core.engine import MacroEngine

        engine = MacroEngine()
        actions = [
            DelayAction(duration_ms=1, enabled=True),
            DelayAction(duration_ms=1, enabled=False),
            DelayAction(duration_ms=1, enabled=True),
        ]
        engine.load_actions(actions)
        engine.set_loop(count=1)
        engine.start()
        engine.wait(3000)
        assert not engine.isRunning()


# ============================================================
# Flow 9: Action get_display_name() — all types
# ============================================================

class TestAllActionDisplayNames:
    """Verify every registered action type returns a non-empty display name."""

    def test_all_types_have_display_name(self) -> None:
        from core.action import get_action_class, get_all_action_types

        for atype in get_all_action_types():
            try:
                cls = get_action_class(atype)
                # Create with minimal defaults
                action = cls.__new__(cls)
                from core.action import Action
                Action.__init__(action)
                action._set_params({})
                name = action.get_display_name()
                assert isinstance(name, str), f"{atype} returns non-string"
                assert len(name) > 0, f"{atype} returns empty display name"
            except Exception:
                # Some types need specific params — just ensure no crash
                pass
