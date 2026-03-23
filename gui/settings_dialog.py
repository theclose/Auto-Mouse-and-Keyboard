"""
Settings dialog – configurable preferences for the application.
"""

import copy
import json
from pathlib import Path
from typing import Any

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QPushButton, QComboBox, QSpinBox, QDoubleSpinBox,
    QCheckBox, QLineEdit, QTabWidget, QWidget, QMessageBox,
    QLabel,
)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QKeySequence


DEFAULT_CONFIG = {
    "hotkeys": {
        "start_stop": "F6",
        "pause_resume": "F7",
        "emergency_stop": "F8",
        "record": "F9",
    },
    "defaults": {
        "click_delay": 100,
        "typing_speed": 50,
        "image_confidence": 0.8,
        "failsafe_enabled": True,
    },
    "ui": {
        "theme": "dark",
        "language": "en",
        "minimize_to_tray": True,
        "window_width": 900,
        "window_height": 650,
    },
    "performance": {
        "screenshot_method": "mss",
        "max_fps": 30,
        "memory_limit_mb": 200,
    },
}

# Keys that are dangerous for Emergency Stop (easy to press accidentally)
_DANGEROUS_ESTOP_KEYS = {
    "A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M",
    "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z",
    "SPACE", "RETURN", "TAB", "BACK", "ESC", "0", "1", "2", "3", "4",
    "5", "6", "7", "8", "9",
}

# Qt Key constants that are modifier-only (should be ignored as main key)
_MODIFIER_QT_KEYS = {
    Qt.Key.Key_Control, Qt.Key.Key_Shift, Qt.Key.Key_Alt,
    Qt.Key.Key_Meta, Qt.Key.Key_AltGr,
}


def load_config(path: str = "config.json") -> dict[str, Any]:
    """Load config from file, falling back to defaults."""
    p = Path(path)
    if p.exists():
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            merged = _deep_merge(DEFAULT_CONFIG, data)
            return merged
        except Exception:
            pass
    return copy.deepcopy(DEFAULT_CONFIG)


def save_config(config: dict[str, Any], path: str = "config.json") -> None:
    """Save config to file."""
    p = Path(path)
    p.write_text(json.dumps(config, indent=2, ensure_ascii=False),
                 encoding="utf-8")


def _deep_merge(defaults: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    result = dict(defaults)
    for k, v in overrides.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


# ---------------------------------------------------------------------------
# Press-to-Bind Widget
# ---------------------------------------------------------------------------

class HotkeyEdit(QLineEdit):
    """Press-to-bind hotkey capture widget.

    Click the field, then press any key or key combination.
    The captured combo is displayed automatically (e.g. "CTRL+SHIFT+F5").
    """

    def __init__(self, current: str = "", parent: Any = None) -> None:
        super().__init__(current, parent)
        self.setReadOnly(True)
        self.setPlaceholderText("Click rồi ấn phím...")
        self._capturing = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event: Any) -> None:
        self._capturing = True
        self.setText("⌨ Ấn phím...")
        self.setStyleSheet("border: 2px solid #6c6cff; background: #2a2a40;")
        self.setFocus()

    def keyPressEvent(self, event: Any) -> None:
        if not self._capturing:
            return

        key = event.key()

        # Ignore lone modifier press — wait for the main key
        if key in _MODIFIER_QT_KEYS:
            return

        # Build combo string
        parts: list[str] = []
        mods = event.modifiers()
        if mods & Qt.KeyboardModifier.ControlModifier:
            parts.append("CTRL")
        if mods & Qt.KeyboardModifier.ShiftModifier:
            parts.append("SHIFT")
        if mods & Qt.KeyboardModifier.AltModifier:
            parts.append("ALT")

        key_name = QKeySequence(key).toString().upper()
        if key_name:
            parts.append(key_name)

        combo = "+".join(parts) if parts else ""
        if combo:
            self.setText(combo)

        self._capturing = False
        self.setStyleSheet("")

    def focusOutEvent(self, event: Any) -> None:
        if self._capturing:
            self._capturing = False
            # Restore previous value if user clicked away without pressing
            if self.text() == "⌨ Ấn phím...":
                self.setText("")
            self.setStyleSheet("")
        super().focusOutEvent(event)


# ---------------------------------------------------------------------------
# Settings Dialog
# ---------------------------------------------------------------------------

class SettingsDialog(QDialog):
    """Settings configuration dialog with tabbed layout."""
    config_saved = pyqtSignal(object)  # emits config dict before accept

    def __init__(self, config: dict[str, Any], parent: Any = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Cài đặt")
        self.setMinimumWidth(460)
        self.setModal(True)
        self._config: dict[str, Any] = dict(config)
        self._widgets: dict[str, Any] = {}
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        tabs = QTabWidget()

        # --- Hotkeys tab ---
        hotkey_tab = QWidget()
        hk_layout = QFormLayout(hotkey_tab)
        hk = self._config.get("hotkeys", {})

        hint = QLabel("💡 Click ô → ấn phím hoặc tổ hợp phím để gán")
        hint.setObjectName("subtitleLabel")
        hint.setStyleSheet("color: #888; font-size: 11px; margin-bottom: 4px;")
        hk_layout.addRow(hint)

        for key, label in [("start_stop", "Chạy / Dừng:"),
                           ("pause_resume", "Tạm dừng / Tiếp:"),
                           ("emergency_stop", "Dừng khẩn cấp:"),
                           ("record", "Ghi:")]:
            edit = HotkeyEdit(hk.get(key, ""))
            hk_layout.addRow(label, edit)
            self._widgets[f"hotkeys.{key}"] = edit

        tabs.addTab(hotkey_tab, "⌨ Phím tắt")

        # --- Defaults tab ---
        defaults_tab = QWidget()
        df_layout = QFormLayout(defaults_tab)
        df = self._config.get("defaults", {})

        click_delay = QSpinBox()
        click_delay.setRange(0, 5000)
        click_delay.setSuffix(" ms")
        click_delay.setValue(df.get("click_delay", 100))
        df_layout.addRow("Trễ click:", click_delay)
        self._widgets["defaults.click_delay"] = click_delay

        typing_speed = QSpinBox()
        typing_speed.setRange(1, 200)
        typing_speed.setSuffix(" cps")
        typing_speed.setValue(df.get("typing_speed", 50))
        df_layout.addRow("Tốc độ gõ:", typing_speed)
        self._widgets["defaults.typing_speed"] = typing_speed

        img_conf = QDoubleSpinBox()
        img_conf.setRange(0.1, 1.0)
        img_conf.setSingleStep(0.05)
        img_conf.setValue(df.get("image_confidence", 0.8))
        df_layout.addRow("Độ chính xác ảnh:", img_conf)
        self._widgets["defaults.image_confidence"] = img_conf

        failsafe = QCheckBox("Bật (di chuột vào góc để dừng)")
        failsafe.setChecked(df.get("failsafe_enabled", True))
        df_layout.addRow("An toàn:", failsafe)
        self._widgets["defaults.failsafe_enabled"] = failsafe

        tabs.addTab(defaults_tab, "Mặc định")

        # --- UI tab ---
        ui_tab = QWidget()
        ui_layout = QFormLayout(ui_tab)
        ui = self._config.get("ui", {})

        theme = QComboBox()
        theme.addItems(["auto", "dark", "light"])
        theme.setCurrentText(ui.get("theme", "auto"))
        ui_layout.addRow("Giao diện:", theme)
        self._widgets["ui.theme"] = theme

        tray_check = QCheckBox("Thu nhỏ vào khay hệ thống")
        tray_check.setChecked(ui.get("minimize_to_tray", True))
        ui_layout.addRow("", tray_check)
        self._widgets["ui.minimize_to_tray"] = tray_check

        tabs.addTab(ui_tab, "Giao diện")

        layout.addWidget(tabs)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        reset_btn = QPushButton("Đặt lại")
        reset_btn.clicked.connect(self._reset_defaults)
        btn_layout.addWidget(reset_btn)

        cancel_btn = QPushButton("Hủy")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        save_btn = QPushButton("Lưu")
        save_btn.setObjectName("primaryButton")
        save_btn.clicked.connect(self._on_save)
        btn_layout.addWidget(save_btn)

        layout.addLayout(btn_layout)

    # -- Validation ----------------------------------------------------------

    def _validate_hotkeys(self) -> str | None:
        """Return error message if hotkey conflicts found, else None."""
        seen: dict[str, str] = {}
        labels = {
            "start_stop": "Chạy/Dừng",
            "pause_resume": "Tạm dừng",
            "emergency_stop": "Dừng khẩn cấp",
            "record": "Ghi",
        }

        for name in ("start_stop", "pause_resume", "emergency_stop", "record"):
            widget = self._widgets.get(f"hotkeys.{name}")
            if widget is None:
                continue
            val = widget.text().strip().upper()

            # Empty check
            if not val or val == "⌨ ẤN PHÍM...":
                return f"Hotkey '{labels[name]}' không được để trống"

            # Duplicate check
            if val in seen:
                return (f"Trùng hotkey '{val}': "
                        f"'{labels[seen[val]]}' và '{labels[name]}'")
            seen[val] = name

        # Safety check for emergency stop
        estop_widget = self._widgets.get("hotkeys.emergency_stop")
        if estop_widget:
            estop_val = estop_widget.text().strip().upper()
            if estop_val in _DANGEROUS_ESTOP_KEYS:
                return (f"⚠ '{estop_val}' dễ ấn nhầm cho Dừng khẩn cấp.\n"
                        f"Nên dùng phím F (F1-F12) hoặc tổ hợp phím (CTRL+...).")

        return None

    # -- Save / Reset --------------------------------------------------------

    def _on_save(self) -> None:
        """Read widget values back into config dict."""
        # Validate hotkeys first
        error = self._validate_hotkeys()
        if error:
            QMessageBox.warning(self, "Lỗi Hotkey", error)
            return

        for key, widget in self._widgets.items():
            parts = key.split(".")
            section, name = parts[0], parts[1]

            if section not in self._config:
                self._config[section] = {}

            if isinstance(widget, QSpinBox):
                self._config[section][name] = widget.value()
            elif isinstance(widget, QDoubleSpinBox):
                self._config[section][name] = widget.value()
            elif isinstance(widget, (QLineEdit, HotkeyEdit)):
                self._config[section][name] = widget.text().strip().upper()
            elif isinstance(widget, QComboBox):
                self._config[section][name] = widget.currentText()
            elif isinstance(widget, QCheckBox):
                self._config[section][name] = widget.isChecked()

        self.config_saved.emit(self._config)  # fire BEFORE accept
        self.accept()

    def _reset_defaults(self) -> None:
        self._config = copy.deepcopy(DEFAULT_CONFIG)
        # Remove old layout and widgets before re-creating
        old_layout = self.layout()
        if old_layout:
            while old_layout.count():
                item = old_layout.takeAt(0)
                if item is None:
                    break
                widget = item.widget()
                if widget:
                    widget.deleteLater()
            from PyQt6.sip import delete
            delete(old_layout)
        self._widgets.clear()
        self._setup_ui()

    def get_config(self) -> dict[str, Any]:
        return self._config

