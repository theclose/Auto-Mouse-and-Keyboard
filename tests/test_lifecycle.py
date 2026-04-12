"""
Lifecycle Tests — Verify window close, resize, show/hide, theme, and config
persistence using a REAL MainWindow (not a stub).

Depends on: conftest_mw.real_main_window fixture (BS-3).

Run: python -m pytest tests/test_lifecycle.py -v
"""

import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestCloseEvent:
    """Verify closeEvent saves state and handles tray/unsaved correctly."""

    def test_close_saves_window_state(self, real_main_window):
        """closeEvent must call _save_window_state → save_config."""
        mw = real_main_window
        with patch.object(mw, "_save_window_state", wraps=mw._save_window_state) as spy, \
             patch.object(mw, "_on_quit"):  # prevent QApp.quit()
            mw._config.setdefault("ui", {})["minimize_to_tray"] = False
            mw._undo_stack.setClean()
            mw.closeEvent(None)
            spy.assert_called_once()

    def test_close_minimize_to_tray(self, real_main_window):
        """With minimize_to_tray=True, closeEvent hides window."""
        mw = real_main_window
        mw._config.setdefault("ui", {})["minimize_to_tray"] = True
        mw._tray = MagicMock()

        from PyQt6.QtGui import QCloseEvent
        event = QCloseEvent()
        mw.closeEvent(event)

        assert not mw.isVisible() or event.isAccepted() is False
        mw._tray.show_message.assert_called_once()

    def test_close_prompts_unsaved(self, real_main_window):
        """With dirty undo stack, closeEvent shows a save prompt."""
        mw = real_main_window
        mw._config.setdefault("ui", {})["minimize_to_tray"] = False

        # Make undo stack dirty via QUndoCommand
        from PyQt6.QtGui import QUndoCommand
        cmd = QUndoCommand("test")
        mw._undo_stack.push(cmd)

        from PyQt6.QtWidgets import QMessageBox
        with patch("gui.main_window.QMessageBox.question",
                    return_value=QMessageBox.StandardButton.Discard), \
             patch.object(mw, "_on_quit"):  # prevent QApp.quit()
            mw.closeEvent(None)
            # Should not crash; Discard means close without saving


class TestResizeAndSplitter:
    """Verify resize and splitter persistence."""

    def test_resize_no_crash(self, real_main_window):
        """Resizing the window must not crash."""
        mw = real_main_window
        mw.resize(640, 480)
        mw.resize(1200, 800)
        mw.resize(800, 500)  # minimum
        assert mw.width() >= 800

    def test_splitter_sizes_persist(self, real_main_window):
        """_save_window_state must capture splitter sizes in config."""
        mw = real_main_window
        mw._save_window_state()

        ui = mw._config.get("ui", {})
        assert "h_splitter_sizes" in ui, "H-splitter sizes not saved"
        assert "v_splitter_sizes" in ui, "V-splitter sizes not saved"
        assert len(ui["h_splitter_sizes"]) == 2
        assert len(ui["v_splitter_sizes"]) == 2


class TestThemeAndVisibility:
    """Verify theme and show/hide."""

    def test_theme_applied_on_init(self, real_main_window):
        """styleSheet() must not be empty after init."""
        mw = real_main_window
        qss = mw.styleSheet()
        assert len(qss) > 100, f"QSS too short ({len(qss)} chars)"
        assert "background-color" in qss

    def test_show_hide_cycle(self, real_main_window):
        """show → hide → show must not crash."""
        mw = real_main_window
        mw.show()
        assert mw.isVisible()
        mw.hide()
        assert not mw.isVisible()
        mw.show()
        assert mw.isVisible()
