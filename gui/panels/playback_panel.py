"""
Playback control panel — extracted from main_window.py.
Contains Play/Pause/Stop, step debug, loop settings, and speed control.
"""

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


class PlaybackPanel(QWidget):
    """Playback controls: play/pause/stop, loop, speed, step debug."""

    # Signals emitted to main_window coordinator
    play_requested = pyqtSignal()
    pause_requested = pyqtSignal()
    stop_requested = pyqtSignal()
    step_toggled = pyqtSignal(bool)
    step_next_requested = pyqtSignal()
    speed_changed = pyqtSignal(float)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # ── Play/Pause/Stop ────────────────────────────────────
        play_group = QGroupBox("Điều khiển")
        play_vbox = QVBoxLayout(play_group)

        self._play_btn = QPushButton("▶  P L A Y")
        self._play_btn.setObjectName("playButton")
        self._play_btn.setMinimumHeight(48)
        self._play_btn.setToolTip("Bắt đầu chạy macro (F6)")
        self._play_btn.setAccessibleName("Chạy macro")
        self._play_btn.clicked.connect(self.play_requested.emit)
        play_vbox.addWidget(self._play_btn)

        ctrl_row = QHBoxLayout()
        self._pause_btn = QPushButton("⏸ Tạm dừng (F7)")
        self._pause_btn.setObjectName("controlButton")
        self._pause_btn.setEnabled(False)
        self._pause_btn.setToolTip("Tạm dừng (F7)")
        self._pause_btn.setAccessibleName("Tạm dừng macro")
        self._pause_btn.clicked.connect(self.pause_requested.emit)
        ctrl_row.addWidget(self._pause_btn)

        self._stop_btn = QPushButton("⏹ Dừng (F8)")
        self._stop_btn.setObjectName("dangerButton")
        self._stop_btn.setEnabled(False)
        self._stop_btn.setToolTip("Dừng hoàn toàn (F8)")
        self._stop_btn.setAccessibleName("Dừng macro")
        self._stop_btn.clicked.connect(self.stop_requested.emit)
        ctrl_row.addWidget(self._stop_btn)
        play_vbox.addLayout(ctrl_row)

        # Step debug controls
        step_row = QHBoxLayout()
        self._step_toggle = QCheckBox("🐛 Chạy từng bước")
        self._step_toggle.setToolTip("Bật chế độ chạy từng bước")
        self._step_toggle.setAccessibleName("Chế độ từng bước")
        self._step_toggle.toggled.connect(self.step_toggled.emit)
        step_row.addWidget(self._step_toggle)

        self._step_next_btn = QPushButton("⏭ Bước tiếp")
        self._step_next_btn.setEnabled(False)
        self._step_next_btn.setToolTip("Thực thi bước tiếp theo")
        self._step_next_btn.setAccessibleName("Bước tiếp theo")
        self._step_next_btn.clicked.connect(self.step_next_requested.emit)
        step_row.addWidget(self._step_next_btn)
        play_vbox.addLayout(step_row)

        layout.addWidget(play_group)

        # ── Loop settings ──────────────────────────────────────
        self._loop_group = QGroupBox("Cài đặt lặp")
        loop_form = QFormLayout(self._loop_group)

        self._loop_spin = QSpinBox()
        self._loop_spin.setRange(0, 999999)
        self._loop_spin.setValue(1)
        self._loop_spin.setSpecialValueText("∞ Vô hạn")
        self._loop_spin.setAccessibleName("Số lần lặp")
        loop_form.addRow("Số lần lặp:", self._loop_spin)

        self._loop_delay_spin = QSpinBox()
        self._loop_delay_spin.setRange(0, 60000)
        self._loop_delay_spin.setSuffix(" ms")
        self._loop_delay_spin.setValue(0)
        self._loop_delay_spin.setAccessibleName("Độ trễ giữa các lần lặp")
        loop_form.addRow("Độ trễ lặp:", self._loop_delay_spin)

        self._stop_on_error_check = QCheckBox("Dừng khi lỗi")
        self._stop_on_error_check.setToolTip("Dừng thực thi khi action bị lỗi thay vì tiếp tục")
        self._stop_on_error_check.setChecked(False)
        self._stop_on_error_check.setAccessibleName("Dừng khi gặp lỗi")
        loop_form.addRow("", self._stop_on_error_check)

        self._speed_spin = QDoubleSpinBox()
        self._speed_spin.setRange(0.1, 5.0)
        self._speed_spin.setValue(1.0)
        self._speed_spin.setSingleStep(0.1)
        self._speed_spin.setDecimals(1)
        self._speed_spin.setSuffix("×")
        self._speed_spin.setToolTip("Tốc độ (0.1× chậm → 5× nhanh)\n" "Thay đổi có hiệu lực ngay khi đang chạy")
        self._speed_spin.setAccessibleName("Tốc độ chạy")
        self._speed_spin.valueChanged.connect(self.speed_changed.emit)
        loop_form.addRow("Tốc độ:", self._speed_spin)

        self._jitter_spin = QSpinBox()
        self._jitter_spin.setRange(0, 50)
        self._jitter_spin.setValue(0)
        self._jitter_spin.setSuffix("%")
        self._jitter_spin.setToolTip("Biến thiên delay ngẫu nhiên (±X%)\n"
                                     "Giúp thao tác tự nhiên hơn, tránh rate-limit")
        self._jitter_spin.setAccessibleName("Biến thiên delay")
        loop_form.addRow("Biến thiên:", self._jitter_spin)

        layout.addWidget(self._loop_group)

    # -- Public API ---------------------------------------------------------

    @property
    def loop_count(self) -> int:
        return self._loop_spin.value()

    @loop_count.setter
    def loop_count(self, v: int) -> None:
        self._loop_spin.setValue(v)

    @property
    def loop_delay_ms(self) -> int:
        return self._loop_delay_spin.value()

    @loop_delay_ms.setter
    def loop_delay_ms(self, v: int) -> None:
        self._loop_delay_spin.setValue(v)

    @property
    def stop_on_error(self) -> bool:
        return self._stop_on_error_check.isChecked()

    @property
    def speed_factor(self) -> float:
        return self._speed_spin.value()

    @property
    def step_mode(self) -> bool:
        return self._step_toggle.isChecked()

    def set_running(self, running: bool) -> None:
        """Update UI state for running/stopped."""
        self._play_btn.setEnabled(not running)
        self._pause_btn.setEnabled(running)
        self._stop_btn.setEnabled(running)
        self._loop_group.setEnabled(not running)
        self._step_next_btn.setEnabled(running and self._step_toggle.isChecked())

    def set_pause_text(self, text: str) -> None:
        """Update pause button text (e.g., '▶ Tiếp tục')."""
        self._pause_btn.setText(text)
