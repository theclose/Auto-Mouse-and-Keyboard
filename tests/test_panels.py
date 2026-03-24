"""
Tests for gui.panels — panel widget initialization and signals.
Exercises all 6 extracted panels to bring coverage from 0%.
"""
import os
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication
app = QApplication.instance() or QApplication([])

from PyQt6.QtWidgets import (
    QWidget, QGroupBox, QPushButton, QLabel, QTableWidget,
    QTextEdit, QTreeView, QProgressBar,
)

# Import action modules for ActionListPanel
import modules.mouse
import modules.keyboard
import modules.image
import modules.pixel
import modules.system
import core.scheduler
from core.action import get_action_class


# ── PlaybackPanel ──────────────────────────────────────

class TestPlaybackPanel:
    def test_init(self):
        from gui.panels.playback_panel import PlaybackPanel
        p = PlaybackPanel()
        assert isinstance(p, QWidget)

    def test_has_play_btn(self):
        from gui.panels.playback_panel import PlaybackPanel
        p = PlaybackPanel()
        assert hasattr(p, '_play_btn')
        assert isinstance(p._play_btn, QPushButton)

    def test_has_signals(self):
        from gui.panels.playback_panel import PlaybackPanel
        p = PlaybackPanel()
        assert hasattr(p, 'play_requested')
        assert hasattr(p, 'pause_requested')
        assert hasattr(p, 'stop_requested')

    def test_play_signal_emits(self):
        from gui.panels.playback_panel import PlaybackPanel
        p = PlaybackPanel()
        received = []
        p.play_requested.connect(lambda: received.append(True))
        p._play_btn.click()
        assert len(received) == 1

    def test_has_loop_controls(self):
        from gui.panels.playback_panel import PlaybackPanel
        p = PlaybackPanel()
        assert hasattr(p, '_loop_spin')
        assert hasattr(p, '_loop_delay_spin')
        assert hasattr(p, '_speed_spin')


# ── ExecutionPanel ─────────────────────────────────────

class TestExecutionPanel:
    def test_init(self):
        from gui.panels.execution_panel import ExecutionPanel
        p = ExecutionPanel()
        assert isinstance(p, QWidget)

    def test_has_progress_bar(self):
        from gui.panels.execution_panel import ExecutionPanel
        p = ExecutionPanel()
        assert hasattr(p, '_progress_bar')
        assert isinstance(p._progress_bar, QProgressBar)

    def test_has_action_label(self):
        from gui.panels.execution_panel import ExecutionPanel
        p = ExecutionPanel()
        assert hasattr(p, '_action_label')

    def test_has_exec_log(self):
        from gui.panels.execution_panel import ExecutionPanel
        p = ExecutionPanel()
        assert hasattr(p, '_exec_log')


# ── VariablePanel ──────────────────────────────────────

class TestVariablePanel:
    def test_init(self):
        from gui.panels.variable_panel import VariablePanel
        p = VariablePanel()
        assert isinstance(p, QWidget)

    def test_has_var_table(self):
        from gui.panels.variable_panel import VariablePanel
        p = VariablePanel()
        assert hasattr(p, '_var_table')
        assert isinstance(p._var_table, QTableWidget)

    def test_has_group(self):
        from gui.panels.variable_panel import VariablePanel
        p = VariablePanel()
        assert hasattr(p, '_group')
        assert isinstance(p._group, QGroupBox)


# ── LogPanel ───────────────────────────────────────────

class TestLogPanel:
    def test_init(self):
        from gui.panels.log_panel import LogPanel
        p = LogPanel()
        assert isinstance(p, QWidget)

    def test_has_app_log(self):
        from gui.panels.log_panel import LogPanel
        p = LogPanel()
        assert hasattr(p, '_app_log')
        assert p._app_log is not None

    def test_init_no_crash(self):
        from gui.panels.log_panel import LogPanel
        p = LogPanel()
        # Just ensure init completes without error
        assert p is not None


# ── MiniMapWidget ──────────────────────────────────────

class TestMiniMapWidget:
    def test_init(self):
        from gui.panels.minimap_panel import MiniMapWidget
        m = MiniMapWidget()
        assert isinstance(m, QWidget)

    def test_set_actions(self):
        from gui.panels.minimap_panel import MiniMapWidget
        m = MiniMapWidget()
        delay = get_action_class("delay")()
        m.set_actions([delay, delay])
        # Should not crash

    def test_highlight_action(self):
        from gui.panels.minimap_panel import MiniMapWidget
        m = MiniMapWidget()
        delay = get_action_class("delay")()
        m.set_actions([delay])
        m.highlight_action(0)
        # Should not crash

    def test_action_clicked_signal(self):
        from gui.panels.minimap_panel import MiniMapWidget
        m = MiniMapWidget()
        assert hasattr(m, 'action_clicked')

    def test_set_actions_empty(self):
        from gui.panels.minimap_panel import MiniMapWidget
        m = MiniMapWidget()
        m.set_actions([])


# ── ActionListPanel ────────────────────────────────────

class TestActionListPanel:
    def test_init_empty(self):
        from gui.panels.action_list_panel import ActionListPanel
        p = ActionListPanel([])
        assert isinstance(p, QWidget)

    def test_init_with_actions(self):
        from gui.panels.action_list_panel import ActionListPanel
        delay = get_action_class("delay")()
        p = ActionListPanel([delay])
        assert p.table is not None

    def test_table_property(self):
        from gui.panels.action_list_panel import ActionListPanel
        p = ActionListPanel([])
        assert isinstance(p.table, QTableWidget)

    def test_tree_property(self):
        from gui.panels.action_list_panel import ActionListPanel
        p = ActionListPanel([])
        assert isinstance(p.tree, QTreeView)

    def test_filter_edit_property(self):
        from gui.panels.action_list_panel import ActionListPanel
        from PyQt6.QtWidgets import QLineEdit
        p = ActionListPanel([])
        assert isinstance(p.filter_edit, QLineEdit)

    def test_stats_label_property(self):
        from gui.panels.action_list_panel import ActionListPanel
        p = ActionListPanel([])
        assert isinstance(p.stats_label, QLabel)

    def test_empty_overlay(self):
        from gui.panels.action_list_panel import ActionListPanel
        p = ActionListPanel([])
        assert isinstance(p.empty_overlay, QLabel)

    def test_signals_exist(self):
        from gui.panels.action_list_panel import ActionListPanel
        p = ActionListPanel([])
        signals = [
            'edit_requested', 'context_menu_requested',
            'move_up_requested', 'move_down_requested',
            'duplicate_requested', 'copy_requested',
            'paste_requested', 'filter_changed', 'view_mode_changed',
        ]
        for s in signals:
            assert hasattr(p, s), f"Missing signal: {s}"

    def test_view_toggle(self):
        from gui.panels.action_list_panel import ActionListPanel
        delay = get_action_class("delay")()
        p = ActionListPanel([delay])
        # Switch to tree mode
        p._on_view_toggle(True)
        assert p._tree_mode is True
        # Switch back to table mode
        p._on_view_toggle(False)
        assert p._tree_mode is False

    def test_buttons_exist(self):
        from gui.panels.action_list_panel import ActionListPanel
        p = ActionListPanel([])
        assert isinstance(p._up_btn, QPushButton)
        assert isinstance(p._down_btn, QPushButton)
        assert isinstance(p._dup_btn, QPushButton)
        assert isinstance(p._copy_btn, QPushButton)
        assert isinstance(p._paste_btn, QPushButton)
