"""
ActionListPanel — Extracted from main_window.py.

Contains: action table (QTableWidget), tree view (QTreeView),
search filter, move/duplicate/copy/paste buttons, view toggle,
and empty state overlay.
"""

import logging

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QKeySequence
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from core.action import Action
from gui.action_tree_model import ActionTreeModel

logger = logging.getLogger(__name__)

# Icon map for action types
TYPE_ICONS: dict[str, str] = {
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
    "take_screenshot": "📸",
    "loop_block": "🔁",
    "if_image_found": "❓",
    "if_pixel_color": "🎯",
    "if_variable": "📏",
    "set_variable": "📊",
    "split_string": "✂",
    "check_pixel_color": "🎨",
    "wait_for_color": "🎨",
    "activate_window": "🪟",
    "log_to_file": "📝",
    "read_clipboard": "📋",
    "read_file_line": "📖",
    "write_to_file": "💾",
    "secure_type_text": "🔐",
    "run_macro": "▶️",
    "comment": "💬",
    "capture_text": "🔍",
}


class ActionListPanel(QWidget):
    """Action list with table/tree views, filter, and manipulation buttons.

    Signals:
        edit_requested(int): row double-clicked or Enter pressed
        context_menu_requested(QPoint): right-click at position
        move_up_requested(): Move Up button clicked
        move_down_requested(): Move Down button clicked
        duplicate_requested(): Duplicate button clicked
        copy_requested(): Copy button clicked
        paste_requested(): Paste button clicked
        view_mode_changed(bool): toggled tree mode
    """

    edit_requested = pyqtSignal()
    context_menu_requested = pyqtSignal(object)  # QPoint
    move_up_requested = pyqtSignal()
    move_down_requested = pyqtSignal()
    duplicate_requested = pyqtSignal()
    copy_requested = pyqtSignal()
    paste_requested = pyqtSignal()
    filter_changed = pyqtSignal(str)
    view_mode_changed = pyqtSignal(bool)

    def __init__(self, actions: list[Action], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._actions = actions
        self._tree_mode = False
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Header
        header_label = QLabel("Danh sách Action")
        header_label.setObjectName("headerLabel")
        layout.addWidget(header_label)

        # Search/filter bar
        self._filter_edit = QLineEdit()
        self._filter_edit.setPlaceholderText("🔍 Tìm action...")
        self._filter_edit.setClearButtonEnabled(True)
        self._filter_edit.setAccessibleName("Tìm kiếm action")
        self._filter_edit.textChanged.connect(self.filter_changed.emit)
        layout.addWidget(self._filter_edit)

        # ── Table view ──
        self._table = QTableWidget(0, 6)
        self._table.setAccessibleName("Bảng danh sách action")
        self._table.setHorizontalHeaderLabels(["#", "", "Hành động", "Trễ", "✓", "Mô tả"])
        h_header = self._table.horizontalHeader()
        assert h_header is not None
        h_header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        h_header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        h_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        h_header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        h_header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        h_header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._table.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self._table.setDragEnabled(True)
        self._table.setAcceptDrops(True)
        self._table.setDropIndicatorShown(True)
        vert_header = self._table.verticalHeader()
        assert vert_header is not None
        vert_header.setVisible(False)
        self._table.setShowGrid(False)
        self._table.setAlternatingRowColors(True)
        self._table.doubleClicked.connect(lambda: self.edit_requested.emit())
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self.context_menu_requested.emit)
        layout.addWidget(self._table)

        # ── Tree view ──
        self._tree = QTreeView()
        self._tree.setAccessibleName("Cây hành động")
        self._tree.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._tree.setAlternatingRowColors(True)
        self._tree.setAnimated(True)
        self._tree.setIndentation(24)
        self._tree.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self._tree.setDragEnabled(True)
        self._tree.setAcceptDrops(True)
        self._tree.setDropIndicatorShown(True)
        self._tree.doubleClicked.connect(lambda: self.edit_requested.emit())
        self._tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self.context_menu_requested.emit)
        self._tree_model = ActionTreeModel(self._actions)
        self._tree.setModel(self._tree_model)
        tree_header = self._tree.header()
        if tree_header:
            tree_header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            tree_header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
            tree_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
            tree_header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self._tree.setVisible(False)
        layout.addWidget(self._tree)

        # ── View toggle ──
        toggle_layout = QHBoxLayout()
        self._view_toggle_btn = QPushButton("🌳 Chế độ Cây")
        self._view_toggle_btn.setToolTip("Chuyển giữa bảng phẳng và chế độ cây phân cấp")
        self._view_toggle_btn.setCheckable(True)
        self._view_toggle_btn.clicked.connect(self._on_view_toggle)
        toggle_layout.addWidget(self._view_toggle_btn)
        toggle_layout.addStretch()
        layout.addLayout(toggle_layout)

        # ── Empty overlay ──
        self._empty_overlay = QLabel(
            "📋 Chưa có action nào\n\n"
            "Bắt đầu bằng cách:\n"
            "  ➕  Click  Thêm  để tạo action đầu tiên\n"
            "  📂  Mở macro có sẵn (Ctrl+O)\n"
            "  ⏺  Nhấn nút  Ghi  để ghi lại thao tác\n\n"
            "Phím tắt: F6=Chạy  F7=Dừng tạm  F8=Dừng hẳn  F9=Ghi\n"
            "Nhấn F1 để xem hướng dẫn đầy đủ"
        )
        self._empty_overlay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_overlay.setObjectName("emptyOverlay")
        self._empty_overlay.setWordWrap(True)
        layout.addWidget(self._empty_overlay)

        # ── Move / Manipulation buttons ──
        btn_layout = QHBoxLayout()

        self._up_btn = QPushButton("⬆ Lên")
        self._up_btn.setShortcut(QKeySequence("Ctrl+Up"))
        self._up_btn.setToolTip("Di chuyển lên (Ctrl+↑)")
        self._up_btn.setAccessibleName("Di chuyển action lên")
        self._up_btn.clicked.connect(self.move_up_requested.emit)
        btn_layout.addWidget(self._up_btn)

        self._down_btn = QPushButton("⬇ Xuống")
        self._down_btn.setShortcut(QKeySequence("Ctrl+Down"))
        self._down_btn.setToolTip("Di chuyển xuống (Ctrl+↓)")
        self._down_btn.setAccessibleName("Di chuyển action xuống")
        self._down_btn.clicked.connect(self.move_down_requested.emit)
        btn_layout.addWidget(self._down_btn)

        self._dup_btn = QPushButton("📋 Nhân bản")
        self._dup_btn.setShortcut(QKeySequence("Ctrl+D"))
        self._dup_btn.setToolTip("Nhân bản action (Ctrl+D)")
        self._dup_btn.setAccessibleName("Nhân bản action")
        self._dup_btn.clicked.connect(self.duplicate_requested.emit)
        btn_layout.addWidget(self._dup_btn)

        self._copy_btn = QPushButton("📄 Sao chép")
        self._copy_btn.setShortcut(QKeySequence("Ctrl+C"))
        self._copy_btn.setToolTip("Sao chép action (Ctrl+C)")
        self._copy_btn.setAccessibleName("Sao chép action")
        self._copy_btn.clicked.connect(self.copy_requested.emit)
        btn_layout.addWidget(self._copy_btn)

        self._paste_btn = QPushButton("📥 Dán")
        self._paste_btn.setShortcut(QKeySequence("Ctrl+V"))
        self._paste_btn.setToolTip("Dán action từ clipboard (Ctrl+V)")
        self._paste_btn.setAccessibleName("Dán action")
        self._paste_btn.clicked.connect(self.paste_requested.emit)
        btn_layout.addWidget(self._paste_btn)

        btn_layout.addStretch()

        # Stats label
        self._stats_label = QLabel("")
        self._stats_label.setObjectName("subtitleLabel")
        btn_layout.addWidget(self._stats_label)

        layout.addLayout(btn_layout)

    def _on_view_toggle(self, checked: bool) -> None:
        """Toggle between table and tree view."""
        self._tree_mode = checked
        self.view_mode_changed.emit(checked)
        has_actions = len(self._actions) > 0
        self._table.setVisible(has_actions and not checked)
        self._tree.setVisible(has_actions and checked)
        self._view_toggle_btn.setText("📋 Chế độ Bảng" if checked else "🌳 Chế độ Cây")

    @property
    def table(self) -> QTableWidget:
        return self._table

    @property
    def tree(self) -> QTreeView:
        return self._tree

    @property
    def tree_model(self) -> ActionTreeModel:
        return self._tree_model

    @property
    def filter_edit(self) -> QLineEdit:
        return self._filter_edit

    @property
    def stats_label(self) -> QLabel:
        return self._stats_label

    @property
    def empty_overlay(self) -> QLabel:
        return self._empty_overlay
