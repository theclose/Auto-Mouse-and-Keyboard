"""
Settings dialog – configurable preferences for the application.
"""

import json
from pathlib import Path
from typing import Any

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QPushButton, QComboBox, QSpinBox, QDoubleSpinBox,
    QCheckBox, QLineEdit, QTabWidget, QWidget,
)
from PyQt6.QtCore import pyqtSignal


DEFAULT_CONFIG = {
    "hotkeys": {
        "start_stop": "F6",
        "pause_resume": "F7",
        "emergency_stop": "F8",
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


def load_config(path: str = "config.json") -> dict[str, Any]:
    """Load config from file, falling back to defaults."""
    p = Path(path)
    if p.exists():
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Merge with defaults so missing keys get filled in
            merged = _deep_merge(DEFAULT_CONFIG, data)
            return merged
        except Exception:
            pass
    return dict(DEFAULT_CONFIG)


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

        for key, label in [("start_stop", "Start / Stop:"),
                           ("pause_resume", "Pause / Resume:"),
                           ("emergency_stop", "Emergency Stop:")]:
            edit = QLineEdit(hk.get(key, ""))
            edit.setPlaceholderText("e.g. F6")
            hk_layout.addRow(label, edit)
            self._widgets[f"hotkeys.{key}"] = edit

        tabs.addTab(hotkey_tab, "Hotkeys")

        # --- Defaults tab ---
        defaults_tab = QWidget()
        df_layout = QFormLayout(defaults_tab)
        df = self._config.get("defaults", {})

        click_delay = QSpinBox()
        click_delay.setRange(0, 5000)
        click_delay.setSuffix(" ms")
        click_delay.setValue(df.get("click_delay", 100))
        df_layout.addRow("Click Delay:", click_delay)
        self._widgets["defaults.click_delay"] = click_delay

        typing_speed = QSpinBox()
        typing_speed.setRange(1, 200)
        typing_speed.setSuffix(" cps")
        typing_speed.setValue(df.get("typing_speed", 50))
        df_layout.addRow("Typing Speed:", typing_speed)
        self._widgets["defaults.typing_speed"] = typing_speed

        img_conf = QDoubleSpinBox()
        img_conf.setRange(0.1, 1.0)
        img_conf.setSingleStep(0.05)
        img_conf.setValue(df.get("image_confidence", 0.8))
        df_layout.addRow("Image Confidence:", img_conf)
        self._widgets["defaults.image_confidence"] = img_conf

        failsafe = QCheckBox("Enable fail-safe (move mouse to corner)")
        failsafe.setChecked(df.get("failsafe_enabled", True))
        df_layout.addRow("Fail-Safe:", failsafe)
        self._widgets["defaults.failsafe_enabled"] = failsafe

        tabs.addTab(defaults_tab, "Defaults")

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

        reset_btn = QPushButton("Reset Defaults")
        reset_btn.clicked.connect(self._reset_defaults)
        btn_layout.addWidget(reset_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        save_btn = QPushButton("Save")
        save_btn.setObjectName("primaryButton")
        save_btn.clicked.connect(self._on_save)
        btn_layout.addWidget(save_btn)

        layout.addLayout(btn_layout)

    def _on_save(self) -> None:
        """Read widget values back into config dict."""
        for key, widget in self._widgets.items():
            parts = key.split(".")
            section, name = parts[0], parts[1]

            if isinstance(widget, QSpinBox):
                self._config[section][name] = widget.value()
            elif isinstance(widget, QDoubleSpinBox):
                self._config[section][name] = widget.value()
            elif isinstance(widget, QLineEdit):
                self._config[section][name] = widget.text()
            elif isinstance(widget, QComboBox):
                self._config[section][name] = widget.currentText()
            elif isinstance(widget, QCheckBox):
                self._config[section][name] = widget.isChecked()

        self.config_saved.emit(self._config)  # fire BEFORE accept
        self.accept()

    def _reset_defaults(self) -> None:
        import copy
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
