"""
Mini-Map widget — compact overview of macro structure showing
all actions with execution progress highlighting.
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QGroupBox,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core.action import Action

# Action type → color mapping
_TYPE_COLORS = {
    "mouse_click": "#3498db",
    "mouse_double_click": "#3498db",
    "mouse_right_click": "#3498db",
    "mouse_move": "#3498db",
    "mouse_drag": "#3498db",
    "mouse_scroll": "#3498db",
    "key_press": "#9b59b6",
    "key_combo": "#9b59b6",
    "type_text": "#9b59b6",
    "hotkey": "#9b59b6",
    "delay": "#95a5a6",
    "wait_for_image": "#e67e22",
    "click_on_image": "#e67e22",
    "image_exists": "#e67e22",
    "take_screenshot": "#e67e22",
    "loop_block": "#2ecc71",
    "if_image_found": "#f39c12",
    "if_pixel_color": "#f39c12",
    "if_variable": "#f39c12",
    "set_variable": "#1abc9c",
    "split_string": "#1abc9c",
    "comment": "#7f8c8d",
    "activate_window": "#e74c3c",
    "log_to_file": "#16a085",
    "run_macro": "#8e44ad",
    "capture_text": "#d35400",
}

# Type icons
_TYPE_ICONS = {
    "mouse_click": "🖱",
    "mouse_double_click": "🖱",
    "mouse_right_click": "🖱",
    "mouse_move": "🖱",
    "mouse_drag": "🖱",
    "mouse_scroll": "🖱",
    "key_press": "⌨",
    "key_combo": "⌨",
    "type_text": "⌨",
    "hotkey": "⌨",
    "delay": "⏱",
    "wait_for_image": "🖼",
    "click_on_image": "🖼",
    "image_exists": "🖼",
    "loop_block": "🔁",
    "if_image_found": "❓",
    "if_pixel_color": "🎯",
    "if_variable": "📏",
    "set_variable": "📊",
    "comment": "💬",
    "activate_window": "🖥",
    "log_to_file": "📝",
    "run_macro": "▶️",
    "capture_text": "🔍",
}


class MiniMapWidget(QWidget):
    """Compact visual overview of macro with execution highlighting."""

    action_clicked = pyqtSignal(int)  # emits action index when clicked

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._actions: list[Action] = []
        self._current_idx: int = -1
        self._completed_idx: int = -1  # all up to this index are done
        self._labels: list[QLabel] = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self._group = QGroupBox("🗺 Mini-Map")
        group_layout = QVBoxLayout(self._group)
        group_layout.setContentsMargins(4, 12, 4, 4)
        group_layout.setSpacing(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMaximumHeight(250)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(2, 2, 2, 2)
        self._content_layout.setSpacing(1)

        scroll.setWidget(self._content)
        group_layout.addWidget(scroll)
        outer.addWidget(self._group)

    def set_actions(self, actions: list[Action]) -> None:
        """Rebuild the mini-map from an action list."""
        self._actions = actions
        self._current_idx = -1
        self._completed_idx = -1

        # Clear existing labels
        for label in self._labels:
            label.deleteLater()
        self._labels.clear()

        for i, action in enumerate(actions):
            atype = getattr(action, "ACTION_TYPE", "")
            icon = _TYPE_ICONS.get(atype, "•")
            color = _TYPE_COLORS.get(atype, "#888888")
            name = action.get_display_name()
            if len(name) > 30:
                name = name[:28] + "…"

            label = QLabel(f"{icon} {name}")
            label.setStyleSheet(
                f"padding: 2px 4px; border-left: 3px solid {color}; "
                f"font-size: 8pt; background: transparent; "
                f"border-radius: 0px;"
            )
            label.setToolTip(f"#{i+1}: {action.get_display_name()}")
            label.setCursor(Qt.CursorShape.PointingHandCursor)
            # Capture index for click
            idx = i
            label.mousePressEvent = lambda e, x=idx: self.action_clicked.emit(x)
            self._content_layout.addWidget(label)
            self._labels.append(label)

        self._content_layout.addStretch()

    def highlight_action(self, idx: int) -> None:
        """Highlight the currently executing action."""
        self._completed_idx = idx - 1
        self._current_idx = idx

        for i, label in enumerate(self._labels):
            atype = getattr(self._actions[i], "ACTION_TYPE", "") if i < len(self._actions) else ""
            color = _TYPE_COLORS.get(atype, "#888888")

            if i == idx:
                # Currently running — bright highlight
                label.setStyleSheet(
                    "padding: 2px 4px; border-left: 3px solid #27ae60; "
                    "font-size: 8pt; font-weight: bold; "
                    "background: rgba(39, 174, 96, 0.2); "
                    "color: #2ecc71; border-radius: 0px;"
                )
            elif i < idx:
                # Completed — dimmed
                label.setStyleSheet(
                    f"padding: 2px 4px; border-left: 3px solid {color}; "
                    f"font-size: 8pt; color: #666; "
                    f"background: transparent; border-radius: 0px;"
                )
            else:
                # Pending — normal
                label.setStyleSheet(
                    f"padding: 2px 4px; border-left: 3px solid {color}; "
                    f"font-size: 8pt; background: transparent; "
                    f"border-radius: 0px;"
                )

    def reset(self) -> None:
        """Reset all highlights."""
        self._current_idx = -1
        self._completed_idx = -1
        for i, label in enumerate(self._labels):
            atype = getattr(self._actions[i], "ACTION_TYPE", "") if i < len(self._actions) else ""
            color = _TYPE_COLORS.get(atype, "#888888")
            label.setStyleSheet(
                f"padding: 2px 4px; border-left: 3px solid {color}; "
                f"font-size: 8pt; background: transparent; "
                f"border-radius: 0px;"
            )
