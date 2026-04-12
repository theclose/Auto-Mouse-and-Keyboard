"""
Phase 2: GUI Integration Tests — tests the dialog→signal→data flow
that was completely untested and caused the dialog.exec() bug.

Run: python -m pytest tests/test_gui_integration.py -v
"""

import copy
import os
import sys
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

_app = QApplication.instance() or QApplication([])

# Force-register all action types
import core.action  # noqa: F401
import core.scheduler  # noqa: F401
import modules.image  # noqa: F401
import modules.keyboard  # noqa: F401
import modules.mouse  # noqa: F401
import modules.pixel  # noqa: F401

# ============================================================
# Test 1: ActionEditorDialog signal lifecycle
# ============================================================

class TestActionEditorSignal:
    """Verify action_ready signal emits correct Action BEFORE accept()."""

    def test_signal_emits_on_ok(self) -> None:
        from gui.action_editor import ActionEditorDialog
        dialog = ActionEditorDialog()
        received: list[Any] = []
        dialog.action_ready.connect(lambda a: received.append(a))

        # Simulate: select mouse_click type, set params, call _on_ok
        # Find the combo index for mouse_click
        for i in range(dialog._type_combo.count()):
            if dialog._type_combo.itemData(
                    i, Qt.ItemDataRole.UserRole) == "mouse_click":
                dialog._type_combo.setCurrentIndex(i)
                break

        # Set X, Y params
        if "x" in dialog._param_widgets:
            dialog._param_widgets["x"].setValue(100)
        if "y" in dialog._param_widgets:
            dialog._param_widgets["y"].setValue(200)

        # Trigger OK
        dialog._on_ok()

        assert len(received) == 1, "action_ready signal should fire once"
        action = received[0]
        assert action.ACTION_TYPE == "mouse_click"
        assert action.x == 100
        assert action.y == 200

    def test_signal_not_emitted_on_cancel(self) -> None:
        from gui.action_editor import ActionEditorDialog
        dialog = ActionEditorDialog()
        received: list[Any] = []
        dialog.action_ready.connect(lambda a: received.append(a))

        dialog.reject()
        assert len(received) == 0, "No signal on cancel"

    def test_get_action_returns_result(self) -> None:
        from gui.action_editor import ActionEditorDialog
        dialog = ActionEditorDialog()

        # Navigate to delay type
        for i in range(dialog._type_combo.count()):
            if dialog._type_combo.itemData(
                    i, Qt.ItemDataRole.UserRole) == "delay":
                dialog._type_combo.setCurrentIndex(i)
                break

        dialog._on_ok()
        action = dialog.get_action()
        assert action is not None
        assert action.ACTION_TYPE == "delay"

    def test_all_action_types_selectable(self) -> None:
        """Every action type in ACTION_CATEGORIES can be selected."""
        from gui.action_editor import ACTION_CATEGORIES, ActionEditorDialog
        dialog = ActionEditorDialog()

        expected_types = set()
        for _, actions in ACTION_CATEGORIES:
            for atype, _ in actions:
                expected_types.add(atype)

        selectable_types = set()
        for i in range(dialog._type_combo.count()):
            data = dialog._type_combo.itemData(i, Qt.ItemDataRole.UserRole)
            if data is not None:
                selectable_types.add(data)

        assert selectable_types == expected_types, (
            f"Missing: {expected_types - selectable_types}, "
            f"Extra: {selectable_types - expected_types}"
        )

    def test_all_action_types_have_builders(self) -> None:
        """REGRESSION: Every action type MUST have a builder that produces
        at least one param widget. Prevents if_image_found/loop_block bug."""
        from gui.action_editor import ACTION_CATEGORIES, ActionEditorDialog
        # Types that legitimately have zero custom params
        NO_PARAMS_TYPES = {"comment"}

        missing_builders = []
        for _, actions in ACTION_CATEGORIES:
            for atype, label in actions:
                if atype in NO_PARAMS_TYPES:
                    continue
                dialog = ActionEditorDialog()
                # Select the action type in the combo
                for i in range(dialog._type_combo.count()):
                    data = dialog._type_combo.itemData(
                        i, Qt.ItemDataRole.UserRole)
                    if data == atype:
                        dialog._type_combo.setCurrentIndex(i)
                        break
                if len(dialog._param_widgets) == 0:
                    missing_builders.append(f"{atype} ({label})")

        assert not missing_builders, (
            f"Action types with NO param widgets (missing builder): "
            f"{missing_builders}"
        )

    def test_category_headers_not_selectable(self) -> None:
        """Category headers (bold items) should have no UserRole data."""
        from gui.action_editor import ACTION_CATEGORIES, ActionEditorDialog
        dialog = ActionEditorDialog()

        header_count = 0
        for i in range(dialog._type_combo.count()):
            data = dialog._type_combo.itemData(i, Qt.ItemDataRole.UserRole)
            if data is None:
                header_count += 1

        # May have +1 header from "Recent Actions" section
        expected_min = len(ACTION_CATEGORIES)
        assert header_count >= expected_min, (
            f"Expected at least {expected_min} headers, got {header_count}"
        )


# ============================================================
# Test 2: _refresh_table column integrity
# ============================================================

class TestRefreshTable:
    """Verify the tree model renders correctly for all action types."""

    def _make_main_window_stub(self) -> Any:
        """Create a minimal MainWindow with just the tree."""
        from gui.main_window import MainWindow
        with patch.object(MainWindow, '__init__', lambda self: None):
            mw = MainWindow.__new__(MainWindow)
        # Setup minimal tree
        from PyQt6.QtWidgets import QLabel, QLineEdit, QSpinBox, QTreeView
        mw._actions = []
        mw._stats_label = QLabel("")
        mw._empty_overlay = QLabel("")
        mw._filter_edit = QLineEdit()
        mw._loop_spin = QSpinBox()
        mw._loop_spin.setValue(1)
        # v3.0: tree view (tree-only)
        mw._tree = QTreeView()
        from gui.action_tree_model import ActionTreeFilterProxy, ActionTreeModel
        mw._tree_model = ActionTreeModel(mw._actions)
        _proxy = ActionTreeFilterProxy()
        _proxy.setSourceModel(mw._tree_model)
        mw._action_list_panel = MagicMock()
        mw._action_list_panel._filter_proxy = _proxy
        mw._action_list_panel.filter_proxy = _proxy
        mw._tree.setModel(_proxy)
        mw._minimap = MagicMock()
        return mw

    def test_empty_table(self) -> None:
        mw = self._make_main_window_stub()
        mw._refresh_table()
        assert mw._tree_model.rowCount() == 0

    def test_single_action_all_columns(self) -> None:
        from PyQt6.QtCore import Qt

        from gui.action_tree_model import COL_DELAY, COL_DESC, COL_DETAILS, COL_ENABLED, COL_INDEX, COL_TYPE
        from modules.mouse import MouseClick
        mw = self._make_main_window_stub()

        action = MouseClick(x=100, y=200, delay_after=50)
        action.description = "test click"
        mw._actions = [action]
        mw._refresh_table()

        assert mw._tree_model.rowCount() == 1
        # Col 0: row number
        idx0 = mw._tree_model.index(0, COL_INDEX)
        assert mw._tree_model.data(idx0, Qt.ItemDataRole.DisplayRole) == "1"
        # Col 2: type (contains icon)
        idx_type = mw._tree_model.index(0, COL_TYPE)
        type_text = mw._tree_model.data(idx_type, Qt.ItemDataRole.DisplayRole)
        assert "🖱" in type_text
        # Col 3: details (display name)
        idx_details = mw._tree_model.index(0, COL_DETAILS)
        details_text = mw._tree_model.data(idx_details, Qt.ItemDataRole.DisplayRole)
        assert "100" in details_text
        # Col 4: delay
        idx_delay = mw._tree_model.index(0, COL_DELAY)
        assert mw._tree_model.data(idx_delay, Qt.ItemDataRole.DisplayRole) == "50ms"
        # Col 1: enabled
        idx_en = mw._tree_model.index(0, COL_ENABLED)
        assert mw._tree_model.data(idx_en, Qt.ItemDataRole.DisplayRole) == "✓"
        # Col 5: description
        idx_desc = mw._tree_model.index(0, COL_DESC)
        assert mw._tree_model.data(idx_desc, Qt.ItemDataRole.DisplayRole) == "test click"

    def test_five_action_types_icons(self) -> None:
        from PyQt6.QtCore import Qt

        from core.action import DelayAction
        from gui.action_tree_model import COL_TYPE
        from modules.keyboard import KeyPress
        from modules.mouse import MouseClick
        from modules.pixel import CheckPixelColor

        mw = self._make_main_window_stub()
        mw._actions = [
            MouseClick(x=0, y=0),
            KeyPress(key="a"),
            DelayAction(duration_ms=100),
            CheckPixelColor(x=0, y=0, r=255, g=0, b=0),
        ]
        mw._refresh_table()

        assert mw._tree_model.rowCount() == 4
        icons = [mw._tree_model.data(mw._tree_model.index(i, COL_TYPE), Qt.ItemDataRole.DisplayRole) for i in range(4)]
        assert "🖱" in icons[0]
        assert "⌨" in icons[1]
        assert "⏱" in icons[2]
        assert "🎨" in icons[3]

    def test_disabled_action_shows_empty(self) -> None:
        from PyQt6.QtCore import Qt

        from core.action import DelayAction
        from gui.action_tree_model import COL_ENABLED

        mw = self._make_main_window_stub()
        mw._actions = [DelayAction(duration_ms=100, enabled=False)]
        mw._refresh_table()

        idx_en = mw._tree_model.index(0, COL_ENABLED)
        assert mw._tree_model.data(idx_en, Qt.ItemDataRole.DisplayRole) == ""


# ============================================================
# Test 3: SettingsDialog signal
# ============================================================

class TestSettingsDialogSignal:
    """Verify config_saved signal emits correct config dict."""

    def test_signal_emits_on_save(self) -> None:
        from gui.settings_dialog import DEFAULT_CONFIG, SettingsDialog
        config = copy.deepcopy(DEFAULT_CONFIG)
        dialog = SettingsDialog(config)
        received: list[Any] = []
        dialog.config_saved.connect(lambda c: received.append(c))

        dialog._on_save()

        assert len(received) == 1
        assert isinstance(received[0], dict)
        assert "hotkeys" in received[0]
        assert "defaults" in received[0]

    def test_changed_value_reflected(self) -> None:
        from gui.settings_dialog import DEFAULT_CONFIG, SettingsDialog
        config = copy.deepcopy(DEFAULT_CONFIG)
        dialog = SettingsDialog(config)
        received: list[Any] = []
        dialog.config_saved.connect(lambda c: received.append(c))

        # Change click delay
        dialog._widgets["defaults.click_delay"].setValue(999)
        dialog._on_save()

        assert received[0]["defaults"]["click_delay"] == 999


# ============================================================
# Test 4: TYPE_ICONS coverage
# ============================================================

class TestTypeIconsCoverage:
    """Every registered action type should have an icon in _TYPE_ICONS."""

    def test_all_types_have_icons(self) -> None:
        from core.action import get_all_action_types
        from gui.main_window import MainWindow

        for atype in get_all_action_types():
            assert atype in MainWindow._TYPE_ICONS, (
                f"Missing icon for action type: {atype}"
            )


# ============================================================
# Test 5: ActionEditor — Edit Flow (_load_action)
# ============================================================

class TestActionEditorEditFlow:
    """Verify dialog correctly loads existing actions for editing."""

    def test_load_mouse_click_sets_xy(self) -> None:
        from gui.action_editor import ActionEditorDialog
        from modules.mouse import MouseClick

        action = MouseClick(x=555, y=777, delay_after=200)
        action.description = "test desc"
        dialog = ActionEditorDialog(action=action)

        # Verify type combo selected mouse_click
        atype = dialog._type_combo.currentData(Qt.ItemDataRole.UserRole)
        assert atype == "mouse_click"

        # Verify params populated
        assert dialog._param_widgets["x"].value() == 555
        assert dialog._param_widgets["y"].value() == 777

        # Verify common settings
        assert dialog._delay_spin.value() == 200
        assert dialog._desc_edit.text() == "test desc"

    def test_load_delay_sets_duration(self) -> None:
        from core.action import DelayAction
        from gui.action_editor import ActionEditorDialog

        action = DelayAction(duration_ms=2500)
        dialog = ActionEditorDialog(action=action)

        atype = dialog._type_combo.currentData(Qt.ItemDataRole.UserRole)
        assert atype == "delay"
        assert dialog._param_widgets["duration_ms"].value() == 2500

    def test_load_preserves_enabled_state(self) -> None:
        from core.action import DelayAction
        from gui.action_editor import ActionEditorDialog

        disabled = DelayAction(duration_ms=100, enabled=False,
                               repeat_count=3)
        dialog = ActionEditorDialog(action=disabled)

        assert not dialog._enabled_check.isChecked()
        assert dialog._repeat_spin.value() == 3

    def test_load_key_press_sets_key(self) -> None:
        from gui.action_editor import ActionEditorDialog
        from modules.keyboard import KeyPress

        action = KeyPress(key="enter")
        dialog = ActionEditorDialog(action=action)

        atype = dialog._type_combo.currentData(Qt.ItemDataRole.UserRole)
        assert atype == "key_press"
        assert dialog._param_widgets["key"].currentText() == "enter"

    def test_load_type_text_sets_text(self) -> None:
        from gui.action_editor import ActionEditorDialog
        from modules.keyboard import TypeText

        action = TypeText(text="hello world")
        dialog = ActionEditorDialog(action=action)

        atype = dialog._type_combo.currentData(Qt.ItemDataRole.UserRole)
        assert atype == "type_text"
        assert dialog._param_widgets["text"].toPlainText() == "hello world"


# ============================================================
# Test 6: ActionEditor — Param Caching
# ============================================================

class TestActionEditorParamCache:
    """Verify x,y values persist when switching between types."""

    def test_xy_cached_on_type_switch(self) -> None:
        from gui.action_editor import ActionEditorDialog

        dialog = ActionEditorDialog()

        # Select mouse_click and set x=123, y=456
        for i in range(dialog._type_combo.count()):
            if dialog._type_combo.itemData(
                    i, Qt.ItemDataRole.UserRole) == "mouse_click":
                dialog._type_combo.setCurrentIndex(i)
                break
        dialog._param_widgets["x"].setValue(123)
        dialog._param_widgets["y"].setValue(456)

        # Switch to delay (no x,y)
        for i in range(dialog._type_combo.count()):
            if dialog._type_combo.itemData(
                    i, Qt.ItemDataRole.UserRole) == "delay":
                dialog._type_combo.setCurrentIndex(i)
                break
        assert "x" not in dialog._param_widgets

        # Switch back to mouse_move (has x,y)
        for i in range(dialog._type_combo.count()):
            if dialog._type_combo.itemData(
                    i, Qt.ItemDataRole.UserRole) == "mouse_move":
                dialog._type_combo.setCurrentIndex(i)
                break

        # x,y should be restored from cache
        assert dialog._param_widgets["x"].value() == 123
        assert dialog._param_widgets["y"].value() == 456

    def test_cache_no_leak_to_unrelated_type(self) -> None:
        from gui.action_editor import ActionEditorDialog

        dialog = ActionEditorDialog()

        # Select mouse_click and set x,y
        for i in range(dialog._type_combo.count()):
            if dialog._type_combo.itemData(
                    i, Qt.ItemDataRole.UserRole) == "mouse_click":
                dialog._type_combo.setCurrentIndex(i)
                break
        dialog._param_widgets["x"].setValue(999)

        # Switch to key_press → should NOT have x/y
        for i in range(dialog._type_combo.count()):
            if dialog._type_combo.itemData(
                    i, Qt.ItemDataRole.UserRole) == "key_press":
                dialog._type_combo.setCurrentIndex(i)
                break

        assert "x" not in dialog._param_widgets
        assert "key" in dialog._param_widgets


# ============================================================
# Test 7: Per-Type Param Builders
# ============================================================

class TestParamBuilders:
    """Verify each action type creates the expected widgets."""

    def _select_type(self, dialog: Any, atype: str) -> None:
        for i in range(dialog._type_combo.count()):
            if dialog._type_combo.itemData(
                    i, Qt.ItemDataRole.UserRole) == atype:
                dialog._type_combo.setCurrentIndex(i)
                return
        pytest.fail(f"Action type {atype} not found in combo")

    def test_mouse_click_has_x_y_duration(self) -> None:
        from gui.action_editor import ActionEditorDialog
        dialog = ActionEditorDialog()
        self._select_type(dialog, "mouse_click")
        assert "x" in dialog._param_widgets
        assert "y" in dialog._param_widgets
        assert "duration" in dialog._param_widgets

    def test_key_press_has_key(self) -> None:
        from gui.action_editor import ActionEditorDialog
        dialog = ActionEditorDialog()
        self._select_type(dialog, "key_press")
        assert "key" in dialog._param_widgets

    def test_type_text_has_text_and_interval(self) -> None:
        from gui.action_editor import ActionEditorDialog
        dialog = ActionEditorDialog()
        self._select_type(dialog, "type_text")
        assert "text" in dialog._param_widgets
        assert "interval" in dialog._param_widgets

    def test_delay_has_duration_ms(self) -> None:
        from gui.action_editor import ActionEditorDialog
        dialog = ActionEditorDialog()
        self._select_type(dialog, "delay")
        assert "duration_ms" in dialog._param_widgets

    def test_check_pixel_has_rgb_tolerance(self) -> None:
        from gui.action_editor import ActionEditorDialog
        dialog = ActionEditorDialog()
        self._select_type(dialog, "check_pixel_color")
        assert "x" in dialog._param_widgets
        assert "r" in dialog._param_widgets
        assert "g" in dialog._param_widgets
        assert "b" in dialog._param_widgets
        assert "tolerance" in dialog._param_widgets

    def test_mouse_scroll_has_clicks(self) -> None:
        from gui.action_editor import ActionEditorDialog
        dialog = ActionEditorDialog()
        self._select_type(dialog, "mouse_scroll")
        assert "clicks" in dialog._param_widgets

    def test_key_combo_has_keys_str(self) -> None:
        from gui.action_editor import ActionEditorDialog
        dialog = ActionEditorDialog()
        self._select_type(dialog, "key_combo")
        assert "keys_str" in dialog._param_widgets


# ============================================================
# Test 8: Settings — Reset Defaults
# ============================================================

class TestSettingsWidgetInit:
    """Verify SettingsDialog populates widgets from config."""

    def test_modified_config_reflected_in_widgets(self) -> None:
        from gui.settings_dialog import DEFAULT_CONFIG, SettingsDialog
        config = copy.deepcopy(DEFAULT_CONFIG)
        config["defaults"]["click_delay"] = 42
        dialog = SettingsDialog(config)

        # Widget should show the modified value
        assert dialog._widgets["defaults.click_delay"].value() == 42

    def test_default_config_values_in_widgets(self) -> None:
        from gui.settings_dialog import DEFAULT_CONFIG, SettingsDialog
        config = copy.deepcopy(DEFAULT_CONFIG)
        dialog = SettingsDialog(config)

        # Should have the default value
        assert dialog._widgets["defaults.click_delay"].value() == \
            DEFAULT_CONFIG["defaults"]["click_delay"]


# ============================================================
# Test 9: RecordingPanel — UI State Machine
# ============================================================

class TestRecordingPanelState:
    """Verify recording panel button state transitions."""

    def test_initial_state(self) -> None:
        from gui.recording_panel import RecordingPanel
        panel = RecordingPanel()
        assert panel._record_btn.isEnabled()
        assert not panel._stop_btn.isEnabled()
        assert panel._mouse_check.isEnabled()
        assert panel._keyboard_check.isEnabled()

    def test_recording_started_disables_record(self) -> None:
        from gui.recording_panel import RecordingPanel
        panel = RecordingPanel()

        # Mock recorder to avoid actual input capture
        with patch.object(panel._recorder, 'start'):
            panel._start_recording()

        assert not panel._record_btn.isEnabled()
        # Stop button ENABLED during countdown (allows cancel)
        assert panel._stop_btn.isEnabled()
        assert not panel._mouse_check.isEnabled()
        # Countdown text should show
        assert "Bắt đầu ghi sau" in panel._status_label.text()

    def test_stop_emits_signal_and_restores_ui(self) -> None:
        from gui.recording_panel import RecordingPanel
        panel = RecordingPanel()
        received: list[Any] = []
        panel.recording_finished.connect(lambda a: received.append(a))

        with patch.object(panel._recorder, 'start'):
            panel._start_recording()
            # Simulate countdown finished: stop timer, start recorder
            panel._countdown_timer.stop()
            panel._recorder.start()

        # Mock stop to return empty actions
        with patch.object(panel._recorder, 'stop', return_value=[]):
            panel._stop_recording()

        assert panel._record_btn.isEnabled()
        assert not panel._stop_btn.isEnabled()
        assert len(received) == 1
        assert received[0] == []

    def test_stop_during_countdown_cancels(self) -> None:
        """Clicking Stop during countdown should cancel without recording."""
        from gui.recording_panel import RecordingPanel
        panel = RecordingPanel()
        received: list[Any] = []
        panel.recording_finished.connect(lambda a: received.append(a))

        with patch.object(panel._recorder, 'start'):
            panel._start_recording()

        # Stop during countdown — should cancel
        panel._stop_recording()

        assert panel._record_btn.isEnabled()
        assert not panel._stop_btn.isEnabled()
        assert "hủy" in panel._status_label.text()
        assert len(received) == 0  # No signal emitted

