"""
Tests for Undo/Redo — verifies all 7 QUndoCommand classes and QUndoStack integration.

Run: python -m pytest tests/test_undo_redo.py -v
"""

import os
import sys
from typing import Any
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import (
    QApplication, QTableWidget, QLabel, QPushButton,
    QSpinBox, QCheckBox, QProgressBar, QGroupBox,
    QListWidget, QPlainTextEdit,
)
from PyQt6.QtGui import QUndoStack

_app = QApplication.instance() or QApplication([])

# Force-register all action types
import core.action       # noqa: F401
import modules.mouse     # noqa: F401
import modules.keyboard  # noqa: F401
import modules.image     # noqa: F401
import modules.pixel     # noqa: F401
import core.scheduler    # noqa: F401


def _make_stub() -> Any:
    """Create a minimal MainWindow stub."""
    from gui.main_window import MainWindow
    with patch.object(MainWindow, '__init__', lambda self: None):
        mw = MainWindow.__new__(MainWindow)

    mw._actions = []
    mw._table = QTableWidget(0, 6)
    mw._status_label = QLabel("Ready")
    mw._play_btn = QPushButton("Play")
    mw._pause_btn = QPushButton("Pause")
    mw._stop_btn = QPushButton("Stop")
    mw._loop_spin = QSpinBox()
    mw._loop_spin.setRange(0, 999999)
    mw._loop_spin.setValue(1)
    mw._loop_delay_spin = QSpinBox()
    mw._loop_delay_spin.setRange(0, 60000)
    mw._stop_on_error_check = QCheckBox()
    mw._action_label = QLabel("Idle")
    mw._progress_bar = QProgressBar()
    mw._loop_label = QLabel("")
    mw._exec_log = QListWidget()
    mw._app_log = QPlainTextEdit()
    mw._current_file = ""
    mw._macro_dir = "macros"
    mw.setWindowTitle = lambda t: None  # mock for engine start/stop

    mw._engine = MagicMock()
    mw._engine.is_paused = False
    mw._engine.is_running = False
    mw._engine.isRunning.return_value = False

    mw._tray = MagicMock()
    mw._autosave = MagicMock()

    mw._add_act = MagicMock()
    mw._edit_act = MagicMock()
    mw._del_act = MagicMock()
    mw._up_btn = QPushButton()
    mw._down_btn = QPushButton()
    mw._dup_btn = QPushButton()
    mw._loop_group = QGroupBox()
    mw._rec_panel = MagicMock()
    mw._ram_label = QLabel()
    mw._stats_label = QLabel()
    mw._empty_overlay = QLabel()
    from PyQt6.QtWidgets import QDoubleSpinBox
    mw._speed_spin = QDoubleSpinBox()
    mw._speed_spin.setValue(1.0)

    # Undo stack (no indexChanged in tests to avoid recursion)
    mw._undo_stack = QUndoStack()

    return mw


def _make_delay(ms: int = 100) -> Any:
    from core.action import DelayAction
    return DelayAction(duration_ms=ms)


# ============================================================
# 1. AddActionCommand
# ============================================================

class TestAddUndo:
    def test_add_then_undo(self) -> None:
        from gui.main_window import MainWindow
        mw = _make_stub()
        action = _make_delay(100)

        from core.undo_commands import AddActionCommand
        cmd = AddActionCommand(mw._actions, 0, action)
        mw._undo_stack.push(cmd)

        assert len(mw._actions) == 1
        assert mw._actions[0] is action

        mw._undo_stack.undo()
        assert len(mw._actions) == 0

    def test_add_undo_redo(self) -> None:
        from gui.main_window import MainWindow
        mw = _make_stub()
        action = _make_delay(42)

        from core.undo_commands import AddActionCommand
        mw._undo_stack.push(AddActionCommand(mw._actions, 0, action))
        mw._undo_stack.undo()
        assert len(mw._actions) == 0

        mw._undo_stack.redo()
        assert len(mw._actions) == 1
        assert mw._actions[0].duration_ms == 42


# ============================================================
# 2. EditActionCommand
# ============================================================

class TestEditUndo:
    def test_edit_undo_restores_old(self) -> None:
        mw = _make_stub()
        old = _make_delay(100)
        new = _make_delay(999)
        mw._actions = [old]

        from core.undo_commands import EditActionCommand
        mw._undo_stack.push(EditActionCommand(mw._actions, 0, old, new))

        assert mw._actions[0].duration_ms == 999

        mw._undo_stack.undo()
        assert mw._actions[0].duration_ms == 100
        assert mw._actions[0] is old


# ============================================================
# 3. DeleteActionsCommand
# ============================================================

class TestDeleteUndo:
    def test_delete_single_undo(self) -> None:
        mw = _make_stub()
        a1, a2 = _make_delay(1), _make_delay(2)
        mw._actions = [a1, a2]

        from core.undo_commands import DeleteActionsCommand
        mw._undo_stack.push(DeleteActionsCommand(mw._actions, [0]))

        assert len(mw._actions) == 1
        assert mw._actions[0] is a2

        mw._undo_stack.undo()
        assert len(mw._actions) == 2
        assert mw._actions[0] is a1
        assert mw._actions[1] is a2

    def test_delete_multiple_undo(self) -> None:
        mw = _make_stub()
        items = [_make_delay(i) for i in range(1, 6)]
        mw._actions = list(items)

        from core.undo_commands import DeleteActionsCommand
        # Delete rows 0, 2, 4
        mw._undo_stack.push(DeleteActionsCommand(mw._actions, [0, 2, 4]))

        assert len(mw._actions) == 2

        mw._undo_stack.undo()
        assert len(mw._actions) == 5
        for i in range(5):
            assert mw._actions[i] is items[i]


# ============================================================
# 4. MoveActionCommand
# ============================================================

class TestMoveUndo:
    def test_move_up_undo(self) -> None:
        mw = _make_stub()
        a1, a2 = _make_delay(1), _make_delay(2)
        mw._actions = [a1, a2]

        from core.undo_commands import MoveActionCommand
        mw._undo_stack.push(MoveActionCommand(mw._actions, 1, 0))

        assert mw._actions[0] is a2
        assert mw._actions[1] is a1

        mw._undo_stack.undo()
        assert mw._actions[0] is a1
        assert mw._actions[1] is a2

    def test_move_down_undo(self) -> None:
        mw = _make_stub()
        a1, a2 = _make_delay(1), _make_delay(2)
        mw._actions = [a1, a2]

        from core.undo_commands import MoveActionCommand
        mw._undo_stack.push(MoveActionCommand(mw._actions, 0, 1))

        assert mw._actions[0] is a2

        mw._undo_stack.undo()
        assert mw._actions[0] is a1


# ============================================================
# 5. DuplicateActionCommand
# ============================================================

class TestDuplicateUndo:
    def test_duplicate_undo(self) -> None:
        mw = _make_stub()
        orig = _make_delay(42)
        mw._actions = [orig]

        from core.action import Action as BaseAction
        dup = BaseAction.from_dict(orig.to_dict())

        from core.undo_commands import DuplicateActionCommand
        mw._undo_stack.push(DuplicateActionCommand(mw._actions, 0, dup))

        assert len(mw._actions) == 2
        assert mw._actions[1].duration_ms == 42

        mw._undo_stack.undo()
        assert len(mw._actions) == 1
        assert mw._actions[0] is orig


# ============================================================
# 6. ToggleEnabledCommand (self-inverse)
# ============================================================

class TestToggleUndo:
    def test_toggle_undo(self) -> None:
        mw = _make_stub()
        a1 = _make_delay()
        assert a1.enabled is True
        mw._actions = [a1]

        from core.undo_commands import ToggleEnabledCommand
        mw._undo_stack.push(ToggleEnabledCommand(mw._actions, [0]))

        assert a1.enabled is False

        mw._undo_stack.undo()
        assert a1.enabled is True

    def test_toggle_multiple_undo(self) -> None:
        mw = _make_stub()
        a1, a2, a3 = _make_delay(), _make_delay(), _make_delay()
        mw._actions = [a1, a2, a3]

        from core.undo_commands import ToggleEnabledCommand
        mw._undo_stack.push(ToggleEnabledCommand(mw._actions, [0, 2]))

        assert a1.enabled is False
        assert a2.enabled is True  # not toggled
        assert a3.enabled is False

        mw._undo_stack.undo()
        assert a1.enabled is True
        assert a2.enabled is True
        assert a3.enabled is True


# ============================================================
# 7. AddBatchCommand
# ============================================================

class TestBatchUndo:
    def test_recording_batch_undo(self) -> None:
        mw = _make_stub()
        mw._actions = [_make_delay()]
        batch = [_make_delay(1), _make_delay(2), _make_delay(3)]

        from core.undo_commands import AddBatchCommand
        mw._undo_stack.push(AddBatchCommand(mw._actions, batch))

        assert len(mw._actions) == 4

        mw._undo_stack.undo()
        assert len(mw._actions) == 1


# ============================================================
# 8. Stack behavior
# ============================================================

class TestUndoStack:
    def test_redo_cleared_on_new_push(self) -> None:
        mw = _make_stub()

        from core.undo_commands import AddActionCommand
        mw._undo_stack.push(
            AddActionCommand(mw._actions, 0, _make_delay(1)))
        mw._undo_stack.push(
            AddActionCommand(mw._actions, 1, _make_delay(2)))
        mw._undo_stack.undo()  # undo add-2

        # Push new command → redo of add-2 should be gone
        mw._undo_stack.push(
            AddActionCommand(mw._actions, 1, _make_delay(3)))

        assert not mw._undo_stack.canRedo()
        assert len(mw._actions) == 2
        assert mw._actions[1].duration_ms == 3

    def test_undo_empty_stack_noop(self) -> None:
        mw = _make_stub()
        assert not mw._undo_stack.canUndo()
        # Should not crash
        mw._undo_stack.undo()
        assert len(mw._actions) == 0

    def test_undo_text_descriptive(self) -> None:
        mw = _make_stub()
        action = _make_delay(100)

        from core.undo_commands import AddActionCommand
        mw._undo_stack.push(
            AddActionCommand(mw._actions, 0, action))

        assert "Delay" in mw._undo_stack.undoText()
