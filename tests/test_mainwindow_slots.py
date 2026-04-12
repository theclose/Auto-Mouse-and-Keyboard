"""
WP1: MainWindow Slot Tests — verifies all untested interaction methods.
Uses the proven stub pattern: patch __init__, inject minimal widgets.

Run: python -m pytest tests/test_mainwindow_slots.py -v
"""

import os
import sys
from typing import Any
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtGui import QUndoStack
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QGroupBox,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSpinBox,
)

_app = QApplication.instance() or QApplication([])

# Force-register all action types
import core.action  # noqa: F401
import core.scheduler  # noqa: F401
import modules.image  # noqa: F401
import modules.keyboard  # noqa: F401
import modules.mouse  # noqa: F401
import modules.pixel  # noqa: F401


def _make_stub() -> Any:
    """Create a minimal MainWindow stub with just the required widgets."""
    from gui.main_window import MainWindow
    with patch.object(MainWindow, '__init__', lambda self: None):
        mw = MainWindow.__new__(MainWindow)

    # Inject minimal widgets
    mw._actions = []
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

    # Mock engine
    mw._engine = MagicMock()
    mw._engine.is_paused = False
    mw._engine.is_running = False
    mw._engine.isRunning.return_value = False

    # Mock tray
    mw._tray = MagicMock()

    # Mock autosave
    mw._autosave = MagicMock()

    # Undo stack (no indexChanged connection in tests to avoid recursion)
    mw._undo_stack = QUndoStack()

    # Mock toolbar actions
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
    # Batch progress timer fields
    from PyQt6.QtCore import QTimer
    mw._pending_progress = None
    mw._pending_action_name = ""
    mw._progress_timer = QTimer()
    mw._progress_timer.setInterval(100)
    from PyQt6.QtWidgets import QDoubleSpinBox
    mw._speed_spin = QDoubleSpinBox()
    mw._speed_spin.setValue(1.0)

    # v3.0: tree view (tree-only, no table)
    from PyQt6.QtWidgets import QTreeView
    mw._tree = QTreeView()
    from gui.action_tree_model import ActionTreeFilterProxy, ActionTreeModel
    mw._tree_model = ActionTreeModel(mw._actions)
    mw._filter_edit = QLineEdit()

    # Mock action_list_panel with filter_proxy
    mw._action_list_panel = MagicMock()
    _filter_proxy = ActionTreeFilterProxy()
    _filter_proxy.setSourceModel(mw._tree_model)
    mw._action_list_panel.filter_proxy = _filter_proxy
    mw._action_list_panel._filter_proxy = _filter_proxy
    mw._tree.setModel(_filter_proxy)  # connect tree to proxy

    # v3.0: variable inspector + step-through widgets
    from PyQt6.QtCore import QTimer
    mw._var_timer = QTimer()
    mw._var_group = QGroupBox()
    mw._step_next_btn = QPushButton()
    mw._step_toggle = QCheckBox()

    # Phase 3: Mini-Map mock
    mw._minimap = MagicMock()

    return mw


def _make_delay(ms: int = 100) -> Any:
    from core.action import DelayAction
    return DelayAction(duration_ms=ms)


# ============================================================
# 1. _handle_action_added
# ============================================================

class TestHandleActionAdded:
    def test_appends_when_no_selection(self) -> None:
        mw = _make_stub()
        action = _make_delay(100)

        mw._handle_action_added(action)

        assert len(mw._actions) == 1
        assert mw._actions[0] is action
        mw._refresh_table()
        assert mw._tree_model.rowCount() == 1

    def test_inserts_after_selected_row(self) -> None:
        mw = _make_stub()
        a1, a2, a3 = _make_delay(1), _make_delay(2), _make_delay(3)
        mw._actions = [a1, a2]
        mw._refresh_table()
        mw._select_tree_row(0)  # select row 0

        mw._handle_action_added(a3)

        assert len(mw._actions) == 3
        assert mw._actions[1] is a3  # inserted at row 0 + 1


# ============================================================
# 2. _handle_action_edited
# ============================================================

class TestHandleActionEdited:
    def test_replaces_at_row(self) -> None:
        mw = _make_stub()
        old = _make_delay(100)
        new = _make_delay(999)
        mw._actions = [old]
        mw._refresh_table()

        mw._handle_action_edited(0, new)

        assert mw._actions[0] is new
        assert mw._actions[0].duration_ms == 999

    def test_oob_row_ignored(self) -> None:
        mw = _make_stub()
        mw._actions = [_make_delay()]

        # Row 5 is out of bounds — should not crash
        mw._handle_action_edited(5, _make_delay(999))
        assert len(mw._actions) == 1
        assert mw._actions[0].duration_ms == 100  # unchanged


# ============================================================
# 3. _on_move_up / _on_move_down
# ============================================================

class TestMoveUpDown:
    def test_move_up_swaps(self) -> None:
        mw = _make_stub()
        a1, a2 = _make_delay(1), _make_delay(2)
        mw._actions = [a1, a2]
        mw._refresh_table()
        mw._select_tree_row(1)

        mw._on_move_up()

        assert mw._actions[0] is a2
        assert mw._actions[1] is a1

    def test_move_up_first_row_noop(self) -> None:
        mw = _make_stub()
        a1 = _make_delay(1)
        mw._actions = [a1]
        mw._refresh_table()
        mw._select_tree_row(0)

        mw._on_move_up()  # should do nothing
        assert mw._actions[0] is a1

    def test_move_down_swaps(self) -> None:
        mw = _make_stub()
        a1, a2 = _make_delay(1), _make_delay(2)
        mw._actions = [a1, a2]
        mw._refresh_table()
        mw._select_tree_row(0)

        mw._on_move_down()

        assert mw._actions[0] is a2
        assert mw._actions[1] is a1

    def test_move_down_last_row_noop(self) -> None:
        mw = _make_stub()
        a1 = _make_delay(1)
        mw._actions = [a1]
        mw._refresh_table()
        mw._select_tree_row(0)

        mw._on_move_down()
        assert mw._actions[0] is a1


# ============================================================
# 4. _on_duplicate
# ============================================================

class TestDuplicate:
    def test_duplicates_action(self) -> None:
        mw = _make_stub()
        orig = _make_delay(42)
        mw._actions = [orig]
        mw._refresh_table()
        mw._select_tree_row(0)

        mw._on_duplicate()

        assert len(mw._actions) == 2
        assert mw._actions[1].duration_ms == 42
        assert mw._actions[1] is not orig  # different object

    def test_no_selection_noop(self) -> None:
        mw = _make_stub()
        mw._actions = [_make_delay()]

        # No row selected
        mw._on_duplicate()
        assert len(mw._actions) == 1


# ============================================================
# 5. _on_toggle_enabled
# ============================================================

class TestToggleEnabled:
    def test_toggle_flips(self) -> None:
        mw = _make_stub()
        action = _make_delay()
        assert action.enabled is True
        mw._actions = [action]
        mw._refresh_table()
        mw._select_tree_row(0)

        mw._on_toggle_enabled()

        assert action.enabled is False

    def test_toggle_multiple_rows(self) -> None:
        mw = _make_stub()
        a1, a2, a3 = _make_delay(), _make_delay(), _make_delay()
        mw._actions = [a1, a2, a3]
        mw._refresh_table()

        with patch.object(type(mw), '_selected_rows',
                          return_value=[0, 2]):
            mw._on_toggle_enabled()

        assert a1.enabled is False
        assert a2.enabled is True  # not selected
        assert a3.enabled is False


# ============================================================
# 5b. _on_delete_action (multi-select)
# ============================================================

class TestDeleteAction:
    def test_delete_single(self) -> None:
        mw = _make_stub()
        mw._actions = [_make_delay(1), _make_delay(2)]
        mw._refresh_table()

        with patch.object(type(mw), '_selected_rows', return_value=[0]), \
             patch.object(QMessageBox, 'question',
                          return_value=QMessageBox.StandardButton.Yes):
            mw._on_delete_action()

        assert len(mw._actions) == 1
        assert mw._actions[0].duration_ms == 2

    def test_delete_multiple(self) -> None:
        mw = _make_stub()
        a1, a2, a3, a4, a5 = [_make_delay(i) for i in range(1, 6)]
        mw._actions = [a1, a2, a3, a4, a5]
        mw._refresh_table()

        # Select rows 0, 2, 4 (a1, a3, a5)
        with patch.object(type(mw), '_selected_rows', return_value=[0, 2, 4]), \
             patch.object(QMessageBox, 'question',
                          return_value=QMessageBox.StandardButton.Yes):
            mw._on_delete_action()

        assert len(mw._actions) == 2
        assert mw._actions[0] is a2
        assert mw._actions[1] is a4

    def test_delete_all_ctrl_a(self) -> None:
        mw = _make_stub()
        mw._actions = [_make_delay(i) for i in range(10)]
        mw._refresh_table()

        with patch.object(type(mw), '_selected_rows',
                          return_value=list(range(10))), \
             patch.object(QMessageBox, 'question',
                          return_value=QMessageBox.StandardButton.Yes):
            mw._on_delete_action()

        assert len(mw._actions) == 0
        mw._refresh_table()
        assert mw._tree_model.rowCount() == 0

    def test_delete_cancelled(self) -> None:
        mw = _make_stub()
        mw._actions = [_make_delay()]
        mw._refresh_table()

        with patch.object(type(mw), '_selected_rows', return_value=[0]), \
             patch.object(QMessageBox, 'question',
                          return_value=QMessageBox.StandardButton.No):
            mw._on_delete_action()

        assert len(mw._actions) == 1  # not deleted


# ============================================================
# 6. _on_play edge cases
# ============================================================

class TestOnPlay:
    def test_play_no_actions_blocked(self) -> None:
        mw = _make_stub()
        mw._actions = []

        with patch.object(QMessageBox, 'warning', return_value=None):
            mw._on_play()

        # Vietnamese: "Không có" or "No actions" or status changes
        status = mw._status_label.text()
        assert status != "Ready"  # status must have changed

    def test_play_all_disabled_blocked(self) -> None:
        mw = _make_stub()
        a = _make_delay()
        a.enabled = False
        mw._actions = [a]

        with patch.object(QMessageBox, 'warning', return_value=None):
            mw._on_play()

        # Status must change from "Ready" when all actions disabled
        status = mw._status_label.text()
        assert status != "Ready"

    def test_play_resume_when_paused(self) -> None:
        mw = _make_stub()
        mw._actions = [_make_delay()]
        mw._engine.is_paused = True

        mw._on_play()

        mw._engine.resume.assert_called_once()


# ============================================================
# 7. _on_stop
# ============================================================

class TestOnStop:
    def test_stop_calls_engine(self) -> None:
        mw = _make_stub()
        mw._on_stop()
        mw._engine.stop.assert_called_once()


# ============================================================
# 8. _on_recording_done
# ============================================================

class TestOnRecordingDone:
    def test_extends_actions(self) -> None:
        mw = _make_stub()
        mw._actions = [_make_delay()]
        new_actions = [_make_delay(1), _make_delay(2)]

        mw._on_recording_done(new_actions)

        assert len(mw._actions) == 3
        assert "2" in mw._status_label.text()

    def test_empty_recording_noop(self) -> None:
        mw = _make_stub()
        mw._actions = [_make_delay()]

        mw._on_recording_done([])

        assert len(mw._actions) == 1


# ============================================================
# 9. _on_coord_picked
# ============================================================

class TestOnCoordPicked:
    def test_copies_to_clipboard(self) -> None:
        mw = _make_stub()
        mock_clipboard = MagicMock()
        with patch.object(type(mw), 'show'), \
             patch.object(type(mw), 'activateWindow'), \
             patch('gui.main_window.QApplication.clipboard', return_value=mock_clipboard):
            mw._on_coord_picked(123, 456)

        mock_clipboard.setText.assert_called_once_with("123, 456")
        assert "123" in mw._status_label.text()


# ============================================================
# 10. _autosave_callback
# ============================================================

class TestAutosaveCallback:
    def test_no_file_returns_false(self) -> None:
        mw = _make_stub()
        mw._current_file = ""

        result = mw._autosave_callback()
        assert result is False

    def test_with_file_saves(self, tmp_path: Any) -> None:
        mw = _make_stub()
        mw._current_file = str(tmp_path / "test.json")
        mw._actions = [_make_delay()]

        result = mw._autosave_callback()

        assert result is True
        assert (tmp_path / "test.json").exists()


# ============================================================
# 11. Engine UI callbacks
# ============================================================

class TestEngineCallbacks:
    def test_on_engine_started_locks_ui(self) -> None:
        mw = _make_stub()
        mw._on_engine_started()
        assert "Đang chạy" in mw._status_label.text()  # Vietnamese
        assert not mw._tree.isEnabled()

    def test_on_engine_stopped_unlocks_ui(self) -> None:
        mw = _make_stub()
        mw._on_engine_started()  # lock first
        mw._on_engine_stopped()
        assert "dừng" in mw._status_label.text().lower()  # Vietnamese
        assert mw._tree.isEnabled()

    def test_on_engine_progress(self) -> None:
        mw = _make_stub()
        mw._on_engine_progress(3, 10)
        mw._flush_progress()  # flush buffered update
        assert mw._progress_bar.value() == 3
        assert mw._progress_bar.maximum() == 10

    def test_on_engine_error(self) -> None:
        mw = _make_stub()
        with patch.object(QMessageBox, 'warning', return_value=None):
            mw._on_engine_error("Something broke")
        assert "Something broke" in mw._status_label.text()

    def test_on_engine_loop(self) -> None:
        mw = _make_stub()
        mw._on_engine_loop(2, 5)
        assert "2" in mw._loop_label.text()
        assert "5" in mw._loop_label.text()

    def test_on_engine_loop_infinite(self) -> None:
        mw = _make_stub()
        mw._on_engine_loop(7, -1)
        assert "∞" in mw._loop_label.text()
