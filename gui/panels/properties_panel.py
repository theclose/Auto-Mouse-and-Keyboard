"""
PropertiesPanel — Inline read-only properties viewer for the selected action.

Shows key parameters at a glance without needing to open the full editor dialog.
Updates automatically when tree selection changes.
"""

import logging
from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)


class PropertiesPanel(QWidget):
    """Compact read-only panel showing selected action's key properties."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._setup_ui()
        self.clear()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 0)

        self._group = QGroupBox("📋 Thuộc tính")
        self._group.setObjectName("propertiesGroup")
        form = QFormLayout(self._group)
        form.setContentsMargins(8, 12, 8, 8)
        form.setVerticalSpacing(4)
        form.setHorizontalSpacing(8)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._type_label = QLabel()
        self._type_label.setWordWrap(True)
        form.addRow("Loại:", self._type_label)

        self._name_label = QLabel()
        self._name_label.setWordWrap(True)
        form.addRow("Chi tiết:", self._name_label)

        self._params_label = QLabel()
        self._params_label.setWordWrap(True)
        form.addRow("Tham số:", self._params_label)

        self._delay_label = QLabel()
        form.addRow("Delay:", self._delay_label)

        self._repeat_label = QLabel()
        form.addRow("Lặp:", self._repeat_label)

        self._status_label = QLabel()
        form.addRow("Trạng thái:", self._status_label)

        self._desc_label = QLabel()
        self._desc_label.setWordWrap(True)
        form.addRow("Mô tả:", self._desc_label)

        layout.addWidget(self._group)

    def clear(self) -> None:
        """Reset to empty state."""
        self._type_label.setText("—")
        self._name_label.setText("—")
        self._params_label.setText("—")
        self._delay_label.setText("—")
        self._repeat_label.setText("—")
        self._status_label.setText("—")
        self._desc_label.setText("")
        self._group.setTitle("📋 Thuộc tính")

    def set_action(self, action: Any) -> None:
        """Display properties for the given action."""
        if action is None:
            self.clear()
            return

        atype = getattr(action, "ACTION_TYPE", "unknown")
        self._group.setTitle(f"📋 {atype}")

        self._type_label.setText(atype)
        self._name_label.setText(action.get_display_name())

        # Format key parameters
        params = self._format_params(action)
        self._params_label.setText(params or "—")

        delay = action.delay_after
        self._delay_label.setText(f"{delay}ms" if delay > 0 else "0ms")
        self._repeat_label.setText(str(action.repeat_count))

        # Status line: enabled, color, bookmarked, composite children
        status_parts: list[str] = []
        if not action.enabled:
            status_parts.append("✗ Tắt")
        else:
            status_parts.append("✓ Bật")
        if getattr(action, "color", ""):
            status_parts.append(f"🎨 {action.color}")
        if getattr(action, "bookmarked", False):
            status_parts.append("🔖")
        if action.is_composite:
            n = len(action.children)
            status_parts.append(f"📦 {n} sub-action{'s' if n != 1 else ''}")
        on_error = getattr(action, "on_error", "stop")
        if on_error != "stop":
            status_parts.append(f"⚠ {on_error}")
        self._status_label.setText(" | ".join(status_parts))

        self._desc_label.setText(action.description or "")

    @staticmethod
    def _format_params(action: Any) -> str:
        """Extract and format key parameters for the action type."""
        atype = getattr(action, "ACTION_TYPE", "")
        parts: list[str] = []

        if atype == "click":
            x = getattr(action, "x", "?")
            y = getattr(action, "y", "?")
            btn = getattr(action, "button", "left")
            click_type = getattr(action, "click_type", "single")
            parts.append(f"({x}, {y})")
            if btn != "left":
                parts.append(btn)
            if click_type != "single":
                parts.append(click_type)

        elif atype == "type_text":
            text = getattr(action, "text", "")
            if len(text) > 40:
                text = text[:40] + "…"
            parts.append(f'"{text}"')

        elif atype == "hotkey":
            keys = getattr(action, "keys", [])
            parts.append("+".join(keys) if keys else "—")

        elif atype == "wait":
            ms = getattr(action, "duration_ms", 0)
            parts.append(f"{ms}ms")

        elif atype == "scroll":
            x = getattr(action, "x", "?")
            y = getattr(action, "y", "?")
            clicks = getattr(action, "clicks", 0)
            parts.append(f"({x}, {y}) × {clicks}")

        elif atype == "move_mouse":
            x = getattr(action, "x", "?")
            y = getattr(action, "y", "?")
            parts.append(f"→ ({x}, {y})")

        elif atype == "loop_block":
            count = getattr(action, "loop_count", 0)
            parts.append(f"{count}× lặp")

        elif atype == "set_variable":
            var = getattr(action, "variable_name", "?")
            val = getattr(action, "value_expression", "?")
            parts.append(f"{var} = {val}")

        elif atype in ("if_image_found", "if_pixel_color", "if_variable"):
            cond = action.get_display_name()
            parts.append(cond[:60])

        elif atype == "run_macro":
            path = getattr(action, "macro_path", "?")
            parts.append(str(path))

        elif atype == "group":
            n = len(getattr(action, "children", []))
            parts.append(f"{n} actions")

        return ", ".join(parts) if parts else action.get_display_name()[:60]
