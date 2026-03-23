"""
Recording panel – a compact widget with Record/Pause/Stop controls,
live preview of captured actions, and recording options.
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
        header = QLabel("⏺ Ghi hành động")
        header.setObjectName("headerLabel")
        layout.addWidget(header)

        # Options row 1: input sources
        opt_layout = QHBoxLayout()
        self._mouse_check = QCheckBox("Chuột")
        self._mouse_check.setChecked(True)
        self._mouse_check.setAccessibleName("Ghi chuột")
        opt_layout.addWidget(self._mouse_check)

        self._keyboard_check = QCheckBox("Bàn phím")
        self._keyboard_check.setChecked(True)
        self._keyboard_check.setAccessibleName("Ghi bàn phím")
        opt_layout.addWidget(self._keyboard_check)
        opt_layout.addStretch()
        layout.addLayout(opt_layout)

        # Options row 2: context capture (#7)
        opt2_layout = QHBoxLayout()
        self._context_check = QCheckBox("Chụp ảnh ngữ cảnh click")
        self._context_check.setChecked(False)
        self._context_check.setToolTip(
            "Chụp ảnh 80×80px quanh mỗi click để dùng cho Image Matching")
        self._context_check.setAccessibleName("Chụp ảnh ngữ cảnh")
        opt2_layout.addWidget(self._context_check)
        opt2_layout.addStretch()
        layout.addLayout(opt2_layout)

        # Buttons: Record / Pause / Stop
        btn_layout = QHBoxLayout()
        self._record_btn = QPushButton("⏺ Ghi (F9)")
        self._record_btn.setObjectName("dangerButton")
        self._record_btn.setToolTip("Bắt đầu ghi hành động (F9)")
        self._record_btn.clicked.connect(self._start_recording)
        btn_layout.addWidget(self._record_btn)

        self._pause_btn = QPushButton("⏸ Tạm dừng")
        self._pause_btn.setEnabled(False)
        self._pause_btn.setToolTip("Tạm dừng/tiếp tục ghi")
        self._pause_btn.clicked.connect(self._toggle_pause)
        btn_layout.addWidget(self._pause_btn)

        self._stop_btn = QPushButton("⏹ Dừng")
        self._stop_btn.setEnabled(False)
        self._stop_btn.setToolTip("Dừng ghi và thêm vào danh sách")
        self._stop_btn.clicked.connect(self._stop_recording)
        btn_layout.addWidget(self._stop_btn)
        layout.addLayout(btn_layout)

        # Live preview list (#8: improved format)
        self._preview_list = QListWidget()
        self._preview_list.setMaximumHeight(200)
        self._preview_list.setAccessibleName("Xem trước hành động ghi")
        layout.addWidget(self._preview_list)

        # Status
        self._status_label = QLabel("Sẵn sàng ghi")
        self._status_label.setObjectName("subtitleLabel")
        layout.addWidget(self._status_label)

    # -- External hotkey trigger (called from MainWindow) --------------------
    def toggle_recording(self) -> None:
        """Toggle recording on/off — called by F9 hotkey."""
        if self._recorder.is_recording:
            self._stop_recording()
        elif self._record_btn.isEnabled():
            self._start_recording()

    def _start_recording(self) -> None:
        self._recorder = Recorder(
            record_mouse=self._mouse_check.isChecked(),
            record_keyboard=self._keyboard_check.isChecked(),
            capture_context=self._context_check.isChecked(),
        )
        self._preview_list.clear()
        self._record_btn.setEnabled(False)
        self._pause_btn.setEnabled(False)  # enabled after countdown
        self._stop_btn.setEnabled(True)   # Allow cancel during countdown
        self._mouse_check.setEnabled(False)
        self._keyboard_check.setEnabled(False)
        self._context_check.setEnabled(False)
        # 3-2-1 countdown before recording starts
        self._countdown_remaining = 3
        self._countdown_timer = QTimer()
        self._countdown_timer.setInterval(1000)
        self._countdown_timer.timeout.connect(self._countdown_tick)
        self._status_label.setText(
            "⏱ Bắt đầu ghi sau 3... (click Dừng để hủy)")
        self._countdown_timer.start()

    def _countdown_tick(self) -> None:
        """Handle countdown tick."""
        self._countdown_remaining -= 1
        if self._countdown_remaining > 0:
            self._status_label.setText(
                f"⏱ Bắt đầu ghi sau {self._countdown_remaining}...")
        else:
            self._countdown_timer.stop()
            self._stop_btn.setEnabled(True)
            self._pause_btn.setEnabled(True)
            self._recorder.start()
            self._status_label.setText(
                "🔴 Đang ghi... thực hiện thao tác của bạn")
            self._update_timer.start()

    def _toggle_pause(self) -> None:
        """Toggle pause/resume (#5)."""
        if self._recorder.is_paused:
            self._recorder.resume()
            self._pause_btn.setText("⏸ Tạm dừng")
            self._status_label.setText(
                f"🔴 Đang ghi... {self._recorder.action_count} actions")
        else:
            self._recorder.pause()
            self._pause_btn.setText("▶ Tiếp tục")
            self._status_label.setText("⏸ Đã tạm dừng")

    def _stop_recording(self) -> None:
        # Cancel countdown if still running
        if hasattr(self, '_countdown_timer') and self._countdown_timer.isActive():
            self._countdown_timer.stop()
            self._record_btn.setEnabled(True)
            self._stop_btn.setEnabled(False)
            self._pause_btn.setEnabled(False)
            self._mouse_check.setEnabled(True)
            self._keyboard_check.setEnabled(True)
            self._context_check.setEnabled(True)
            self._status_label.setText("⚠ Đã hủy ghi")
            return
        self._update_timer.stop()
        actions = self._recorder.stop()
        self._record_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self._pause_btn.setEnabled(False)
        self._pause_btn.setText("⏸ Tạm dừng")  # reset text
        self._mouse_check.setEnabled(True)
        self._keyboard_check.setEnabled(True)
        self._context_check.setEnabled(True)
        self._status_label.setText(f"✅ Đã ghi {len(actions)} hành động")
        self.recording_finished.emit(actions)

    def _update_preview(self) -> None:
        """Periodically refresh the preview list with new actions (#8)."""
        count = self._recorder.action_count
        current = self._preview_list.count()
        if count > current:
            new_actions = self._recorder.get_actions_snapshot(start=current)
            for action in new_actions:
                # Improved preview: show type + detail (#8)
                name = action.get_display_name()
                atype = getattr(action, 'ACTION_TYPE', '')
                if hasattr(action, 'x') and hasattr(action, 'y'):
                    name += f"  ({action.x}, {action.y})"
                if hasattr(action, 'duration_ms'):
                    name += f"  [{action.duration_ms}ms]"
                item = QListWidgetItem(name)
                self._preview_list.addItem(item)
            self._preview_list.scrollToBottom()
            self._status_label.setText(
                f"🔴 Đang ghi... {count} hành động")
