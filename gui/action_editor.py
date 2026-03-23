"""
Action Editor – dialog and panel for adding/editing macro actions.
Provides a user-friendly form for each action type with appropriate widgets.
"""

import logging
import os
from typing import Optional, Callable, Any

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QComboBox, QSpinBox, QDoubleSpinBox, QLineEdit, QPushButton,
    QGroupBox, QCheckBox, QFileDialog, QWidget, QLabel,
    QTextBrowser, QFrame, QSizePolicy,
)
from PyQt6.QtCore import QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QKeySequence, QShortcut

from gui.coordinate_picker import CoordinatePickerOverlay
from gui.image_capture import ImageCaptureOverlay

from core.action import Action, get_action_class, get_all_action_types

logger = logging.getLogger(__name__)

# Grouped action categories for the type selector
ACTION_CATEGORIES: list[tuple[str, list[tuple[str, str]]]] = [
    ("🖱 Mouse", [
        ("mouse_click", "Click"),
        ("mouse_double_click", "Double Click"),
        ("mouse_right_click", "Right Click"),
        ("mouse_move", "Move"),
        ("mouse_drag", "Drag"),
        ("mouse_scroll", "Scroll"),
    ]),
    ("⌨ Keyboard", [
        ("key_press", "Key Press"),
        ("key_combo", "Key Combo"),
        ("type_text", "Type Text"),
        ("hotkey", "Hotkey"),
    ]),
    ("🖼 Image", [
        ("wait_for_image", "Wait for Image"),
        ("click_on_image", "Click on Image"),
        ("image_exists", "Image Exists"),
        ("take_screenshot", "Take Screenshot"),
    ]),
    ("🎨 Pixel", [
        ("check_pixel_color", "Check Pixel Color"),
        ("wait_for_color", "Wait for Color"),
    ]),
    ("⏱ Flow Control", [
        ("delay", "Delay"),
        ("loop_block", "Loop Block"),
        ("if_image_found", "If Image Found"),
        ("if_pixel_color", "If Pixel Color"),
        ("if_variable", "If Variable"),
    ]),
    ("📊 Variables", [
        ("set_variable", "Set Variable"),
        ("split_string", "Split String"),
        ("comment", "Comment / Label"),
    ]),
    ("🖥 System", [
        ("activate_window", "Activate Window"),
        ("log_to_file", "Log to File"),
        ("read_clipboard", "Read Clipboard"),
        ("read_file_line", "Read File Line"),
        ("write_to_file", "Write to File"),
        ("secure_type_text", "Secure Type Text"),
        ("run_macro", "Run Sub-Macro"),
        ("capture_text", "Capture Text (OCR)"),
    ]),
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
    "hotkey": "Nhấn tổ hợp phím nóng (hỗ trợ nhiều phím)",
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
}

from gui.help_content import _ACTION_HELP  # noqa: F401


class _HelpPopup(QFrame):
    """Persistent help popup with close button and Escape key support."""

    def __init__(self, html: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(
            "_HelpPopup { background: #1e1e2e; border: 1px solid #6c6cff; "
            "border-radius: 8px; }"
        )
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
        browser.setHtml(f"<div style='color:#ccc; font-size:12px; "
                        f"line-height:1.5'>{html}</div>")
        browser.setOpenExternalLinks(False)
        browser.setStyleSheet(
            "QTextBrowser { background: transparent; border: none; "
            "color: #ccc; }"
        )
        browser.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
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

    def __init__(self, parent: Any = None, action: Optional[Action] = None,
                 macro_dir: str = "") -> None:
        super().__init__(parent)
        self._action = action
        self._macro_dir = macro_dir
        self._result_action: Optional[Action] = None
        self._param_widgets: dict[str, Any] = {}

        self.setWindowTitle("Sửa Action" if action else "Thêm Action")
        self.setMinimumWidth(480)
        self.resize(500, 520)
        self.setSizeGripEnabled(True)
        self.setModal(True)
        self._param_cache: dict[str, Any] = {}  # persist x,y across types

        self._setup_ui()

        if action:
            self._load_action(action)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Action type selector — grouped with category headers
        type_group = QGroupBox("Loại Action")
        type_layout = QVBoxLayout(type_group)

        # Combo + Help button in same row
        combo_row = QHBoxLayout()
        self._type_combo = QComboBox()
        self._type_combo.blockSignals(True)
        self._build_grouped_combo()
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

        # Common settings
        common_group = QGroupBox("Cài đặt chung")
        common_layout = QFormLayout(common_group)

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
        _err_items = [("Dừng", "stop"), ("Bỏ qua", "skip"),
                      ("Thử lại: 3", "retry:3"), ("Thử lại: 5", "retry:5")]
        for vi_label, en_val in _err_items:
            self._error_combo.addItem(vi_label, en_val)
        self._error_combo.setToolTip("Hành động khi action bị lỗi")
        common_layout.addRow("Khi lỗi:", self._error_combo)

        layout.addWidget(common_group)

        # OK / Cancel
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        cancel_btn = QPushButton("Hủy")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        ok_btn = QPushButton("Đồng ý")
        ok_btn.setObjectName("primaryButton")
        ok_btn.clicked.connect(self._on_ok)
        btn_layout.addWidget(ok_btn)
        layout.addLayout(btn_layout)

        # Initialize params for the pre-selected type
        self._on_type_changed()

    def _build_grouped_combo(self) -> None:
        """Build grouped combo box with category headers."""
        from PyQt6.QtGui import QStandardItemModel, QStandardItem, QFont
        model = QStandardItemModel()
        for cat_label, actions in ACTION_CATEGORIES:
            # Category header (non-selectable, bold)
            header = QStandardItem(cat_label)
            header_font = QFont()
            header_font.setBold(True)
            header.setFont(header_font)
            header.setEnabled(False)                     # non-selectable
            header.setSelectable(False)
            model.appendRow(header)
            # Action items (indented with spaces)
            for atype, label in actions:
                item = QStandardItem(f"    {label}")
                item.setData(atype, Qt.ItemDataRole.UserRole)
                model.appendRow(item)
        self._type_combo.setModel(model)

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

    def _on_type_changed(self) -> None:
        """Rebuild parameter widgets when action type changes."""
        self._clear_params()
        atype = self._type_combo.currentData(Qt.ItemDataRole.UserRole)
        if not atype:
            self._type_desc_label.setText("")
            return

        # Update description (P2 #8)
        self._type_desc_label.setText(
            f"ℹ️ {_ACTION_DESCRIPTIONS.get(atype, '')}")

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
            "if_pixel_color": lambda: self._build_pixel_params(atype),
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
        }
        builder = builders.get(atype)
        if builder:
            builder()
        elif atype:
            import logging
            logging.getLogger(__name__).warning(
                "No param builder registered for action type '%s'", atype)

        # Restore cached x,y values if new type also has them
        for key in ("x", "y"):
            if key in self._param_cache and key in self._param_widgets:
                w = self._param_widgets[key]
                if isinstance(w, QSpinBox):
                    w.setValue(self._param_cache[key])

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
                f"<b>{display_name}</b><br><br>"
                f"{desc}<br><br>"
                "<i>Chưa có hướng dẫn chi tiết cho action này.</i>"
            )
        # Close previous popup if open
        if hasattr(self, '_help_popup') and self._help_popup is not None:
            self._help_popup.close()
        self._help_popup = _HelpPopup(html, parent=self)
        # Position to the right of the help button
        btn_pos = self._help_btn.mapToGlobal(
            self._help_btn.rect().topRight())
        self._help_popup.move(btn_pos.x() + 6, btn_pos.y())
        self._help_popup.show()
        self._help_popup.setFocus()

    def _build_mouse_params(self, atype: str) -> None:
        self._add_xy_params()
        if atype in ("mouse_click", "mouse_move"):
            self._add_duration_param()

    def _build_drag_params(self) -> None:
        self._add_xy_params()
        self._add_duration_param()
        self._add_button_param()

    def _build_scroll_params(self) -> None:
        self._add_xy_params()
        clicks = QSpinBox()
        clicks.setRange(-100, 100)
        clicks.setValue(3)
        self._params_layout.addRow("Cuộn (+ lên, - xuống):", clicks)
        self._param_widgets["clicks"] = clicks

    def _build_key_press_params(self) -> None:
        key_edit = QLineEdit("enter")
        self._params_layout.addRow("Phím:", key_edit)
        self._param_widgets["key"] = key_edit

    def _build_key_combo_params(self) -> None:
        keys_edit = QLineEdit("ctrl+c")
        keys_edit.setPlaceholderText("VD: ctrl+shift+s")
        self._params_layout.addRow("Tổ hợp phím (+):", keys_edit)
        self._param_widgets["keys_str"] = keys_edit

    def _build_type_text_params(self) -> None:
        text_edit = QLineEdit()
        text_edit.setPlaceholderText("Nội dung cần gõ...")
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
        dur = QSpinBox()
        dur.setRange(0, 300000)
        dur.setSuffix(" ms")
        dur.setValue(1000)
        self._params_layout.addRow("Thời gian:", dur)
        self._param_widgets["duration_ms"] = dur

    def _build_image_params(self, atype: str) -> None:
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

    def _build_screenshot_params(self) -> None:
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
        pattern_edit.setToolTip(
            "%Y=năm, %m=tháng, %d=ngày, %H=giờ, %M=phút, %S=giây"
        )
        self._params_layout.addRow("Tên file:", pattern_edit)
        self._param_widgets["filename_pattern"] = pattern_edit

        # Optional region (0 = full screen)
        for label, key, default in [
            ("Region X:", "region_x", 0), ("Region Y:", "region_y", 0),
            ("Region W:", "region_w", 0), ("Region H:", "region_h", 0),
        ]:
            spin = QSpinBox()
            spin.setRange(0, 9999)
            spin.setValue(default)
            spin.setToolTip("0 = chụp toàn màn hình")
            self._params_layout.addRow(label, spin)
            self._param_widgets[key] = spin

    def _browse_dir(self, line_edit: QLineEdit) -> None:
        path = QFileDialog.getExistingDirectory(self, "Chọn thư mục")
        if path:
            line_edit.setText(path)

    def _build_pixel_params(self, atype: str) -> None:
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
        if atype == "wait_for_color":
            timeout = QSpinBox()
            timeout.setRange(0, 120000)
            timeout.setSuffix(" ms")
            timeout.setValue(10000)
            self._params_layout.addRow("Giới hạn:", timeout)
            self._param_widgets["timeout_ms"] = timeout

    def _add_xy_params(self) -> None:
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
            "Nhấn để chọn toạ độ trên màn hình.\n"
            "Click bất kỳ → toạ độ tự điền.\n"
            "Nhấn Escape để hủy."
        )
        pick_btn.clicked.connect(
            lambda: self._start_coordinate_picker(x_spin, y_spin)
        )
        self._params_layout.addRow("", pick_btn)

    def _build_if_image_found_params(self) -> None:
        """Builder for IfImageFound — image path, confidence, timeout, ELSE."""
        self._add_image_params()

        timeout = QSpinBox()
        timeout.setRange(0, 120000)
        timeout.setSuffix(" ms")
        timeout.setValue(5000)
        self._params_layout.addRow("Giới hạn:", timeout)
        self._param_widgets["timeout_ms"] = timeout

        # 3.1: ELSE action (optional)
        else_action = QLineEdit()
        else_action.setPlaceholderText('Tuỳ chọn: {"type":"log_to_file","params":{"message":"Không tìm thấy ảnh"}}')
        else_action.setToolTip("Action thực thi khi ảnh KHÔNG tìm thấy (JSON)")
        self._params_layout.addRow("Nếu không:", else_action)
        self._param_widgets["else_action_json"] = else_action

    def _build_loop_block_params(self) -> None:
        """Builder for LoopBlock — iterations count."""
        iterations = QSpinBox()
        iterations.setRange(0, 999999)
        iterations.setValue(1)
        iterations.setSpecialValueText("∞ Vô hạn")
        iterations.setToolTip("0 = lặp vô hạn (cho đến khi dừng)")
        self._params_layout.addRow("Số lần lặp:", iterations)
        self._param_widgets["iterations"] = iterations

    def _build_if_variable_params(self) -> None:
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

        # 3.1: ELSE action (optional)
        else_action = QLineEdit()
        else_action.setPlaceholderText('Tuỳ chọn: {"type":"set_variable","params":{"var_name":"x","value":"0","operation":"set"}}')
        else_action.setToolTip("Action thực thi khi điều kiện SAI (JSON)")
        self._params_layout.addRow("Nếu không:", else_action)
        self._param_widgets["else_action_json"] = else_action

    def _build_set_variable_params(self) -> None:
        var_name = QLineEdit()
        var_name.setPlaceholderText("VD: counter, row")
        self._params_layout.addRow("Biến:", var_name)
        self._param_widgets["var_name"] = var_name

        value = QLineEdit()
        value.setPlaceholderText("VD: 0, 1, hello")
        self._params_layout.addRow("Giá trị:", value)
        self._param_widgets["value"] = value

        operation = QComboBox()
        operation.addItems(["set", "increment", "decrement", "add",
                           "subtract", "multiply", "divide", "modulo", "eval"])
        self._params_layout.addRow("Phép toán:", operation)
        self._param_widgets["operation"] = operation

    def _build_split_string_params(self) -> None:
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
        path = QLineEdit()
        path.setPlaceholderText("Đường dẫn file macro .json")
        self._params_layout.addRow("File macro:", path)
        self._param_widgets["macro_path"] = path

        browse_btn = QPushButton("📂 Duyệt...")
        def _browse():
            from PyQt6.QtWidgets import QFileDialog
            fpath, _ = QFileDialog.getOpenFileName(
                self, "Chọn macro", "macros",
                "JSON Macros (*.json)")
            if fpath:
                path.setText(fpath)
        browse_btn.clicked.connect(_browse)
        self._params_layout.addRow("", browse_btn)

    def _build_capture_text_params(self) -> None:
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

    def _start_coordinate_picker(self, x_spin: QSpinBox, y_spin: QSpinBox) -> None:
        """Launch coordinate picker overlay after hiding the dialog."""
        self._picker = CoordinatePickerOverlay()
        self._picker_x_target = x_spin
        self._picker_y_target = y_spin
        self._picker.coordinate_picked.connect(self._on_coordinate_picked)
        self._picker.cancelled.connect(self._on_picker_cancelled)
        # Hide both the dialog AND the main window behind it
        self._parent_window = self.parent()
        if self._parent_window:
            self._parent_window.hide()
        self.hide()
        # Short delay so windows fully hide before screenshot
        QTimer.singleShot(300, self._picker.start)

    def _on_coordinate_picked(self, x: int, y: int) -> None:
        """Handle picked coordinates."""
        self._picker_x_target.setValue(x)
        self._picker_y_target.setValue(y)
        if self._parent_window:
            self._parent_window.show()
            self._parent_window.activateWindow()
        self.show()
        self.activateWindow()

    def _on_picker_cancelled(self) -> None:
        """Handle picker cancellation."""
        if self._parent_window:
            self._parent_window.show()
            self._parent_window.activateWindow()
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
        capture_btn.setToolTip(
            "Chụp vùng màn hình → tự động điền path\n"
            "Kéo vùng chọn, nhấn Escape để hủy."
        )
        capture_btn.clicked.connect(
            lambda: self._start_image_capture(img_edit)
        )
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

    def _browse_image(self, line_edit: QLineEdit) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Image", self._macro_dir,
            "Images (*.png *.jpg *.bmp)")
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
        if self._capture_parent:
            self._capture_parent.hide()
        self.hide()
        QTimer.singleShot(300, self._capture_overlay.start)

    def _on_image_captured(self, path: str) -> None:
        """Handle captured image — fill path into target edit."""
        self._capture_target_edit.setText(path)
        if self._capture_parent:
            self._capture_parent.show()
            self._capture_parent.activateWindow()
        self.show()
        self.activateWindow()
        logger.info("Image captured for template: %s", path)

    def _on_capture_cancelled(self) -> None:
        """Restore windows if capture was cancelled."""
        if self._capture_parent:
            self._capture_parent.show()
            self._capture_parent.activateWindow()
        self.show()
        self.activateWindow()

    def _load_action(self, action: Action) -> None:
        """Pre-fill dialog from an existing action."""
        # Select the correct type
        for i in range(self._type_combo.count()):
            if self._type_combo.itemData(i, Qt.ItemDataRole.UserRole) == action.ACTION_TYPE:
                self._type_combo.setCurrentIndex(i)
                break

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

        # Type-specific params
        params = action._get_params()
        for key, widget in self._param_widgets.items():
            if key == "keys_str" and "keys" in params:
                widget.setText("+".join(params["keys"]))
            elif key in params:
                val = params[key]
                if isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                    widget.setValue(val)
                elif isinstance(widget, QLineEdit):
                    widget.setText(str(val))
                elif isinstance(widget, QComboBox):
                    idx = widget.findText(str(val))
                    if idx >= 0:
                        widget.setCurrentIndex(idx)

    def _on_ok(self) -> None:
        """Build the action from widget values and accept."""
        atype = self._type_combo.currentData(Qt.ItemDataRole.UserRole)
        params = self._collect_params()

        # Create action
        try:
            cls = get_action_class(atype)
            action = cls(**params)
            action.delay_after = self._delay_spin.value()
            action.repeat_count = self._repeat_spin.value()
            action.description = self._desc_edit.text()
            action.enabled = self._enabled_check.isChecked()
            action.on_error = self._error_combo.currentData() or "stop"

            if not self._validate_image_path(action):
                return

            self._result_action = action
            self.action_ready.emit(action)  # fire BEFORE accept
            self.accept()
            logger.info("Action created: type=%s params=%s", atype, params)
        except Exception as e:
            logger.warning("Action creation failed: type=%s error=%s", atype, e)
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self, "Thông Số Không Hợp Lệ",
                f"Vui lòng kiểm tra lại các thông số đã nhập.\n\n"
                f"Chi tiết: {e}")

    def _collect_params(self) -> dict[str, Any]:
        """Extract parameter values from widgets."""
        params: dict[str, Any] = {}
        for key, widget in self._param_widgets.items():
            if isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                params[key] = widget.value()
            elif isinstance(widget, QLineEdit):
                params[key] = widget.text()
            elif isinstance(widget, QComboBox):
                params[key] = widget.currentText()

        # Handle keys_str → keys list
        if "keys_str" in params:
            params["keys"] = [k.strip() for k in
                              params.pop("keys_str").split("+") if k.strip()]
        return params

    def _validate_image_path(self, action: Action) -> bool:
        """Warn if image path doesn't exist. Returns False to cancel."""
        if not hasattr(action, 'image_path') or not action.image_path:
            return True
        if os.path.isfile(action.image_path):
            return True
        from PyQt6.QtWidgets import QMessageBox
        r = QMessageBox.warning(
            self, "Warning",
            f"Image file not found:\n{action.image_path}\n\nContinue anyway?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        return r == QMessageBox.StandardButton.Yes

    def get_action(self) -> Optional[Action]:
        return self._result_action
