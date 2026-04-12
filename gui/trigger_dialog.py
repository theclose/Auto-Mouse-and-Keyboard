"""
Trigger management dialog — configure schedule and window-focus triggers.
"""

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from core.trigger_manager import TriggerManager
from core.triggers import TriggerConfig


class TriggerDialog(QDialog):
    """Dialog for managing automation triggers."""

    def __init__(self, trigger_mgr: TriggerManager, macros_dir: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        self._mgr = trigger_mgr
        self._macros_dir = macros_dir
        self.setWindowTitle("⏰ Quản lý Trigger")
        self.setMinimumSize(560, 480)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        self._build_ui()
        self._refresh_list()

    def _build_ui(self) -> None:
        main_layout = QHBoxLayout(self)

        # -- Left: trigger list --
        left = QVBoxLayout()
        left.addWidget(QLabel("<b>Triggers</b>"))

        self._list = QListWidget()
        self._list.currentRowChanged.connect(self._on_selection_changed)
        left.addWidget(self._list)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("➕ Thêm")
        add_btn.clicked.connect(self._on_add)
        btn_row.addWidget(add_btn)

        del_btn = QPushButton("🗑 Xóa")
        del_btn.clicked.connect(self._on_delete)
        btn_row.addWidget(del_btn)
        left.addLayout(btn_row)

        main_layout.addLayout(left, 1)

        # -- Right: trigger config --
        right = QVBoxLayout()

        # Type selector
        type_group = QGroupBox("Loại trigger")
        type_form = QFormLayout(type_group)
        self._type_combo = QComboBox()
        self._type_combo.addItems(["schedule", "window_focus"])
        self._type_combo.currentTextChanged.connect(self._on_type_changed)
        type_form.addRow("Loại:", self._type_combo)

        self._macro_edit = QLineEdit()
        self._macro_edit.setPlaceholderText("Chọn file macro...")
        self._macro_edit.setReadOnly(True)
        macro_row = QHBoxLayout()
        macro_row.addWidget(self._macro_edit)
        browse_btn = QPushButton("📂")
        browse_btn.setFixedWidth(32)
        browse_btn.clicked.connect(self._on_browse_macro)
        macro_row.addWidget(browse_btn)
        type_form.addRow("Macro:", macro_row)

        self._enabled_check = QCheckBox("Kích hoạt")
        self._enabled_check.setChecked(True)
        type_form.addRow("", self._enabled_check)

        self._cooldown_spin = QSpinBox()
        self._cooldown_spin.setRange(1, 3600)
        self._cooldown_spin.setValue(5)
        self._cooldown_spin.setSuffix(" giây")
        type_form.addRow("Cooldown:", self._cooldown_spin)
        right.addWidget(type_group)

        # -- Schedule params --
        self._schedule_group = QGroupBox("Lịch trình")
        sched_form = QFormLayout(self._schedule_group)

        self._mode_combo = QComboBox()
        self._mode_combo.addItems(["interval", "daily", "weekday"])
        self._mode_combo.currentTextChanged.connect(self._on_mode_changed)
        sched_form.addRow("Chế độ:", self._mode_combo)

        self._interval_spin = QSpinBox()
        self._interval_spin.setRange(1, 1440)
        self._interval_spin.setValue(5)
        self._interval_spin.setSuffix(" phút")
        sched_form.addRow("Mỗi:", self._interval_spin)

        self._time_edit = QTimeEdit()
        self._time_edit.setDisplayFormat("HH:mm")
        sched_form.addRow("Thời gian:", self._time_edit)

        # Weekday checkboxes
        weekday_widget = QWidget()
        weekday_layout = QHBoxLayout(weekday_widget)
        weekday_layout.setContentsMargins(0, 0, 0, 0)
        self._weekday_checks: list[QCheckBox] = []
        for i, label in enumerate(["T2", "T3", "T4", "T5", "T6", "T7", "CN"]):
            cb = QCheckBox(label)
            cb.setChecked(i < 5)  # Mon-Fri default
            self._weekday_checks.append(cb)
            weekday_layout.addWidget(cb)
        sched_form.addRow("Ngày:", weekday_widget)
        right.addWidget(self._schedule_group)

        # -- Window focus params --
        self._window_group = QGroupBox("Cửa sổ mục tiêu")
        win_form = QFormLayout(self._window_group)

        self._match_type_combo = QComboBox()
        self._match_type_combo.addItems(["process", "title_contains", "title_regex"])
        win_form.addRow("So khớp:", self._match_type_combo)

        self._match_value = QLineEdit()
        self._match_value.setPlaceholderText("vd: notepad.exe hoặc tiêu đề cửa sổ")
        win_form.addRow("Giá trị:", self._match_value)
        right.addWidget(self._window_group)

        # Save button
        save_btn = QPushButton("💾 Lưu trigger")
        save_btn.clicked.connect(self._on_save)
        right.addWidget(save_btn)

        right.addStretch()
        main_layout.addLayout(right, 2)

        # Initial visibility
        self._on_type_changed(self._type_combo.currentText())

    # -- UI callbacks ---------------------------------------------------------

    def _on_type_changed(self, trigger_type: str) -> None:
        self._schedule_group.setVisible(trigger_type == "schedule")
        self._window_group.setVisible(trigger_type == "window_focus")

    def _on_mode_changed(self, mode: str) -> None:
        self._interval_spin.setVisible(mode == "interval")
        self._time_edit.setVisible(mode in ("daily", "weekday"))
        for cb in self._weekday_checks:
            cb.setVisible(mode == "weekday")

    def _on_browse_macro(self) -> None:
        start_dir = self._macros_dir or str(Path.home())
        path, _ = QFileDialog.getOpenFileName(
            self, "Chọn file macro", start_dir, "Macro Files (*.json)"
        )
        if path:
            self._macro_edit.setText(path)

    def _on_add(self) -> None:
        config = TriggerConfig(trigger_type="schedule")
        tid = self._mgr.add_trigger(config)
        self._refresh_list()
        # Select the new item
        for i in range(self._list.count()):
            item = self._list.item(i)
            if item and item.data(Qt.ItemDataRole.UserRole) == tid:
                self._list.setCurrentRow(i)
                break

    def _on_delete(self) -> None:
        item = self._list.currentItem()
        if not item:
            return
        tid = item.data(Qt.ItemDataRole.UserRole)
        self._mgr.remove_trigger(tid)
        self._refresh_list()

    def _on_selection_changed(self, row: int) -> None:
        if row < 0:
            return
        item = self._list.item(row)
        if not item:
            return
        tid = item.data(Qt.ItemDataRole.UserRole)
        triggers = self._mgr.get_triggers()
        config = next((t for t in triggers if t.id == tid), None)
        if not config:
            return
        self._load_config(config)

    def _load_config(self, config: TriggerConfig) -> None:
        """Load trigger config into form fields."""
        self._type_combo.setCurrentText(config.trigger_type)
        self._macro_edit.setText(config.macro_file)
        self._enabled_check.setChecked(config.enabled)
        self._cooldown_spin.setValue(config.cooldown_ms // 1000)

        params = config.params
        if config.trigger_type == "schedule":
            self._mode_combo.setCurrentText(params.get("mode", "interval"))
            self._interval_spin.setValue(params.get("interval_min", 5))
            time_str = params.get("time", "08:00")
            from PyQt6.QtCore import QTime
            h, m = (int(x) for x in time_str.split(":"))
            self._time_edit.setTime(QTime(h, m))
            weekdays = params.get("weekdays", [0, 1, 2, 3, 4])
            for i, cb in enumerate(self._weekday_checks):
                cb.setChecked(i in weekdays)
        elif config.trigger_type == "window_focus":
            self._match_type_combo.setCurrentText(params.get("match_type", "title_contains"))
            self._match_value.setText(params.get("match_value", ""))

    def _on_save(self) -> None:
        """Save current form values to the selected trigger."""
        item = self._list.currentItem()
        if not item:
            QMessageBox.warning(self, "Chưa chọn", "Vui lòng chọn hoặc thêm trigger trước.")
            return

        tid = item.data(Qt.ItemDataRole.UserRole)
        triggers = self._mgr.get_triggers()
        config = next((t for t in triggers if t.id == tid), None)
        if not config:
            return

        config.trigger_type = self._type_combo.currentText()
        config.macro_file = self._macro_edit.text()
        config.enabled = self._enabled_check.isChecked()
        config.cooldown_ms = self._cooldown_spin.value() * 1000

        if config.trigger_type == "schedule":
            mode = self._mode_combo.currentText()
            config.params = {
                "mode": mode,
                "interval_min": self._interval_spin.value(),
                "time": self._time_edit.time().toString("HH:mm"),
                "weekdays": [i for i, cb in enumerate(self._weekday_checks) if cb.isChecked()],
            }
        elif config.trigger_type == "window_focus":
            config.params = {
                "match_type": self._match_type_combo.currentText(),
                "match_value": self._match_value.text(),
            }

        self._refresh_list()
        QMessageBox.information(self, "Đã lưu", f"Trigger {tid} đã được cập nhật.")

    def _refresh_list(self) -> None:
        """Refresh the trigger list widget."""
        current_id = ""
        if self._list.currentItem():
            current_id = self._list.currentItem().data(Qt.ItemDataRole.UserRole)

        self._list.clear()
        for t in self._mgr.get_triggers():
            icon = "⏰" if t.trigger_type == "schedule" else "🖥"
            status = "✅" if t.enabled else "❌"
            macro_name = Path(t.macro_file).stem if t.macro_file else "(chưa chọn)"
            label = f"{icon} {status} {t.trigger_type} → {macro_name}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, t.id)
            self._list.addItem(item)
            if t.id == current_id:
                self._list.setCurrentItem(item)
