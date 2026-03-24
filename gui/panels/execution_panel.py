"""
Execution panel widget — extracted from main_window.py.
Shows progress bar, current action label, loop counter, and execution log.
"""

import datetime as _dt

from PyQt6.QtWidgets import (
    QGroupBox,
    QLabel,
    QListWidget,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)


class ExecutionPanel(QWidget):
    """Shows execution progress, current action, and execution log."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        group = QGroupBox("Thực thi")
        group_layout = QVBoxLayout(group)

        self._action_label = QLabel("Đang chờ")
        self._action_label.setObjectName("subtitleLabel")
        group_layout.addWidget(self._action_label)

        self._progress_bar = QProgressBar()
        self._progress_bar.setFormat("%v / %m")
        group_layout.addWidget(self._progress_bar)

        self._loop_label = QLabel("")
        self._loop_label.setObjectName("subtitleLabel")
        group_layout.addWidget(self._loop_label)

        self._exec_log = QListWidget()
        self._exec_log.setObjectName("execLog")
        self._exec_log.setMaximumHeight(150)
        group_layout.addWidget(self._exec_log)

        layout.addWidget(group)

    # -- Public API (called by main_window engine slots) --------------------

    def on_progress(self, current: int, total: int) -> None:
        """Update progress bar."""
        self._progress_bar.setMaximum(total)
        self._progress_bar.setValue(current)

    def on_action(self, name: str) -> None:
        """Display the currently executing action name."""
        self._action_label.setText(f"▶ {name}")
        ts = _dt.datetime.now().strftime("%H:%M:%S")
        self._exec_log.addItem(f"[{ts}] {name}")
        self._exec_log.scrollToBottom()
        while self._exec_log.count() > 500:
            self._exec_log.takeItem(0)

    def on_loop(self, current: int, total: int) -> None:
        """Display current loop iteration."""
        if total < 0:
            self._loop_label.setText(f"Vòng lặp: {current} / ∞")
        else:
            self._loop_label.setText(f"Vòng lặp: {current} / {total}")

    def reset(self) -> None:
        """Reset to idle state."""
        self._action_label.setText("Đang chờ")
        self._loop_label.setText("")
        self._progress_bar.reset()

    def clear_log(self) -> None:
        """Clear execution log entries."""
        self._exec_log.clear()
