"""
Recording panel – a compact widget with Record/Stop controls
and a live preview of captured actions.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QCheckBox, QListWidget, QListWidgetItem,
)
from PyQt6.QtCore import QTimer, pyqtSignal
from typing import Optional

from core.recorder import Recorder


class RecordingPanel(QWidget):
    """
    Emits `recording_finished(list[Action])` when the user stops recording.
    """

    recording_finished = pyqtSignal(list)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._recorder = Recorder()
        self._update_timer = QTimer()
        self._update_timer.setInterval(300)
        self._update_timer.timeout.connect(self._update_preview)

        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Header
        header = QLabel("⏺ Recording")
        header.setObjectName("headerLabel")
        layout.addWidget(header)

        # Options
        opt_layout = QHBoxLayout()
        self._mouse_check = QCheckBox("Mouse")
        self._mouse_check.setChecked(True)
        opt_layout.addWidget(self._mouse_check)

        self._keyboard_check = QCheckBox("Keyboard")
        self._keyboard_check.setChecked(True)
        opt_layout.addWidget(self._keyboard_check)
        opt_layout.addStretch()
        layout.addLayout(opt_layout)

        # Buttons
        btn_layout = QHBoxLayout()
        self._record_btn = QPushButton("⏺ Record")
        self._record_btn.setObjectName("dangerButton")
        self._record_btn.clicked.connect(self._start_recording)
        btn_layout.addWidget(self._record_btn)

        self._stop_btn = QPushButton("⏹ Stop")
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self._stop_recording)
        btn_layout.addWidget(self._stop_btn)
        layout.addLayout(btn_layout)

        # Live preview list
        self._preview_list = QListWidget()
        self._preview_list.setMaximumHeight(200)
        layout.addWidget(self._preview_list)

        # Status
        self._status_label = QLabel("Ready to record")
        self._status_label.setObjectName("subtitleLabel")
        layout.addWidget(self._status_label)

    def _start_recording(self) -> None:
        self._recorder = Recorder(
            record_mouse=self._mouse_check.isChecked(),
            record_keyboard=self._keyboard_check.isChecked(),
        )
        self._preview_list.clear()
        self._record_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)   # Allow cancel during countdown
        self._mouse_check.setEnabled(False)
        self._keyboard_check.setEnabled(False)
        # 3-2-1 countdown before recording starts
        self._countdown_remaining = 3
        self._countdown_timer = QTimer()
        self._countdown_timer.setInterval(1000)
        self._countdown_timer.timeout.connect(self._countdown_tick)
        self._status_label.setText("⏱ Recording in 3... (click Stop to cancel)")
        self._countdown_timer.start()

    def _countdown_tick(self) -> None:
        """Handle countdown tick."""
        self._countdown_remaining -= 1
        if self._countdown_remaining > 0:
            self._status_label.setText(
                f"⏱ Recording in {self._countdown_remaining}...")
        else:
            self._countdown_timer.stop()
            self._stop_btn.setEnabled(True)
            self._recorder.start()
            self._status_label.setText(
                "🔴 Recording... perform your actions")
            self._update_timer.start()

    def _stop_recording(self) -> None:
        # Cancel countdown if still running
        if hasattr(self, '_countdown_timer') and self._countdown_timer.isActive():
            self._countdown_timer.stop()
            self._record_btn.setEnabled(True)
            self._stop_btn.setEnabled(False)
            self._mouse_check.setEnabled(True)
            self._keyboard_check.setEnabled(True)
            self._status_label.setText("⚠ Recording cancelled")
            return
        self._update_timer.stop()
        actions = self._recorder.stop()
        self._record_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self._mouse_check.setEnabled(True)
        self._keyboard_check.setEnabled(True)
        self._status_label.setText(f"✅ Recorded {len(actions)} actions")
        self.recording_finished.emit(actions)

    def _update_preview(self) -> None:
        """Periodically refresh the preview list with new actions."""
        count = self._recorder.action_count
        current = self._preview_list.count()
        if count > current:
            new_actions = self._recorder.get_actions_snapshot(start=current)
            for action in new_actions:
                item = QListWidgetItem(action.get_display_name())
                self._preview_list.addItem(item)
            self._preview_list.scrollToBottom()
            self._status_label.setText(f"🔴 Recording... {count} actions")
