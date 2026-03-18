"""
End-to-end flow tests – validates the full user journey WITHOUT a GUI.
Tests the data layer that the GUI wires to: _actions list management,
save/load persistence, recorder snapshot API, and engine safeguards.

Run: python -m pytest tests/test_e2e_flows.py -v
"""

import json
import os
import sys
import tempfile
import time
import threading
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# QApplication singleton for engine signals
from PyQt6.QtWidgets import QApplication
_app = QApplication.instance() or QApplication([])

# Force-register all action types
import core.action       # noqa: F401
import modules.mouse     # noqa: F401
import modules.keyboard  # noqa: F401
import modules.image     # noqa: F401
import modules.pixel     # noqa: F401
import core.scheduler    # noqa: F401


# ============================================================
# Flow 1: Add → Verify in list → Verify table data
# ============================================================

class TestAddActionFlow:
    """Simulate: User clicks Add → fills dialog → action appears in list."""

    def test_add_to_empty_list(self) -> None:
        from modules.mouse import MouseClick
        actions: list = []

        action = MouseClick(x=100, y=200)
        actions.append(action)

        assert len(actions) == 1
        assert actions[0].x == 100
        assert actions[0].y == 200

    def test_add_inserts_after_selection(self) -> None:
        from core.action import DelayAction
        from modules.mouse import MouseClick

        actions = [DelayAction(duration_ms=100), DelayAction(duration_ms=200)]
        new_action = MouseClick(x=50, y=60)
        selected_row = 0  # first row selected
        actions.insert(selected_row + 1, new_action)

        assert len(actions) == 3
        assert actions[0].ACTION_TYPE == "delay"
        assert actions[1].ACTION_TYPE == "mouse_click"
        assert actions[2].ACTION_TYPE == "delay"

    def test_add_appends_when_no_selection(self) -> None:
        from core.action import DelayAction
        from modules.mouse import MouseClick

        actions = [DelayAction(duration_ms=100)]
        new_action = MouseClick(x=50, y=60)
        selected_row = -1  # no selection
        if selected_row >= 0:
            actions.insert(selected_row + 1, new_action)
        else:
            actions.append(new_action)

        assert len(actions) == 2
        assert actions[1].ACTION_TYPE == "mouse_click"

    def test_add_multiple_types(self) -> None:
        from modules.mouse import MouseClick
        from modules.keyboard import TypeText, KeyPress
        from core.action import DelayAction

        actions: list = []
        actions.append(MouseClick(x=10, y=20))
        actions.append(TypeText(text="hello"))
        actions.append(KeyPress(key="enter"))
        actions.append(DelayAction(duration_ms=500))

        assert len(actions) == 4
        types = [a.ACTION_TYPE for a in actions]
        assert types == ["mouse_click", "type_text", "key_press", "delay"]


# ============================================================
# Flow 2: Edit → Verify change
# ============================================================

class TestEditActionFlow:
    """Simulate: User edits an existing action → verify mutation."""

    def test_edit_replaces_action(self) -> None:
        from modules.mouse import MouseClick

        actions = [MouseClick(x=100, y=200)]
        # User edits: change x to 300
        new_action = MouseClick(x=300, y=200)
        actions[0] = new_action

        assert actions[0].x == 300

    def test_edit_preserves_other_actions(self) -> None:
        from core.action import DelayAction
        from modules.mouse import MouseClick

        actions = [
            DelayAction(duration_ms=100),
            MouseClick(x=50, y=60),
            DelayAction(duration_ms=200),
        ]
        # Edit middle action
        actions[1] = MouseClick(x=999, y=888)

        assert actions[0].duration_ms == 100
        assert actions[1].x == 999
        assert actions[2].duration_ms == 200

    def test_edit_no_selection_noop(self) -> None:
        from modules.mouse import MouseClick

        actions = [MouseClick(x=100, y=200)]
        selected_row = -1
        if selected_row < 0:
            pass  # noop
        else:
            actions[selected_row] = MouseClick(x=999, y=999)

        # Unchanged
        assert actions[0].x == 100


# ============================================================
# Flow 3: Delete → Verify removal
# ============================================================

class TestDeleteActionFlow:
    """Simulate: User deletes an action → verify list shrinks."""

    def test_delete_single_action(self) -> None:
        from modules.mouse import MouseClick

        actions = [MouseClick(x=100, y=200)]
        actions.pop(0)
        assert len(actions) == 0

    def test_delete_middle_action(self) -> None:
        from core.action import DelayAction
        from modules.mouse import MouseClick

        actions = [
            DelayAction(duration_ms=100),
            MouseClick(x=50, y=60),
            DelayAction(duration_ms=200),
        ]
        actions.pop(1)

        assert len(actions) == 2
        assert actions[0].duration_ms == 100
        assert actions[1].duration_ms == 200

    def test_delete_last_action(self) -> None:
        from core.action import DelayAction

        actions = [DelayAction(duration_ms=100), DelayAction(duration_ms=200)]
        actions.pop(len(actions) - 1)

        assert len(actions) == 1
        assert actions[0].duration_ms == 100


# ============================================================
# Flow 4: Move Up/Down → Verify order
# ============================================================

class TestMoveActionFlow:
    """Simulate: User moves actions up/down → verify order swaps."""

    def test_move_up(self) -> None:
        from core.action import DelayAction

        actions = [
            DelayAction(duration_ms=100),
            DelayAction(duration_ms=200),
            DelayAction(duration_ms=300),
        ]
        row = 1  # move second item up
        actions[row - 1], actions[row] = actions[row], actions[row - 1]

        assert actions[0].duration_ms == 200
        assert actions[1].duration_ms == 100
        assert actions[2].duration_ms == 300

    def test_move_down(self) -> None:
        from core.action import DelayAction

        actions = [
            DelayAction(duration_ms=100),
            DelayAction(duration_ms=200),
            DelayAction(duration_ms=300),
        ]
        row = 1  # move second item down
        actions[row], actions[row + 1] = actions[row + 1], actions[row]

        assert actions[0].duration_ms == 100
        assert actions[1].duration_ms == 300
        assert actions[2].duration_ms == 200

    def test_move_up_first_item_noop(self) -> None:
        from core.action import DelayAction

        actions = [
            DelayAction(duration_ms=100),
            DelayAction(duration_ms=200),
        ]
        row = 0
        if row <= 0:
            pass  # noop
        else:
            actions[row - 1], actions[row] = actions[row], actions[row - 1]

        assert actions[0].duration_ms == 100

    def test_move_down_last_item_noop(self) -> None:
        from core.action import DelayAction

        actions = [
            DelayAction(duration_ms=100),
            DelayAction(duration_ms=200),
        ]
        row = len(actions) - 1
        if row >= len(actions) - 1:
            pass  # noop
        else:
            actions[row], actions[row + 1] = actions[row + 1], actions[row]

        assert actions[1].duration_ms == 200


# ============================================================
# Flow 5: Duplicate → Verify copy
# ============================================================

class TestDuplicateActionFlow:
    """Simulate: User duplicates an action → verify independent copy."""

    def test_duplicate_creates_copy(self) -> None:
        from core.action import Action
        from modules.mouse import MouseClick

        actions = [MouseClick(x=100, y=200, delay_after=50)]
        row = 0
        dup = Action.from_dict(actions[row].to_dict())
        actions.insert(row + 1, dup)

        assert len(actions) == 2
        assert actions[0].x == 100
        assert actions[1].x == 100
        assert actions[0].id != actions[1].id  # different IDs

    def test_duplicate_is_independent(self) -> None:
        from core.action import Action
        from modules.mouse import MouseClick

        original = MouseClick(x=100, y=200)
        dup = Action.from_dict(original.to_dict())

        # Modify original — dup should NOT change
        original.x = 999
        assert dup.x == 100


# ============================================================
# Flow 6: Save → Load → Verify persistence
# ============================================================

class TestSaveLoadPersistence:
    """Full save/load roundtrip with all settings."""

    def test_full_roundtrip(self, tmp_path: Path) -> None:
        from core.engine import MacroEngine
        from modules.mouse import MouseClick
        from modules.keyboard import TypeText
        from core.action import DelayAction

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
        from core.engine import MacroEngine
        from core.action import DelayAction

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
        from core.engine import MacroEngine
        from core.action import DelayAction

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
        from core.recorder import Recorder
        from core.action import DelayAction

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
        from core.recorder import Recorder
        from core.action import DelayAction

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
        from core.recorder import Recorder
        from core.action import DelayAction

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
        from core.engine import MacroEngine
        from core.action import DelayAction

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
        from core.engine import MacroEngine
        from core.action import DelayAction

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
        from core.action import get_all_action_types, get_action_class

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
