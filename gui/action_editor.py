"""
Action Editor – dialog and panel for adding/editing macro actions.
Provides a user-friendly form for each action type with appropriate widgets.
"""

import logging
import os
from typing import Any, Callable, Optional

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from core.action import Action, get_action_class
from gui.coordinate_picker import CoordinatePickerOverlay
from gui.image_capture import ImageCaptureOverlay

logger = logging.getLogger(__name__)

# Grouped action categories for the type selector
ACTION_CATEGORIES: list[tuple[str, list[tuple[str, str]]]] = [
    (
        "🖱 Mouse",
        [
            ("mouse_click", "Click"),
            ("mouse_double_click", "Double Click"),
            ("mouse_right_click", "Right Click"),
            ("mouse_move", "Move"),
            ("mouse_drag", "Drag"),
            ("mouse_scroll", "Scroll"),
        ],
    ),
    (
        "⌨ Keyboard",
        [
            ("key_press", "Key Press"),
            ("key_combo", "Key Combo"),
            ("type_text", "Type Text"),
            ("hotkey", "Hotkey"),
        ],
    ),
    (
        "🖼 Image",
        [
            ("wait_for_image", "Wait for Image"),
            ("click_on_image", "Click on Image"),
            ("image_exists", "Image Exists"),
            ("take_screenshot", "Take Screenshot"),
        ],
    ),
    (
        "🎨 Pixel",
        [
            ("check_pixel_color", "Check Pixel Color"),
            ("wait_for_color", "Wait for Color"),
        ],
    ),
    (
        "⏱ Flow Control",
        [
            ("delay", "Delay"),
            ("loop_block", "Loop Block"),
            ("if_image_found", "If Image Found"),
            ("if_pixel_color", "If Pixel Color"),
            ("if_variable", "If Variable"),
        ],
    ),
    (
        "📊 Variables",
        [
            ("set_variable", "Set Variable"),
            ("split_string", "Split String"),
            ("comment", "Comment / Label"),
        ],
    ),
    (
        "🖥 System",
        [
            ("activate_window", "Activate Window"),
            ("log_to_file", "Log to File"),
            ("read_clipboard", "Read Clipboard"),
            ("read_file_line", "Read File Line"),
            ("write_to_file", "Write to File"),
            ("secure_type_text", "Secure Type Text"),
            ("run_macro", "Run Sub-Macro"),
            ("capture_text", "Capture Text (OCR)"),
            ("run_command", "Run Command"),
        ],
    ),
    (
        "👻 Stealth",
        [
            ("stealth_click", "Stealth Click"),
            ("stealth_type", "Stealth Type"),
        ],
    ),
]

# Per-type descriptions shown in editor (P2 #8)
_ACTION_DESCRIPTIONS: dict[str, str] = {
    "mouse_click": "Click chuột trái tại tọa độ (X, Y) hoặc vị trí ảnh mẫu",
    "mouse_double_click": "Double-click chuột trái tại tọa độ hoặc ảnh mẫu",
    "mouse_right_click": "Click chuột phải tại tọa độ hoặc ảnh mẫu",
    "mouse_move": "Di chuyển chuột đến vị trí chỉ định",
    "mouse_drag": "Kéo thả chuột từ vị trí hiện tại đến tọa độ đích",
    "mouse_scroll": "Cuộn chuột lên/xuống số dòng chỉ định",
    "key_press": "Nhấn một phím (đơn hoặc đặc biệt như Enter, Tab)",
    "key_combo": "Nhấn tổ hợp phím (ví dụ: Ctrl+C, Alt+F4)",
    "type_text": "Gõ chuỗi ký tự vào ô nhập liệu hiện tại",
    "hotkey": "Tương tự Key Combo — dùng cho tương thích ngược",
    "wait_for_image": "Đợi cho đến khi ảnh mẫu xuất hiện trên màn hình",
    "click_on_image": "Tìm ảnh mẫu trên màn hình và click vào vị trí tìm thấy",
    "image_exists": "Kiểm tra ảnh mẫu có tồn tại trên màn hình không",
    "take_screenshot": "Chụp màn hình và lưu thành file ảnh",
    "check_pixel_color": "Kiểm tra màu pixel tại tọa độ chỉ định",
    "wait_for_color": "Đợi cho đến khi pixel tại tọa độ có màu chỉ định",
    "delay": "Dừng chờ một khoảng thời gian (ms)",
    "loop_block": "Lặp lại nhóm action bên trong số lần chỉ định",
    "if_image_found": "Rẽ nhánh: thực hiện action tuỳ theo ảnh có tìm thấy hay không",
    "if_pixel_color": "Rẽ nhánh: thực hiện action tuỳ theo màu pixel",
    "if_variable": "Rẽ nhánh: so sánh giá trị biến và thực hiện action tương ứng",
    "set_variable": "Tạo hoặc cập nhật giá trị biến (số, chuỗi, biểu thức)",
    "split_string": "Tách chuỗi thành mảng theo dấu phân cách",
    "comment": "Nhãn/ghi chú — không thực thi, dùng để đánh dấu",
    "activate_window": "Kích hoạt cửa sổ ứng dụng theo tiêu đề",
    "log_to_file": "Ghi nội dung vào file log",
    "read_clipboard": "Đọc nội dung clipboard vào biến",
    "read_file_line": "Đọc 1 dòng từ file text vào biến",
    "write_to_file": "Ghi nội dung vào file (tạo mới hoặc nối thêm)",
    "secure_type_text": "Gõ text bảo mật (dùng cho mật khẩu)",
    "run_macro": "Chạy một macro khác như sub-routine",
    "capture_text": "Nhận dạng chữ trên màn hình (OCR) và lưu vào biến",
    "run_command": "Chạy lệnh hệ thống (CMD/PowerShell) và lưu kết quả vào biến",
    "stealth_click": "Click ẩn vào cửa sổ qua PostMessage — không chiếm chuột vật lý",
    "stealth_type": "Gõ text ẩn vào cửa sổ qua WM_CHAR — không chiếm bàn phím vật lý",
}

from gui.help_content import _ACTION_HELP  # noqa: F401


class _HelpPopup(QFrame):
    """Persistent help popup with close button and Escape key support."""

    def __init__(self, html: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("_HelpPopup { background: #1e1e2e; border: 1px solid #6c6cff; " "border-radius: 8px; }")
        self.setFixedWidth(420)
        self.setMinimumHeight(200)
        self.setMaximumHeight(450)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 8)
        layout.setSpacing(4)

        # Header row: title + close button
        header = QHBoxLayout()
        title = QLabel("📖 Hướng dẫn")
        title.setStyleSheet("font-weight: bold; font-size: 13px; color: #e0e0ff;")
        header.addWidget(title)
        header.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(24, 24)
        close_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #aaa; "
            "border: none; font-size: 16px; font-weight: bold; } "
            "QPushButton:hover { color: #ff6b6b; }"
        )
        close_btn.setToolTip("Đóng (Esc)")
        close_btn.clicked.connect(self.close)
        header.addWidget(close_btn)
        layout.addLayout(header)

        # Content browser
        browser = QTextBrowser()
        browser.setHtml(f"<div style='color:#ccc; font-size:12px; " f"line-height:1.5'>{html}</div>")
        browser.setOpenExternalLinks(False)
        browser.setStyleSheet("QTextBrowser { background: transparent; border: none; " "color: #ccc; }")
        browser.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(browser)

        # Escape key shortcut
        esc = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        esc.activated.connect(self.close)

    def keyPressEvent(self, event: Any) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)


class ActionEditorDialog(QDialog):
    """
    Modal dialog for creating or editing a single action.
    Emits action_ready(action) when user confirms.
    """

    action_ready = pyqtSignal(object)  # emits Action before dialog closes

    def __init__(self, parent: Any = None, action: Optional[Action] = None, macro_dir: str = "") -> None:
        super().__init__(parent)
        self._action = action
        self._macro_dir = macro_dir
        self._result_action: Optional[Action] = None
        self._param_widgets: dict[str, Any] = {}
        self._branch_data: dict[str, list] = {}  # Store Action objects per branch
        self._guard_type_changing = False  # Re-entrancy guard for _on_type_changed

        self.setWindowTitle("Sửa Action" if action else "Thêm Action")
        self.setMinimumSize(420, 280)
        # Dynamic max height: 85% of available screen
        from PyQt6.QtWidgets import QApplication
        screen = QApplication.primaryScreen()
        if screen:
            avail = screen.availableGeometry()
            self.setMaximumHeight(int(avail.height() * 0.85))
        self.setSizeGripEnabled(True)
        self.setModal(True)
        self._param_cache: dict[str, Any] = {}  # persist x,y across types

        self._setup_ui()

        if action:
            self._load_action(action)

    def _setup_ui(self) -> None:
        """Build the editor UI: type combo, param area, buttons."""
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        # Scrollable content area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(scroll.Shape.NoFrame)
        scroll_widget = QWidget()
        layout = QVBoxLayout(scroll_widget)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 8, 12, 4)
        scroll.setWidget(scroll_widget)
        outer_layout.addWidget(scroll)

        # Action type selector — grouped with category headers
        type_group = QGroupBox("Loại Action")
        type_layout = QVBoxLayout(type_group)

        # Search filter for action types
        self._type_search = QLineEdit()
        self._type_search.setPlaceholderText("🔍 Tìm action...")
        self._type_search.setClearButtonEnabled(True)
        self._type_search.textChanged.connect(self._filter_action_types)
        type_layout.addWidget(self._type_search)

        # Combo + Help button in same row
        combo_row = QHBoxLayout()
        self._type_combo = QComboBox()
        self._type_combo.blockSignals(True)
        self._build_grouped_combo()
        self._all_combo_items: list[tuple[str, str | None]] = []  # (label, atype)
        # Skip to first non-header item before connecting signals
        for i in range(self._type_combo.count()):
            if self._type_combo.itemData(i, Qt.ItemDataRole.UserRole) is not None:
                self._type_combo.setCurrentIndex(i)
                break
        self._type_combo.blockSignals(False)
        self._type_combo.currentIndexChanged.connect(self._on_type_changed)
        combo_row.addWidget(self._type_combo, stretch=1)

        self._help_btn = QPushButton("❓")
        self._help_btn.setFixedSize(28, 28)
        self._help_btn.setToolTip("Xem hướng dẫn & ví dụ")
        self._help_btn.setAccessibleName("Hướng dẫn action")
        self._help_btn.clicked.connect(self._show_action_help)
        combo_row.addWidget(self._help_btn)
        type_layout.addLayout(combo_row)

        # Action type description (P2 #8)
        self._type_desc_label = QLabel("")
        self._type_desc_label.setObjectName("subtitleLabel")
        self._type_desc_label.setWordWrap(True)
        type_layout.addWidget(self._type_desc_label)
        layout.addWidget(type_group)

        # Parameters area (dynamic)
        self._params_group = QGroupBox("Tham số")
        self._params_layout = QFormLayout(self._params_group)
        layout.addWidget(self._params_group)

        # Common settings — collapsible "Advanced" section
        self._advanced_toggle = QPushButton("▶ Nâng cao (5 tuỳ chọn)")
        self._advanced_toggle.setCheckable(True)
        self._advanced_toggle.setChecked(False)
        self._advanced_toggle.setStyleSheet(
            "QPushButton { text-align: left; padding: 6px 12px; "
            "font-weight: 600; color: #ababc0; border: 1px solid #3a3c60; "
            "border-radius: 6px; background: #232442; }"
            "QPushButton:checked { color: #6c63ff; }"
        )
        self._advanced_toggle.clicked.connect(self._toggle_advanced)
        layout.addWidget(self._advanced_toggle)

        self._advanced_widget = QWidget()
        self._advanced_widget.setVisible(False)
        common_layout = QFormLayout(self._advanced_widget)
        common_layout.setContentsMargins(8, 4, 8, 4)

        self._delay_spin = QSpinBox()
        self._delay_spin.setRange(0, 60000)
        self._delay_spin.setSuffix(" ms")
        self._delay_spin.setValue(0)
        common_layout.addRow("Trễ sau:", self._delay_spin)

        self._repeat_spin = QSpinBox()
        self._repeat_spin.setRange(1, 10000)
        self._repeat_spin.setValue(1)
        common_layout.addRow("Lặp lại:", self._repeat_spin)

        self._desc_edit = QLineEdit()
        self._desc_edit.setPlaceholderText("Mô tả tuỳ chọn...")
        common_layout.addRow("Mô tả:", self._desc_edit)

        self._enabled_check = QCheckBox("Bật")
        self._enabled_check.setChecked(True)
        common_layout.addRow("", self._enabled_check)

        self._error_combo = QComboBox()
        _err_items = [
            ("Dừng", "stop"),
            ("Bỏ qua", "skip"),
            ("Thử lại: 1", "retry:1"),
            ("Thử lại: 3", "retry:3"),
            ("Thử lại: 5", "retry:5"),
        ]
        for vi_label, en_val in _err_items:
            self._error_combo.addItem(vi_label, en_val)
        self._error_combo.setToolTip(
            "Chế độ xử lý khi action thất bại:\n\n"
            "• Dừng (stop): Đánh dấu lỗi — macro dừng nếu bật\n"
            "  'Dừng khi lỗi' trong cài đặt chạy, hoặc tiếp tục nếu tắt.\n"
            "• Bỏ qua (skip): Coi như thành công, tiếp tục action tiếp.\n"
            "• Thử lại 1-5x: Thử lại N lần (nghỉ 1s giữa mỗi lần),\n"
            "  nếu vẫn lỗi thì xử lý theo chế độ mặc định."
        )
        common_layout.addRow("Khi lỗi:", self._error_combo)

        layout.addWidget(self._advanced_widget)

        # OK / Cancel — always visible at bottom (outside scroll area)
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(12, 6, 12, 8)
        btn_layout.addStretch()
        cancel_btn = QPushButton("Hủy")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        ok_btn = QPushButton("Đồng ý")
        ok_btn.setObjectName("primaryButton")
        ok_btn.clicked.connect(self._on_ok)
        btn_layout.addWidget(ok_btn)
        outer_layout.addLayout(btn_layout)

        # Initialize params for the pre-selected type
        self._on_type_changed()
        self._type_combo.setFocus()

        # Static tab order for bottom section

        QWidget.setTabOrder(self._advanced_toggle, self._delay_spin)
        QWidget.setTabOrder(self._delay_spin, self._repeat_spin)
        QWidget.setTabOrder(self._repeat_spin, self._desc_edit)
        QWidget.setTabOrder(self._desc_edit, self._enabled_check)
        QWidget.setTabOrder(self._enabled_check, self._error_combo)
        QWidget.setTabOrder(self._error_combo, cancel_btn)
        QWidget.setTabOrder(cancel_btn, ok_btn)
        
        self._cancel_btn = cancel_btn
        self._ok_btn = ok_btn

    def _build_grouped_combo(self) -> None:
        """Build grouped combo box with category headers."""
        from PyQt6.QtCore import QSettings
        from PyQt6.QtGui import QFont, QStandardItem, QStandardItemModel

        model = QStandardItemModel()

        # Recent Actions section
        recent = QSettings("AutoMacro", "ActionEditor").value("recent_actions", [])
        if recent and isinstance(recent, list):
            header = QStandardItem("⏱ Gần đây")
            header_font = QFont()
            header_font.setBold(True)
            header.setFont(header_font)
            header.setEnabled(False)
            header.setSelectable(False)
            model.appendRow(header)
            # Find display names for recent types
            _type_labels = {}
            for _, actions in ACTION_CATEGORIES:
                for atype, label in actions:
                    _type_labels[atype] = label
            for atype in recent[:5]:
                label = _type_labels.get(atype, atype)
                item = QStandardItem(f"    {label}")
                item.setData(atype, Qt.ItemDataRole.UserRole)
                model.appendRow(item)

        for cat_label, actions in ACTION_CATEGORIES:
            # Category header (non-selectable, bold)
            header = QStandardItem(cat_label)
            header_font = QFont()
            header_font.setBold(True)
            header.setFont(header_font)
            header.setEnabled(False)  # non-selectable
            header.setSelectable(False)
            model.appendRow(header)
            # Action items (indented with spaces)
            for atype, label in actions:
                item = QStandardItem(f"    {label}")
                item.setData(atype, Qt.ItemDataRole.UserRole)
                model.appendRow(item)
        self._type_combo.setModel(model)

    def _filter_action_types(self, text: str) -> None:
        """Filter action type combo items based on search text."""
        text = text.strip().lower()
        # Rebuild combo with filtered items
        self._type_combo.blockSignals(True)
        current_type = self._type_combo.currentData(Qt.ItemDataRole.UserRole)

        from PyQt6.QtGui import QFont, QStandardItem, QStandardItemModel

        model = QStandardItemModel()
        first_selectable = -1
        idx = 0
        for cat_label, actions in ACTION_CATEGORIES:
            # Filter actions in this category
            filtered = [(atype, label) for atype, label in actions
                        if not text or text in label.lower() or text in atype.lower()]
            if not filtered:
                continue
            # Category header
            header = QStandardItem(cat_label)
            header_font = QFont()
            header_font.setBold(True)
            header.setFont(header_font)
            header.setEnabled(False)
            header.setSelectable(False)
            model.appendRow(header)
            idx += 1
            for atype, label in filtered:
                item = QStandardItem(f"    {label}")
                item.setData(atype, Qt.ItemDataRole.UserRole)
                model.appendRow(item)
                if first_selectable < 0:
                    first_selectable = idx
                if atype == current_type:
                    first_selectable = idx  # prefer current selection
                idx += 1

        self._type_combo.setModel(model)
        if first_selectable >= 0:
            self._type_combo.setCurrentIndex(first_selectable)
        self._type_combo.blockSignals(False)
        self._on_type_changed()

    def _toggle_advanced(self, checked: bool) -> None:
        """Show/hide advanced settings section."""
        self._advanced_widget.setVisible(checked)
        icon = "▼" if checked else "▶"
        self._advanced_toggle.setText(f"{icon} Nâng cao (5 tuỳ chọn)")

    def _clear_params(self) -> None:
        """Remove all dynamic parameter widgets, cache reusable values."""
        # Cache x,y before clearing
        for key in ("x", "y"):
            w = self._param_widgets.get(key)
            if w and isinstance(w, QSpinBox):
                self._param_cache[key] = w.value()
        while self._params_layout.count():
            item = self._params_layout.takeAt(0)
            if item is None:
                break
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self._param_widgets.clear()
        self._branch_data.clear()

    def _on_type_changed(self) -> None:
        """Rebuild parameter widgets when action type changes."""
        if self._guard_type_changing:
            return  # Prevent re-entrant calls (Qt signal double-fire)
        self._guard_type_changing = True
        try:
            self._clear_params()
            atype = self._type_combo.currentData(Qt.ItemDataRole.UserRole)
            if not atype:
                self._type_desc_label.setText("")
                return

            # Update description (P2 #8)
            self._type_desc_label.setText(f"ℹ️ {_ACTION_DESCRIPTIONS.get(atype, '')}")

            # Dispatch to per-category builder
            builders: dict[str, Callable[[], None]] = {
                "mouse_click": lambda: self._build_mouse_params(atype),
                "mouse_double_click": lambda: self._build_mouse_params(atype),
                "mouse_right_click": lambda: self._build_mouse_params(atype),
                "mouse_move": lambda: self._build_mouse_params(atype),
                "mouse_drag": self._build_drag_params,
                "mouse_scroll": self._build_scroll_params,
                "key_press": self._build_key_press_params,
                "key_combo": self._build_key_combo_params,
                "hotkey": self._build_key_combo_params,
                "type_text": self._build_type_text_params,
                "delay": self._build_delay_params,
                "wait_for_image": lambda: self._build_image_params(atype),
                "click_on_image": lambda: self._build_image_params(atype),
                "image_exists": lambda: self._build_image_params(atype),
                "check_pixel_color": lambda: self._build_pixel_params(atype),
                "wait_for_color": lambda: self._build_pixel_params(atype),
                "take_screenshot": self._build_screenshot_params,
                "if_pixel_color": self._build_if_pixel_color_params,
                "if_image_found": self._build_if_image_found_params,
                "loop_block": self._build_loop_block_params,
                "if_variable": self._build_if_variable_params,
                "set_variable": self._build_set_variable_params,
                "split_string": self._build_split_string_params,
                "comment": self._build_comment_params,
                "activate_window": self._build_activate_window_params,
                "log_to_file": self._build_log_params,
                "read_clipboard": self._build_read_clipboard_params,
                "read_file_line": self._build_read_file_line_params,
                "write_to_file": self._build_write_file_params,
                "secure_type_text": self._build_secure_text_params,
                "run_macro": self._build_run_macro_params,
                "capture_text": self._build_capture_text_params,
                "run_command": self._build_run_command_params,
                "stealth_click": self._build_stealth_click_params,
                "stealth_type": self._build_stealth_type_params,
            }
            builder = builders.get(atype)
            if builder:
                builder()
            elif atype:
                import logging
                logging.getLogger(__name__).warning("No param builder registered for action type '%s'", atype)

            # Restore cached x,y values if new type also has them
            for key in ("x", "y"):
                if key in self._param_cache and key in self._param_widgets:
                    w = self._param_widgets[key]
                    if isinstance(w, QSpinBox):
                        w.setValue(self._param_cache[key])

            # Resize dialog to fit new content
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(0, self.adjustSize)
        finally:
            self._guard_type_changing = False

    def _show_action_help(self) -> None:
        """Show persistent help popup for the selected action type."""
        atype = self._type_combo.currentData(Qt.ItemDataRole.UserRole)
        if not atype:
            return
        html = _ACTION_HELP.get(atype)
        if not html:
            display_name = self._type_combo.currentText()
            desc = _ACTION_DESCRIPTIONS.get(atype, "")
            html = (
                f"<b>{display_name}</b><br><br>" f"{desc}<br><br>" "<i>Chưa có hướng dẫn chi tiết cho action này.</i>"
            )
        # Close previous popup if open
        if hasattr(self, "_help_popup") and self._help_popup is not None:  # type: ignore[has-type]
            self._help_popup.close()  # type: ignore[has-type]
        self._help_popup = _HelpPopup(html, parent=self)
        # Position to the right of the help button
        btn_pos = self._help_btn.mapToGlobal(self._help_btn.rect().topRight())
        self._help_popup.move(btn_pos.x() + 6, btn_pos.y())
        self._help_popup.show()
        self._help_popup.setFocus()

    def _build_mouse_params(self, atype: str) -> None:
        """Create widgets for mouse action parameters."""
        self._add_xy_params()
        if atype in ("mouse_click", "mouse_move"):
            self._add_duration_param()
        # context_image: read-only display (set by recorder, not edited manually)
        if atype in ("mouse_click", "mouse_double_click", "mouse_right_click"):
            ctx_img = QLineEdit()
            ctx_img.setPlaceholderText("(thiết lập bởi Recorder)")
            ctx_img.setReadOnly(True)
            ctx_img.setStyleSheet("color: #888;")
            self._params_layout.addRow("Ảnh ngữ cảnh 📷:", ctx_img)
            self._param_widgets["context_image"] = ctx_img

    def _build_drag_params(self) -> None:
        """Create widgets for mouse drag parameters."""
        self._add_xy_params()
        self._add_duration_param()
        self._add_button_param()

    def _build_scroll_params(self) -> None:
        """Create widgets for scroll action parameters."""
        self._add_xy_params()
        clicks = QSpinBox()
        clicks.setRange(-100, 100)
        clicks.setValue(3)
        self._params_layout.addRow("Cuộn (+ lên, - xuống):", clicks)
        self._param_widgets["clicks"] = clicks

    def _build_key_press_params(self) -> None:
        """Create widgets for single key press — dropdown with all keys."""
        from modules.keyboard import SPECIAL_KEYS
        key_combo = QComboBox()
        key_combo.setEditable(True)  # Allow custom key names
        key_combo.addItems(SPECIAL_KEYS)
        key_combo.setCurrentText("enter")
        self._params_layout.addRow("Phím:", key_combo)
        self._param_widgets["key"] = key_combo

    def _build_key_combo_params(self) -> None:
        """Create tag-chip UI for key combination."""
        from PyQt6.QtWidgets import QHBoxLayout, QWidget

        from modules.keyboard import SPECIAL_KEYS

        # Container for tag chips
        self._combo_keys: list[str] = []
        chip_container = QWidget()
        self._chip_layout = QHBoxLayout(chip_container)
        self._chip_layout.setContentsMargins(0, 0, 0, 0)
        self._chip_layout.setSpacing(4)
        self._chip_layout.addStretch()
        self._params_layout.addRow("Tổ hợp phím:", chip_container)

        # Key selector dropdown + Add button
        add_row = QHBoxLayout()
        key_selector = QComboBox()
        key_selector.setEditable(True)
        key_selector.addItems(["ctrl", "shift", "alt", "win"] + SPECIAL_KEYS)
        add_btn = QPushButton("➕")
        add_btn.setFixedSize(28, 28)
        add_btn.setToolTip("Thêm phím vào tổ hợp")
        add_btn.clicked.connect(lambda: self._add_combo_key(key_selector.currentText()))
        add_row.addWidget(key_selector, stretch=1)
        add_row.addWidget(add_btn)
        add_wrapper = QWidget()
        add_wrapper.setLayout(add_row)
        self._params_layout.addRow("Thêm phím:", add_wrapper)

        # Store as hidden QLineEdit for _collect_params compatibility
        hidden = QLineEdit()
        hidden.setVisible(False)
        self._params_layout.addRow(hidden)  # Add to layout so it's managed
        self._param_widgets["keys_str"] = hidden

    def _add_combo_key(self, key: str) -> None:
        """Add a tag chip for a key in the combo."""
        key = key.strip().lower()
        if not key or key in getattr(self, "_combo_keys", []):
            return
        self._combo_keys.append(key)
        self._rebuild_key_chips()

    def _remove_combo_key(self, key: str) -> None:
        """Remove a tag chip."""
        if key in getattr(self, "_combo_keys", []):
            self._combo_keys.remove(key)
            self._rebuild_key_chips()

    def _rebuild_key_chips(self) -> None:
        """Rebuild tag chip buttons from _combo_keys list."""
        if not hasattr(self, "_chip_layout"):
            return
        # Clear existing chips (keep stretch at end)
        while self._chip_layout.count() > 1:
            item = self._chip_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()
        # Add chips before stretch
        for i, key in enumerate(self._combo_keys):
            chip = QPushButton(f"{key} ×")
            chip.setFixedHeight(24)
            chip.setStyleSheet(
                "border-radius: 10px; padding: 2px 8px; "
                "background: #3a6; color: #fff; font-weight: bold;"
            )
            chip.setToolTip(f"Click để xoá phím '{key}'")
            chip.clicked.connect(lambda _, k=key: self._remove_combo_key(k))
            self._chip_layout.insertWidget(i, chip)
        # Update hidden keys_str widget
        hidden = self._param_widgets.get("keys_str")
        if hidden:
            hidden.setText("+".join(self._combo_keys))

    def _build_type_text_params(self) -> None:
        """Create widgets for text typing action — multiline support."""
        from PyQt6.QtWidgets import QTextEdit as _QTextEdit
        text_edit = _QTextEdit()
        text_edit.setPlaceholderText("Nội dung cần gõ (hỗ trợ nhiều dòng, ${var})...")
        text_edit.setMaximumHeight(80)
        self._params_layout.addRow("Nội dung:", text_edit)
        self._param_widgets["text"] = text_edit
        interval = QDoubleSpinBox()
        interval.setRange(0.0, 1.0)
        interval.setSingleStep(0.01)
        interval.setValue(0.02)
        interval.setSuffix(" s")
        self._params_layout.addRow("Khoảng cách:", interval)
        self._param_widgets["interval"] = interval

    def _build_delay_params(self) -> None:
        """Create widgets for delay duration."""
        dur = QSpinBox()
        dur.setRange(0, 300000)
        dur.setSuffix(" ms")
        dur.setValue(1000)
        self._params_layout.addRow("Thời gian:", dur)
        self._param_widgets["duration_ms"] = dur

    def _build_image_params(self, atype: str) -> None:
        """Create widgets for image-based action parameters."""
        self._add_image_params()
        if atype in ("wait_for_image", "click_on_image"):
            timeout = QSpinBox()
            timeout.setRange(0, 120000)
            timeout.setSuffix(" ms")
            timeout.setValue(10000)
            self._params_layout.addRow("Giới hạn:", timeout)
            self._param_widgets["timeout_ms"] = timeout
        if atype == "click_on_image":
            self._add_button_param()
        # Region search fields
        self._add_region_params()

    def _add_region_params(self) -> None:
        """Add optional search region fields (shared by all image actions).

        When all values are 0: search full screen (default).
        When w/h > 0: constrain search to the specified rectangle.
        """
        from PyQt6.QtWidgets import QGroupBox

        region_group = QGroupBox("🔲 Vùng tìm kiếm (tuỳ chọn)")
        region_group.setCheckable(True)
        region_group.setChecked(False)  # Default: full screen
        region_group.setToolTip(
            "Bật để giới hạn vùng tìm kiếm hình ảnh.\n"
            "Tắt = tìm toàn màn hình (mặc định).\n"
            "Bật = chỉ tìm trong vùng (x, y, w, h) → nhanh hơn \u0026 chính xác hơn."
        )
        region_layout = QFormLayout(region_group)
        region_layout.setContentsMargins(8, 4, 8, 4)

        for label, key, tooltip in [
            ("X:", "region_x", "Toạ độ X góc trái trên của vùng"),
            ("Y:", "region_y", "Toạ độ Y góc trái trên của vùng"),
            ("Rộng (W):", "region_w", "Chiều rộng vùng tìm kiếm (pixel)"),
            ("Cao (H):", "region_h", "Chiều cao vùng tìm kiếm (pixel)"),
        ]:
            spin = QSpinBox()
            spin.setRange(0, 9999)
            spin.setValue(0)
            spin.setToolTip(tooltip)
            region_layout.addRow(label, spin)
            self._param_widgets[key] = spin

        # Region picker button
        pick_btn = QPushButton("🖱 Chọn vùng trên màn hình")
        pick_btn.setToolTip("Kéo chuột để chọn vùng tìm kiếm trực tiếp trên màn hình")
        pick_btn.clicked.connect(lambda: self._start_region_picker())
        region_layout.addRow("", pick_btn)

        self._params_layout.addRow(region_group)
        self._param_widgets["_region_group"] = region_group

        # Connect checkbox to enable/disable region fields
        def _on_region_toggled(checked: bool) -> None:
            if not checked:
                # Reset to 0 when unchecked
                for k in ("region_x", "region_y", "region_w", "region_h"):
                    w = self._param_widgets.get(k)
                    if isinstance(w, QSpinBox):
                        w.setValue(0)
        region_group.toggled.connect(_on_region_toggled)

    def _start_region_picker(self) -> None:
        """Launch snipping-tool-style overlay to drag-select a search region."""
        try:
            from gui.region_picker import RegionPickerOverlay
        except ImportError:
            return

        # Store as instance variable to prevent garbage collection
        self._region_picker = RegionPickerOverlay()

        # Get reference to main window for minimize/restore
        self._region_parent_window = self.parent()
        self._region_was_maximized = (
            self._region_parent_window.isMaximized()  # type: ignore[union-attr]
            if self._region_parent_window else False
        )

        def _restore_and_apply(x: int, y: int, w: int, h: int) -> None:
            for key, val in [("region_x", x), ("region_y", y),
                             ("region_w", w), ("region_h", h)]:
                widget = self._param_widgets.get(key)
                if isinstance(widget, QSpinBox):
                    widget.setValue(val)
            # Auto-check the region group
            grp = self._param_widgets.get("_region_group")
            if grp is not None:
                grp.setChecked(True)
            # Restore main window and dialog
            if self._region_parent_window:
                if self._region_was_maximized:
                    self._region_parent_window.showMaximized()  # type: ignore[attr-defined]
                else:
                    self._region_parent_window.showNormal()  # type: ignore[attr-defined]
                self._region_parent_window.activateWindow()  # type: ignore[attr-defined]
            self.show()
            self.activateWindow()

        def _restore_cancelled() -> None:
            if self._region_parent_window:
                if self._region_was_maximized:
                    self._region_parent_window.showMaximized()  # type: ignore[attr-defined]
                else:
                    self._region_parent_window.showNormal()  # type: ignore[attr-defined]
                self._region_parent_window.activateWindow()  # type: ignore[attr-defined]
            self.show()
            self.activateWindow()

        self._region_picker.region_selected.connect(_restore_and_apply)
        self._region_picker.cancelled.connect(_restore_cancelled)

        # Minimize main window + hide dialog, then show picker after delay
        self.hide()
        if self._region_parent_window:
            self._region_parent_window.showMinimized()  # type: ignore[attr-defined]
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(400, self._region_picker.start)

    def _build_screenshot_params(self) -> None:
        """Create widgets for screenshot parameters."""
        # Save directory
        dir_layout = QHBoxLayout()
        dir_edit = QLineEdit("macros/screenshots")
        dir_edit.setPlaceholderText("Thư mục lưu ảnh...")
        dir_browse = QPushButton("Duyệt")
        dir_browse.clicked.connect(lambda: self._browse_dir(dir_edit))
        dir_layout.addWidget(dir_edit)
        dir_layout.addWidget(dir_browse)
        dir_wrapper = QWidget()
        dir_wrapper.setLayout(dir_layout)
        self._params_layout.addRow("Thư mục:", dir_wrapper)
        self._param_widgets["save_dir"] = dir_edit

        # Filename pattern
        pattern_edit = QLineEdit("screenshot_%Y%m%d_%H%M%S.png")
        pattern_edit.setToolTip("%Y=năm, %m=tháng, %d=ngày, %H=giờ, %M=phút, %S=giây")
        self._params_layout.addRow("Tên file:", pattern_edit)
        self._param_widgets["filename_pattern"] = pattern_edit

        # Optional region (0 = full screen)
        for label, key, default in [
            ("Region X:", "region_x", 0),
            ("Region Y:", "region_y", 0),
            ("Region W:", "region_w", 0),
            ("Region H:", "region_h", 0),
        ]:
            spin = QSpinBox()
            spin.setRange(0, 9999)
            spin.setValue(default)
            spin.setToolTip("0 = chụp toàn màn hình")
            self._params_layout.addRow(label, spin)
            self._param_widgets[key] = spin

    def _browse_dir(self, line_edit: QLineEdit) -> None:
        """Open directory browser and fill target QLineEdit."""
        path = QFileDialog.getExistingDirectory(self, "Chọn thư mục")
        if path:
            line_edit.setText(path)

    def _build_pixel_params(self, atype: str) -> None:
        """Create widgets for pixel color check parameters."""
        self._add_xy_params()
        for color_name, default_val in [("r", 255), ("g", 0), ("b", 0)]:
            spin = QSpinBox()
            spin.setRange(0, 255)
            spin.setValue(default_val)
            self._params_layout.addRow(f"Màu {color_name.upper()}:", spin)
            self._param_widgets[color_name] = spin
        tol = QSpinBox()
        tol.setRange(0, 255)
        tol.setValue(10)
        self._params_layout.addRow("Sai số:", tol)
        self._param_widgets["tolerance"] = tol

        # R5: Color Preview square
        self._color_preview = QLabel()
        self._color_preview.setFixedSize(32, 32)
        self._color_preview.setStyleSheet("border: 1px solid #666; border-radius: 4px;")
        self._params_layout.addRow("Màu đã chọn:", self._color_preview)
        for c in ("r", "g", "b"):
            self._param_widgets[c].valueChanged.connect(self._update_color_preview)
        self._update_color_preview()

        # Color Picker — click screen to auto-fill R,G,B
        pick_color_btn = QPushButton("🎨 Chọn màu trên màn hình")
        pick_color_btn.setObjectName("primaryButton")
        pick_color_btn.setToolTip("Click bất kỳ trên màn hình → tự điền X, Y, R, G, B")
        pick_color_btn.clicked.connect(self._pick_pixel_color)
        self._params_layout.addRow("", pick_color_btn)
        if atype in ("wait_for_color", "if_pixel_color"):
            timeout = QSpinBox()
            timeout.setRange(0, 120000)
            timeout.setSuffix(" ms")
            timeout.setValue(10000)
            self._params_layout.addRow("Giới hạn:", timeout)
            self._param_widgets["timeout_ms"] = timeout

    def _build_branch_editor(self, label: str, branch_key: str) -> None:
        """Create inline branch editor with mini action list + Add/Remove."""
        from PyQt6.QtWidgets import QListWidget

        group = QGroupBox(label)
        group_layout = QVBoxLayout(group)
        group_layout.setContentsMargins(6, 8, 6, 4)
        group_layout.setSpacing(4)

        action_list = QListWidget()
        action_list.setMaximumHeight(80)
        action_list.setStyleSheet("QListWidget { font-size: 11px; }")
        action_list.setToolTip("Danh sách actions trong nhánh này")
        group_layout.addWidget(action_list)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("➕ Thêm")
        add_btn.setFixedHeight(24)
        add_btn.clicked.connect(lambda: self._add_branch_action(branch_key, action_list))
        remove_btn = QPushButton("➖ Xoá")
        remove_btn.setFixedHeight(24)
        remove_btn.clicked.connect(lambda: self._remove_branch_action(branch_key, action_list))
        btn_row.addWidget(add_btn)
        btn_row.addWidget(remove_btn)
        btn_row.addStretch()
        group_layout.addLayout(btn_row)

        self._params_layout.addRow(group)
        # Store list widget for later reference
        self._param_widgets[f"_branch_list_{branch_key}"] = action_list
        # Initialize branch data
        if branch_key not in self._branch_data:
            self._branch_data[branch_key] = []

    def _add_branch_action(self, branch_key: str, list_widget: Any) -> None:
        """Open nested editor to add an action to a branch."""
        dialog = ActionEditorDialog(parent=self, macro_dir=self._macro_dir)
        dialog.setWindowTitle("Thêm Action vào nhánh")
        if dialog.exec():
            action = dialog.get_action()
            if action:
                self._branch_data.setdefault(branch_key, []).append(action)
                list_widget.addItem(f"{action.ACTION_TYPE}: {action.get_display_name()}")

    def _remove_branch_action(self, branch_key: str, list_widget: Any) -> None:
        """Remove selected action from branch."""
        row = list_widget.currentRow()
        if row >= 0 and branch_key in self._branch_data:
            if row < len(self._branch_data[branch_key]):
                self._branch_data[branch_key].pop(row)
                list_widget.takeItem(row)

    def _build_if_pixel_color_params(self) -> None:
        """Builder for IfPixelColor — pixel check with timeout and ELSE."""
        self._build_pixel_params("if_pixel_color")
        self._build_branch_editor("✅ Khi khớp (THEN)", "then_actions")
        self._build_branch_editor("❌ Khi không khớp (ELSE)", "else_actions")

    def _add_xy_params(self) -> None:
        """Add standard X/Y coordinate fields with coordinate picker."""
        x_spin = QSpinBox()
        x_spin.setRange(0, 9999)
        self._params_layout.addRow("X:", x_spin)
        self._param_widgets["x"] = x_spin

        y_spin = QSpinBox()
        y_spin.setRange(0, 9999)
        self._params_layout.addRow("Y:", y_spin)
        self._param_widgets["y"] = y_spin

        # Coordinate Picker button
        pick_btn = QPushButton("📌 Chọn trên màn hình")
        pick_btn.setObjectName("primaryButton")
        pick_btn.setToolTip(
            "Nhấn để chọn toạ độ trên màn hình.\n" "Click bất kỳ → toạ độ tự điền.\n" "Nhấn Escape để hủy."
        )
        pick_btn.clicked.connect(lambda: self._start_coordinate_picker(x_spin, y_spin))
        self._params_layout.addRow("", pick_btn)

    def _build_if_image_found_params(self) -> None:
        """Builder for IfImageFound — image path, confidence, timeout, region, ELSE."""
        self._add_image_params()

        timeout = QSpinBox()
        timeout.setRange(0, 120000)
        timeout.setSuffix(" ms")
        timeout.setValue(5000)
        self._params_layout.addRow("Giới hạn:", timeout)
        self._param_widgets["timeout_ms"] = timeout

        # Region search fields
        self._add_region_params()

        # 3.1: Inline branch editors
        self._build_branch_editor("✅ Khi tìm thấy (THEN)", "then_actions")
        self._build_branch_editor("❌ Khi không thấy (ELSE)", "else_actions")

    def _build_loop_block_params(self) -> None:
        """Builder for LoopBlock — iterations count."""
        iterations = QSpinBox()
        iterations.setRange(0, 999999)
        iterations.setValue(1)
        iterations.setSpecialValueText("∞ Vô hạn")
        iterations.setToolTip("0 = lặp vô hạn (cho đến khi dừng)")
        self._params_layout.addRow("Số lần lặp:", iterations)
        self._param_widgets["iterations"] = iterations
        # R4: Sub-actions editor (same pattern as If* branches)
        self._build_branch_editor("🔁 Actions trong vòng lặp", "sub_actions")

    def _build_if_variable_params(self) -> None:
        """Create widgets for variable conditional."""
        var_name = QLineEdit()
        var_name.setPlaceholderText("VD: counter, row")
        self._params_layout.addRow("Biến:", var_name)
        self._param_widgets["var_name"] = var_name

        operator = QComboBox()
        operator.addItems(["==", "!=", ">", "<", ">=", "<="])
        self._params_layout.addRow("Toán tử:", operator)
        self._param_widgets["operator"] = operator

        compare_value = QLineEdit()
        compare_value.setPlaceholderText("VD: 10, hello")
        self._params_layout.addRow("Giá trị so sánh:", compare_value)
        self._param_widgets["compare_value"] = compare_value

        # Inline branch editors
        self._build_branch_editor("✅ Khi đúng (THEN)", "then_actions")
        self._build_branch_editor("❌ Khi sai (ELSE)", "else_actions")

    def _build_set_variable_params(self) -> None:
        """Create widgets for set-variable action."""
        var_name = QLineEdit()
        var_name.setPlaceholderText("VD: counter, row")
        self._params_layout.addRow("Biến:", var_name)
        self._param_widgets["var_name"] = var_name

        value = QLineEdit()
        value.setPlaceholderText("VD: 0, 1, hello")
        self._params_layout.addRow("Giá trị:", value)
        self._param_widgets["value"] = value

        operation = QComboBox()
        _ops = [
            ("Gán giá trị", "set"),
            ("Tăng +N", "increment"),
            ("Giảm -N", "decrement"),
            ("Cộng", "add"),
            ("Trừ", "subtract"),
            ("Nhân", "multiply"),
            ("Chia", "divide"),
            ("Chia dư (%)", "modulo"),
            ("Nối chuỗi", "concat"),
            ("Tính biểu thức", "eval"),
        ]
        for label, val in _ops:
            operation.addItem(label, val)
        self._params_layout.addRow("Phép toán:", operation)
        self._param_widgets["operation"] = operation

    def _build_split_string_params(self) -> None:
        """Create widgets for string split action."""
        src = QLineEdit()
        src.setPlaceholderText("Tên biến nguồn")
        self._params_layout.addRow("Biến nguồn:", src)
        self._param_widgets["source_var"] = src

        delim = QLineEdit()
        delim.setText(",")
        self._params_layout.addRow("Dấu phân cách:", delim)
        self._param_widgets["delimiter"] = delim

        idx = QSpinBox()
        idx.setRange(0, 100)
        self._params_layout.addRow("Vị trí:", idx)
        self._param_widgets["field_index"] = idx

        target = QLineEdit()
        target.setPlaceholderText("Tên biến lưu kết quả")
        self._params_layout.addRow("Lưu vào:", target)
        self._param_widgets["target_var"] = target

    def _build_comment_params(self) -> None:
        """Create widgets for comment label text."""
        text = QLineEdit()
        text.setPlaceholderText("Nhãn mục, VD: 'Giai đoạn đăng nhập'")
        self._params_layout.addRow("Ghi chú:", text)
        self._param_widgets["text"] = text

    def _build_activate_window_params(self) -> None:
        title = QLineEdit()
        title.setPlaceholderText("Tiêu đề cửa sổ (tìm gần đúng)")
        self._params_layout.addRow("Tiêu đề:", title)
        self._param_widgets["window_title"] = title

        exact = QCheckBox("Khớp chính xác")
        self._params_layout.addRow("", exact)
        self._param_widgets["exact_match"] = exact

    def _build_log_params(self) -> None:
        """Create widgets for log-to-file action."""
        msg = QLineEdit()
        msg.setPlaceholderText("Nội dung (hỗ trợ ${var})")
        self._params_layout.addRow("Nội dung:", msg)
        self._param_widgets["message"] = msg

        path = QLineEdit()
        path.setPlaceholderText("macros/macro_log.txt")
        self._params_layout.addRow("File log:", path)
        self._param_widgets["file_path"] = path

    def _build_read_clipboard_params(self) -> None:
        var_name = QLineEdit()
        var_name.setPlaceholderText("Tên biến lưu clipboard")
        var_name.setText("clipboard")
        self._params_layout.addRow("Lưu vào:", var_name)
        self._param_widgets["var_name"] = var_name

    def _build_read_file_line_params(self) -> None:
        path = QLineEdit()
        path.setPlaceholderText("Đường dẫn file")
        self._params_layout.addRow("Đường dẫn:", path)
        self._param_widgets["file_path"] = path

        line = QLineEdit()
        line.setPlaceholderText("Số dòng (hoặc ${var})")
        line.setText("1")
        self._params_layout.addRow("Dòng:", line)
        self._param_widgets["line_number"] = line

        var_name = QLineEdit()
        var_name.setText("line")
        self._params_layout.addRow("Store in:", var_name)
        self._param_widgets["var_name"] = var_name

    def _build_write_file_params(self) -> None:
        """Create widgets for write-to-file action."""
        path = QLineEdit()
        path.setPlaceholderText("Đường dẫn file xuất")
        self._params_layout.addRow("Đường dẫn:", path)
        self._param_widgets["file_path"] = path

        text = QLineEdit()
        text.setPlaceholderText("Nội dung ghi (hỗ trợ ${var})")
        self._params_layout.addRow("Nội dung:", text)
        self._param_widgets["text"] = text

        mode = QComboBox()
        mode.addItems(["append", "overwrite"])
        self._params_layout.addRow("Chế độ:", mode)
        self._param_widgets["mode"] = mode

    def _build_secure_text_params(self) -> None:
        text_edit = QLineEdit()
        text_edit.setPlaceholderText("Nhập nội dung nhạy cảm (sẽ được mã hóa)")
        text_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._params_layout.addRow("Nội dung:", text_edit)
        self._param_widgets["encrypted_text"] = text_edit

        encrypt_btn = QPushButton("🔒 Mã hóa ngay")
        encrypt_btn.setToolTip("Mã hóa nội dung bằng Windows DPAPI")

        def _do_encrypt():
            from core.secure import encrypt

            raw = text_edit.text()
            if raw and not raw.startswith("DPAPI:"):
                text_edit.setText(encrypt(raw))

        encrypt_btn.clicked.connect(_do_encrypt)
        self._params_layout.addRow("", encrypt_btn)

    def _build_run_macro_params(self) -> None:
        """Create widgets for run-macro sub-routine."""
        path = QLineEdit()
        path.setPlaceholderText("Đường dẫn file macro .json")
        self._params_layout.addRow("File macro:", path)
        self._param_widgets["macro_path"] = path

        browse_btn = QPushButton("📂 Duyệt...")

        def _browse():
            from PyQt6.QtWidgets import QFileDialog

            fpath, _ = QFileDialog.getOpenFileName(self, "Chọn macro", "macros", "JSON Macros (*.json)")
            if fpath:
                path.setText(fpath)

        browse_btn.clicked.connect(_browse)
        self._params_layout.addRow("", browse_btn)

    def _build_capture_text_params(self) -> None:
        """Create widgets for OCR capture-text action."""
        self._add_xy_params()

        w_spin = QSpinBox()
        w_spin.setRange(10, 9999)
        w_spin.setValue(200)
        self._params_layout.addRow("Chiều rộng:", w_spin)
        self._param_widgets["width"] = w_spin

        h_spin = QSpinBox()
        h_spin.setRange(10, 9999)
        h_spin.setValue(50)
        self._params_layout.addRow("Chiều cao:", h_spin)
        self._param_widgets["height"] = h_spin

        var_name = QLineEdit()
        var_name.setText("ocr_text")
        self._params_layout.addRow("Store in:", var_name)
        self._param_widgets["var_name"] = var_name

        lang = QLineEdit()
        lang.setText("eng")
        lang.setPlaceholderText("Ngôn ngữ (eng, vie, ...)")
        self._params_layout.addRow("Ngôn ngữ:", lang)
        self._param_widgets["lang"] = lang

    def _build_run_command_params(self) -> None:
        """Create widgets for run_command action."""
        cmd = QLineEdit()
        cmd.setPlaceholderText("Lệnh (ví dụ: echo hello, dir C:\\Users)")
        self._params_layout.addRow("Lệnh:", cmd)
        self._param_widgets["command"] = cmd

        timeout = QSpinBox()
        timeout.setRange(1, 300)
        timeout.setValue(30)
        timeout.setSuffix(" giây")
        self._params_layout.addRow("Timeout:", timeout)
        self._param_widgets["timeout"] = timeout

        var_name = QLineEdit()
        var_name.setPlaceholderText("Tên biến lưu stdout (bỏ trống = không lưu)")
        self._params_layout.addRow("Lưu output:", var_name)
        self._param_widgets["var_name"] = var_name

        cwd = QLineEdit()
        cwd.setPlaceholderText("Thư mục làm việc (bỏ trống = mặc định)")
        self._params_layout.addRow("Thư mục:", cwd)
        self._param_widgets["working_dir"] = cwd

    # ── Stealth action builders ──────────────────────────

    def _add_window_picker(self) -> None:
        """Add a window title ComboBox with Refresh button for stealth actions."""
        win_row = QHBoxLayout()
        win_combo = QComboBox()
        win_combo.setEditable(True)
        win_combo.setPlaceholderText("Chọn hoặc nhập tên cửa sổ mục tiêu...")
        win_combo.setMinimumWidth(200)

        refresh_btn = QPushButton("↻")
        refresh_btn.setFixedSize(28, 28)
        refresh_btn.setToolTip("Làm mới danh sách cửa sổ")

        def _refresh_windows() -> None:
            current = win_combo.currentText()
            win_combo.clear()
            try:
                from core.win32_stealth import get_visible_windows
                windows = get_visible_windows()
                for _hwnd, title in windows:
                    win_combo.addItem(title)
            except Exception:
                logger.debug("Failed to enumerate windows for stealth picker")
            win_combo.setCurrentText(current)

        refresh_btn.clicked.connect(_refresh_windows)
        # Auto-populate on first build
        _refresh_windows()

        win_row.addWidget(win_combo, stretch=1)
        win_row.addWidget(refresh_btn)
        win_wrapper = QWidget()
        win_wrapper.setLayout(win_row)
        self._params_layout.addRow("Cửa sổ:", win_wrapper)
        self._param_widgets["window_title"] = win_combo

        # Info label
        info = QLabel(
            "⚠ Click ẩn: gửi trực tiếp vào cửa sổ qua PostMessage.\n"
            "  Không chiếm chuột/bàn phím vật lý.\n"
            "  Tọa độ client-relative (góc trên-trái cửa sổ)."
        )
        info.setObjectName("subtitleLabel")
        info.setWordWrap(True)
        info.setStyleSheet("color: #f9e2af; font-size: 11px; padding: 4px;")
        self._params_layout.addRow(info)

    def _build_stealth_click_params(self) -> None:
        """Create widgets for stealth click (PostMessage-based)."""
        self._add_window_picker()
        self._add_xy_params()

        right_check = QCheckBox("Click phải")
        right_check.setToolTip("Gửi WM_RBUTTONDOWN/UP thay vì WM_LBUTTONDOWN/UP")
        self._params_layout.addRow("", right_check)
        self._param_widgets["right_click"] = right_check

        double_check = QCheckBox("Double-click")
        double_check.setToolTip("Gửi WM_LBUTTONDBLCLK sequence")
        self._params_layout.addRow("", double_check)
        self._param_widgets["double_click"] = double_check

    def _build_stealth_type_params(self) -> None:
        """Create widgets for stealth type (WM_CHAR-based)."""
        self._add_window_picker()

        from PyQt6.QtWidgets import QTextEdit as _QTextEdit
        text_edit = _QTextEdit()
        text_edit.setPlaceholderText("Nội dung gõ ẩn (hỗ trợ nhiều dòng)...")
        text_edit.setMaximumHeight(80)
        self._params_layout.addRow("Nội dung:", text_edit)
        self._param_widgets["text"] = text_edit

        delay = QSpinBox()
        delay.setRange(0, 1000)
        delay.setSuffix(" ms")
        delay.setValue(0)
        delay.setToolTip("0 = gõ tức thì (bulk), >0 = delay giữa mỗi ký tự")
        self._params_layout.addRow("Delay giữa phím:", delay)
        self._param_widgets["key_delay_ms"] = delay


    def _start_coordinate_picker(self, x_spin: QSpinBox, y_spin: QSpinBox) -> None:
        """Launch coordinate picker overlay after minimizing the app."""
        self._picker = CoordinatePickerOverlay()
        self._picker_x_target = x_spin
        self._picker_y_target = y_spin
        self._picker.coordinate_picked.connect(self._on_coordinate_picked)
        self._picker.cancelled.connect(self._on_picker_cancelled)
        # Minimize main window + hide dialog so screen is clean for picking
        self._parent_window = self.parent()
        self._picker_was_maximized = (
            self._parent_window.isMaximized()  # type: ignore[union-attr]
            if self._parent_window else False
        )
        self.hide()
        if self._parent_window:
            self._parent_window.showMinimized()  # type: ignore[attr-defined]
        # Short delay so windows fully minimize before screenshot
        QTimer.singleShot(400, self._picker.start)

    def _on_coordinate_picked(self, x: int, y: int) -> None:
        """Handle picked coordinates."""
        self._picker_x_target.setValue(x)
        self._picker_y_target.setValue(y)

        # If in color-pick mode, also fill R,G,B
        if getattr(self, "_color_pick_mode", False):
            self._color_pick_mode = False
            try:
                import ctypes
                hdc = ctypes.windll.user32.GetDC(0)
                color = ctypes.windll.gdi32.GetPixel(hdc, x, y)
                ctypes.windll.user32.ReleaseDC(0, hdc)
                r = color & 0xFF
                g = (color >> 8) & 0xFF
                b = (color >> 16) & 0xFF
                if "r" in self._param_widgets:
                    self._param_widgets["r"].setValue(r)
                if "g" in self._param_widgets:
                    self._param_widgets["g"].setValue(g)
                if "b" in self._param_widgets:
                    self._param_widgets["b"].setValue(b)
                logger.info("Color picked: (%d, %d) → RGB(%d, %d, %d)", x, y, r, g, b)
            except Exception as e:
                logger.warning("Color pick failed: %s", e)

        if self._parent_window:
            if getattr(self, '_picker_was_maximized', False):
                self._parent_window.showMaximized()  # type: ignore[attr-defined]
            else:
                self._parent_window.showNormal()  # type: ignore[attr-defined]
            self._parent_window.activateWindow()  # type: ignore[attr-defined]
        self.show()
        self.activateWindow()

    def _on_picker_cancelled(self) -> None:
        """Handle coordinate picker cancellation — restore windows."""
        if self._parent_window:
            if getattr(self, '_picker_was_maximized', False):
                self._parent_window.showMaximized()  # type: ignore[attr-defined]
            else:
                self._parent_window.showNormal()  # type: ignore[attr-defined]
            self._parent_window.activateWindow()  # type: ignore[attr-defined]
        self.show()
        self.activateWindow()

    def _update_color_preview(self) -> None:
        """Update the color preview square with current R,G,B values."""
        r = self._param_widgets.get("r")
        g = self._param_widgets.get("g")
        b = self._param_widgets.get("b")
        if r and g and b and hasattr(self, "_color_preview"):
            rv, gv, bv = r.value(), g.value(), b.value()
            self._color_preview.setStyleSheet(
                f"background-color: rgb({rv},{gv},{bv}); "
                f"border: 1px solid #666; border-radius: 4px;"
            )
            self._color_preview.setToolTip(f"RGB({rv}, {gv}, {bv}) | #{rv:02x}{gv:02x}{bv:02x}")

    def _pick_pixel_color(self) -> None:
        """Launch coordinate picker in color-pick mode — fills X,Y AND R,G,B."""
        x_spin = self._param_widgets.get("x")
        y_spin = self._param_widgets.get("y")
        if not x_spin or not y_spin:
            return
        self._color_pick_mode = True
        self._start_coordinate_picker(x_spin, y_spin)

    def _on_picker_cancelled(self) -> None:
        """Handle picker cancellation."""
        if self._parent_window:
            self._parent_window.show()  # type: ignore[attr-defined]
            self._parent_window.activateWindow()  # type: ignore[attr-defined]
        self.show()
        self.activateWindow()

    def _add_duration_param(self) -> None:
        dur = QDoubleSpinBox()
        dur.setRange(0.0, 10.0)
        dur.setSingleStep(0.1)
        dur.setValue(0.0)
        dur.setSuffix(" s")
        self._params_layout.addRow("Thời gian:", dur)
        self._param_widgets["duration"] = dur

    def _add_button_param(self) -> None:
        btn = QComboBox()
        btn.addItems(["left", "right", "middle"])
        self._params_layout.addRow("Nút chuột:", btn)
        self._param_widgets["button"] = btn

    def _add_image_params(self) -> None:
        img_layout = QHBoxLayout()
        img_edit = QLineEdit()
        img_edit.setPlaceholderText("Đường dẫn ảnh mẫu...")
        browse_btn = QPushButton("Duyệt")
        browse_btn.clicked.connect(lambda: self._browse_image(img_edit))
        capture_btn = QPushButton("📸 Chụp")
        capture_btn.setObjectName("primaryButton")
        capture_btn.setToolTip("Chụp vùng màn hình → tự động điền path\n" "Kéo vùng chọn, nhấn Escape để hủy.")
        capture_btn.clicked.connect(lambda: self._start_image_capture(img_edit))
        img_layout.addWidget(img_edit)
        img_layout.addWidget(browse_btn)
        img_layout.addWidget(capture_btn)

        wrapper = QWidget()
        wrapper.setLayout(img_layout)
        self._params_layout.addRow("Image:", wrapper)
        self._param_widgets["image_path"] = img_edit

        conf = QDoubleSpinBox()
        conf.setRange(0.1, 1.0)
        conf.setSingleStep(0.05)
        conf.setValue(0.8)
        self._params_layout.addRow("Độ chính xác:", conf)
        self._param_widgets["confidence"] = conf

        # 3.2: Live Preview
        from gui.image_preview_widget import ImagePreviewWidget

        self._image_preview = ImagePreviewWidget()
        img_edit.textChanged.connect(self._image_preview.set_template)
        conf.valueChanged.connect(self._image_preview.set_confidence)
        self._params_layout.addRow(self._image_preview)

    def _browse_image(self, line_edit: QLineEdit) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select Image", self._macro_dir, "Images (*.png *.jpg *.bmp)")
        if path:
            line_edit.setText(path)

    def _start_image_capture(self, target_edit: QLineEdit) -> None:
        """Launch capture overlay to snip a screen region as template."""
        import os

        assets_dir = os.path.join(self._macro_dir, "assets")
        self._capture_overlay = ImageCaptureOverlay(save_dir=assets_dir)
        self._capture_target_edit = target_edit
        self._capture_overlay.image_captured.connect(self._on_image_captured)
        self._capture_overlay.cancelled.connect(self._on_capture_cancelled)
        # Hide both dialog and main window
        self._capture_parent = self.parent()
        self._capture_was_maximized = (
            self._capture_parent.isMaximized()  # type: ignore[union-attr]
            if self._capture_parent else False
        )
        if self._capture_parent:
            self._capture_parent.hide()  # type: ignore[attr-defined]
        self.hide()
        QTimer.singleShot(300, self._capture_overlay.start)

    def _on_image_captured(self, path: str) -> None:
        """Handle captured image — fill path into target edit."""
        self._capture_target_edit.setText(path)
        if self._capture_parent:
            if self._capture_was_maximized:
                self._capture_parent.showMaximized()  # type: ignore[attr-defined]
            else:
                self._capture_parent.show()  # type: ignore[attr-defined]
            self._capture_parent.activateWindow()  # type: ignore[attr-defined]
        self.show()
        self.activateWindow()
        self._capture_overlay = None  # Release ref → allow GC
        logger.info("Image captured for template: %s", path)

    def _on_capture_cancelled(self) -> None:
        """Restore windows if capture was cancelled."""
        if self._capture_parent:
            if self._capture_was_maximized:
                self._capture_parent.showMaximized()  # type: ignore[attr-defined]
            else:
                self._capture_parent.show()  # type: ignore[attr-defined]
            self._capture_parent.activateWindow()  # type: ignore[attr-defined]
        self.show()
        self.activateWindow()
        self._capture_overlay = None  # Release ref → allow GC

    def _load_action(self, action: Action) -> None:
        """Pre-fill dialog from an existing action."""
        self._editing_action = action  # Store for context_image preservation
        # Block signals to prevent double _on_type_changed (first call was in _setup_ui)
        self._type_combo.blockSignals(True)
        for i in range(self._type_combo.count()):
            if self._type_combo.itemData(i, Qt.ItemDataRole.UserRole) == action.ACTION_TYPE:
                self._type_combo.setCurrentIndex(i)
                break
        self._type_combo.blockSignals(False)
        # Manually fire type change once (re-entrancy guard prevents double-fire)
        self._on_type_changed()

        # Common settings
        self._delay_spin.setValue(action.delay_after)
        self._repeat_spin.setValue(action.repeat_count)
        self._desc_edit.setText(action.description)
        self._enabled_check.setChecked(action.enabled)
        # Match by internal data value (EN), not display text
        for i in range(self._error_combo.count()):
            if self._error_combo.itemData(i) == action.on_error:
                self._error_combo.setCurrentIndex(i)
                break

        # Auto-expand advanced section if any value is non-default
        has_custom = (
            action.delay_after > 0
            or action.repeat_count > 1
            or action.description != ""
            or not action.enabled
            or action.on_error != "stop"
        )
        if has_custom:
            self._advanced_toggle.setChecked(True)
            self._advanced_widget.setVisible(True)
            self._advanced_toggle.setText("▼ Nâng cao (5 tuỳ chọn)")

        # Type-specific params
        params = action._get_params()
        from PyQt6.QtWidgets import QTextEdit as _QTextEdit
        for key, widget in self._param_widgets.items():
            if key == "keys_str" and "keys" in params:
                widget.setText("+".join(params["keys"]))
                # R3: Restore tag chips
                for k in params["keys"]:
                    self._add_combo_key(k)
            elif key in params:
                val = params[key]
                if isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                    widget.setValue(val)
                elif isinstance(widget, _QTextEdit):
                    widget.setPlainText(str(val))
                elif isinstance(widget, QLineEdit):
                    widget.setText(str(val))
                elif isinstance(widget, QComboBox):
                    # Match by data value first, then by display text
                    data = widget.findData(str(val))
                    if data >= 0:
                        widget.setCurrentIndex(data)
                    else:
                        idx = widget.findText(str(val))
                        if idx >= 0:
                            widget.setCurrentIndex(idx)
                        elif widget.isEditable():
                            widget.setCurrentText(str(val))

        # Auto-check region group if action has region values
        region_w_val = params.get("region_w", 0)
        region_group = self._param_widgets.get("_region_group")
        if region_group is not None and region_w_val and int(region_w_val) > 0:
            region_group.setChecked(True)

        # Load existing branch actions into inline editors (synchronous)
        for branch_key, attr_name in [
            ("then_actions", "_then_actions"),
            ("else_actions", "_else_actions"),
            ("sub_actions", "_sub_actions"),  # R4: Loop Block children
        ]:
            actions_list = getattr(action, attr_name, None)
            if actions_list:
                list_widget = self._param_widgets.get(f"_branch_list_{branch_key}")
                if list_widget is not None:
                    self._branch_data[branch_key] = list(actions_list)
                    for a in actions_list:
                        list_widget.addItem(f"{a.ACTION_TYPE}: {a.get_display_name()}")
                    logger.info("Loaded %d actions into %s branch", len(actions_list), branch_key)

    def _validate_params(self, atype: str, params: dict) -> str | None:
        """Return error message if params invalid, None if OK."""
        if atype in ("set_variable", "split_string") and not params.get("var_name", "").strip():
            return "Tên biến không được để trống"
        if atype in ("key_combo", "hotkey"):
            keys = params.get("keys", [])
            if not keys:
                return "Chưa nhập tổ hợp phím"
        if atype == "key_press" and not params.get("key", "").strip():
            return "Chưa chọn phím"
        if atype == "run_command" and not params.get("command", "").strip():
            return "Chưa nhập lệnh"
        if atype == "activate_window" and not params.get("window_title", "").strip():
            return "Chưa nhập tiêu đề cửa sổ"
        return None

    def _on_ok(self) -> None:
        """Build the action from widget values and accept."""
        atype = self._type_combo.currentData(Qt.ItemDataRole.UserRole)
        params = self._collect_params()

        # P0: Validate params before creating action
        warn = self._validate_params(atype, params)
        if warn:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Thiếu thông số", warn)
            return

        # Create action
        try:
            cls = get_action_class(atype)
            action = cls(**params)
            action.delay_after = self._delay_spin.value()
            action.repeat_count = self._repeat_spin.value()
            action.description = self._desc_edit.text()
            action.enabled = self._enabled_check.isChecked()
            action.on_error = self._error_combo.currentData() or "stop"

            # Preserve hidden params from original action (e.g. context_image)
            if hasattr(self, "_editing_action") and self._editing_action:
                orig = self._editing_action
                if hasattr(orig, "context_image") and orig.context_image:
                    if hasattr(action, "context_image") and not action.context_image:
                        action.context_image = orig.context_image

                # CRITICAL: Preserve composite children when editing parameters
                if orig.is_composite:
                    if hasattr(orig, "_sub_actions") and hasattr(action, "_sub_actions"):
                        # LoopBlock children
                        action._sub_actions = list(orig._sub_actions)
                    if hasattr(orig, "_then_actions") and hasattr(action, "_then_actions"):
                        # If* THEN branch
                        action._then_actions = list(orig._then_actions)
                    if hasattr(orig, "_else_actions") and hasattr(action, "_else_actions"):
                        # If* ELSE branch
                        action._else_actions = list(orig._else_actions)

            # Inject inline branch editor data
            if self._branch_data:
                if "then_actions" in self._branch_data and hasattr(action, "_then_actions"):
                    action._then_actions = list(action._then_actions) + self._branch_data["then_actions"]
                if "else_actions" in self._branch_data and hasattr(action, "_else_actions"):
                    action._else_actions = list(action._else_actions) + self._branch_data["else_actions"]
                if "sub_actions" in self._branch_data and hasattr(action, "_sub_actions"):
                    action._sub_actions = list(action._sub_actions) + self._branch_data["sub_actions"]

            if not self._validate_image_path(action):
                return

            self._result_action = action
            self.action_ready.emit(action)  # fire BEFORE accept

            # Save to recent actions
            from PyQt6.QtCore import QSettings
            settings = QSettings("AutoMacro", "ActionEditor")
            recent = settings.value("recent_actions", [])
            if not isinstance(recent, list):
                recent = []
            if atype in recent:
                recent.remove(atype)
            recent.insert(0, atype)
            settings.setValue("recent_actions", recent[:5])

            self.accept()
            logger.info("Action created: type=%s params=%s", atype, params)
        except Exception as e:
            logger.warning("Action creation failed: type=%s error=%s", atype, e)
            from PyQt6.QtWidgets import QMessageBox

            QMessageBox.warning(
                self, "Thông Số Không Hợp Lệ", f"Vui lòng kiểm tra lại các thông số đã nhập.\n\n" f"Chi tiết: {e}"
            )

    def _collect_params(self) -> dict[str, Any]:
        """Extract parameter values from widgets."""
        from PyQt6.QtWidgets import QTextEdit as _QTextEdit
        params: dict[str, Any] = {}
        for key, widget in self._param_widgets.items():
            if key.startswith("_branch_list_"):
                continue  # Internal widget, skip
            if isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                params[key] = widget.value()
            elif isinstance(widget, _QTextEdit):
                params[key] = widget.toPlainText()
            elif isinstance(widget, QLineEdit):
                params[key] = widget.text()
            elif isinstance(widget, QCheckBox):
                params[key] = widget.isChecked()
            elif isinstance(widget, QComboBox):
                # Prefer itemData if set, else fallback to text
                data = widget.currentData()
                params[key] = data if data is not None else widget.currentText()

        # Handle keys_str → keys list
        if "keys_str" in params:
            params["keys"] = [k.strip() for k in params.pop("keys_str").split("+") if k.strip()]
        return params

    def _validate_image_path(self, action: Action) -> bool:
        """Warn if image path doesn't exist. Returns False to cancel."""
        if not hasattr(action, "image_path") or not action.image_path:
            return True
        if os.path.isfile(action.image_path):
            return True
        from PyQt6.QtWidgets import QMessageBox

        r = QMessageBox.warning(
            self,
            "Warning",
            f"Image file not found:\n{action.image_path}\n\nContinue anyway?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        return r == QMessageBox.StandardButton.Yes

    def get_action(self) -> Optional[Action]:
        return self._result_action
