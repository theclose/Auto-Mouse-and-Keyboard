"""
ActionListPanel — Tree-only action list with filter and manipulation buttons.

Contains: action tree view (QTreeView with ActionTreeModel),
search filter (via QSortFilterProxyModel), move/duplicate/copy/paste buttons,
and empty state overlay.
"""

import logging

from PyQt6.QtCore import QModelIndex, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QToolButton,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from core.action import Action
from gui.action_tree_model import ActionTreeFilterProxy, ActionTreeModel

logger = logging.getLogger(__name__)


class ActionListPanel(QWidget):
    """Action list with tree view, filter, and manipulation buttons.

    Signals:
        edit_requested(): row double-clicked or Enter pressed
        context_menu_requested(QPoint): right-click at position
        move_up_requested(): Move Up button clicked
        move_down_requested(): Move Down button clicked
        duplicate_requested(): Duplicate button clicked
        copy_requested(): Copy button clicked
        paste_requested(): Paste button clicked
        filter_changed(str): filter text changed
    """

    edit_requested = pyqtSignal()
    context_menu_requested = pyqtSignal(object)  # QPoint
    move_up_requested = pyqtSignal()
    move_down_requested = pyqtSignal()
    duplicate_requested = pyqtSignal()
    copy_requested = pyqtSignal()
    paste_requested = pyqtSignal()
    delete_requested = pyqtSignal()
    filter_changed = pyqtSignal(str)
    add_action_requested = pyqtSignal()
    record_requested = pyqtSignal()
    open_file_requested = pyqtSignal()
    quick_add_requested = pyqtSignal(str)  # emit action type for instant add

    def __init__(self, actions: list[Action], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._actions = actions
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Header
        header_label = QLabel("Danh sách Action")
        header_label.setObjectName("headerLabel")
        layout.addWidget(header_label)

        # Search/filter bar + type filter
        filter_row = QHBoxLayout()
        filter_row.setContentsMargins(0, 0, 0, 0)

        self._filter_edit = QLineEdit()
        self._filter_edit.setPlaceholderText("🔍 Tìm action...")
        self._filter_edit.setClearButtonEnabled(True)
        self._filter_edit.setAccessibleName("Tìm kiếm action")
        filter_row.addWidget(self._filter_edit, stretch=3)

        self._type_combo = QComboBox()
        self._type_combo.setToolTip("Lọc theo loại action")
        self._type_combo.setFixedHeight(28)
        _type_options = [
            ("", "🎯 Tất cả"),
            ("click", "🖱 Click"), ("type_text", "⌨ Nhập text"),
            ("hotkey", "⌘ Phím tắt"), ("wait", "⏳ Chờ"),
            ("scroll", "🖱 Cuộn"), ("move_mouse", "🖱 Di chuột"),
            ("loop_block", "🔁 Loop"), ("if_image_found", "🖼 Nếu hình"),
            ("if_pixel_color", "🎨 Nếu pixel"), ("if_variable", "📊 Nếu biến"),
            ("set_variable", "📊 Đặt biến"), ("comment", "💬 Ghi chú"),
            ("group", "📦 Group"), ("capture_text", "🔍 OCR"),
            ("run_macro", "▶️ Chạy macro"), ("split_string", "✂️ Chia chuỗi"),
            ("activate_window", "🖥 Cửa sổ"), ("log_to_file", "📝 Ghi file"),
            ("run_command", "⚡ Lệnh hệ thống"),
        ]
        for type_key, label in _type_options:
            self._type_combo.addItem(label, type_key)
        self._type_combo.currentIndexChanged.connect(self._on_type_filter_changed)
        filter_row.addWidget(self._type_combo, stretch=1)

        layout.addLayout(filter_row)

        # ── Expand/Collapse controls ──
        expand_layout = QHBoxLayout()
        expand_layout.setContentsMargins(0, 0, 0, 0)

        self._expand_all_btn = QPushButton("⊞ Mở hết")
        self._expand_all_btn.setToolTip("Mở tất cả nhánh")
        self._expand_all_btn.setFixedHeight(24)
        expand_layout.addWidget(self._expand_all_btn)

        self._collapse_all_btn = QPushButton("⊟ Đóng hết")
        self._collapse_all_btn.setToolTip("Đóng tất cả nhánh")
        self._collapse_all_btn.setFixedHeight(24)
        expand_layout.addWidget(self._collapse_all_btn)

        self._expand_l1_btn = QPushButton("⊟₁ Mức 1")
        self._expand_l1_btn.setToolTip("Chỉ mở mức đầu tiên")
        self._expand_l1_btn.setFixedHeight(24)
        expand_layout.addWidget(self._expand_l1_btn)

        expand_layout.addStretch()
        layout.addLayout(expand_layout)

        # ── Quick-Add Toolbar ──
        quick_row = QHBoxLayout()
        quick_row.setContentsMargins(0, 0, 0, 0)
        quick_row.setSpacing(3)
        quick_label = QLabel("⚡")
        quick_label.setStyleSheet("font-family: 'Segoe UI Emoji', 'Segoe UI'; font-size: 12pt;")
        quick_label.setToolTip("Thêm nhanh (không cần mở dialog)")
        quick_label.setFixedWidth(20)
        quick_row.addWidget(quick_label)
        _quick_btn_style = (
            "QPushButton { font-size: 8pt; padding: 2px 6px; min-height: 22px; }"
        )
        for label, atype, tip in [
            ("+Click", "mouse_click", "Click chuột"),
            ("+Gõ", "type_text", "Gõ chữ"),
            ("+Chờ", "delay", "Delay"),
            ("+Lặp", "loop_block", "Loop"),
            ("+If", "if_variable", "If"),
            ("+Chú", "comment", "Ghi chú"),
        ]:
            btn = QPushButton(label)
            btn.setObjectName(f"quick_add_{atype}")
            btn.setFixedHeight(26)
            btn.setStyleSheet(_quick_btn_style)
            btn.setToolTip(f"Thêm nhanh: {tip}")
            btn.clicked.connect(lambda _, t=atype: self.quick_add_requested.emit(t))
            quick_row.addWidget(btn)
        quick_row.addStretch()
        layout.addLayout(quick_row)

        # ── P6: Breadcrumb navigation ──
        self._breadcrumb_label = QLabel("")
        self._breadcrumb_label.setObjectName("breadcrumbLabel")
        self._breadcrumb_label.setStyleSheet(
            "QLabel { font-size: 9pt; color: #8a8aa8; padding: 2px 6px; "
            "background: rgba(30, 30, 50, 0.5); border-radius: 4px; }"
        )
        self._breadcrumb_label.setWordWrap(True)
        self._breadcrumb_label.setVisible(False)  # Hidden when root selected
        layout.addWidget(self._breadcrumb_label)

        # ── Tree model + filter proxy ──
        self._tree_model = ActionTreeModel(self._actions)
        self._filter_proxy = ActionTreeFilterProxy()
        self._filter_proxy.setSourceModel(self._tree_model)
        self._filter_proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

        # Connect filter
        self._filter_edit.textChanged.connect(self._on_filter_text_changed)

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
        # Style the drop indicator for better visibility
        self._tree.setStyleSheet(
            "QTreeView::indicator:drop { "
            "  background: rgba(0, 120, 215, 0.3); "
            "  border: 2px solid #0078d7; "
            "  border-radius: 3px; "
            "} "
            "QTreeView { "
            "  show-decoration-selected: 1; "
            "}"
        )
        self._tree.doubleClicked.connect(lambda: self.edit_requested.emit())
        self._tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self.context_menu_requested.emit)
        self._tree.setModel(self._filter_proxy)

        tree_header = self._tree.header()
        if tree_header:
            tree_header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)  # #
            tree_header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)  # ✓
            tree_header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)  # Loại
            tree_header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)  # Chi tiết
            tree_header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)  # Delay
            tree_header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)  # Mô tả
            tree_header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)  # ⏱ Thực tế
            # Column visibility: right-click header to toggle
            tree_header.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            tree_header.customContextMenuRequested.connect(self._show_column_menu)

        # Default: hide less-used columns (✓ only; # must stay for tree indentation)
        self._tree.setColumnHidden(1, True)   # COL_ENABLED

        layout.addWidget(self._tree)

        # Connect expand/collapse buttons (after tree is created)
        self._expand_mode = "all"  # Default: expand all nodes
        self._expand_all_btn.clicked.connect(self._set_expand_all)
        self._collapse_all_btn.clicked.connect(self._set_collapse_all)
        self._expand_l1_btn.clicked.connect(self._set_expand_level_1)

        # Apply default expand mode
        self._tree.expandAll()

        # ── Empty overlay (CTA) ──
        self._empty_overlay = QWidget()
        self._empty_overlay.setObjectName("emptyOverlay")
        overlay_layout = QVBoxLayout(self._empty_overlay)
        overlay_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        overlay_layout.setSpacing(8)

        title = QLabel("📋 Chưa có action nào")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 14pt; color: #ababc0; background: transparent;")
        overlay_layout.addWidget(title)

        subtitle = QLabel("Bắt đầu tạo macro đầu tiên")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("font-size: 10pt; color: #8a8aa8; background: transparent;")
        overlay_layout.addWidget(subtitle)

        overlay_layout.addSpacing(12)

        add_cta = QPushButton("➕ Thêm Action")
        add_cta.setObjectName("primaryButton")
        add_cta.setFixedWidth(200)
        add_cta.clicked.connect(self.add_action_requested.emit)
        overlay_layout.addWidget(add_cta, alignment=Qt.AlignmentFlag.AlignCenter)

        rec_cta = QPushButton("⏺ Ghi Macro (F9)")
        rec_cta.setFixedWidth(200)
        rec_cta.clicked.connect(self.record_requested.emit)
        overlay_layout.addWidget(rec_cta, alignment=Qt.AlignmentFlag.AlignCenter)

        open_cta = QPushButton("📂 Mở File (Ctrl+O)")
        open_cta.setFixedWidth(200)
        open_cta.clicked.connect(self.open_file_requested.emit)
        overlay_layout.addWidget(open_cta, alignment=Qt.AlignmentFlag.AlignCenter)

        overlay_layout.addSpacing(8)

        hotkey_label = QLabel("F6=Chạy  F7=Tạm dừng  F8=Dừng hẳn")
        hotkey_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hotkey_label.setStyleSheet("font-size: 9pt; color: #8a8aa8; background: transparent;")
        overlay_layout.addWidget(hotkey_label)

        layout.addWidget(self._empty_overlay)

        # ── Move / Manipulation buttons ──
        btn_layout = QHBoxLayout()

        self._up_btn = QToolButton()
        self._up_btn.setText("⬆ Lên")
        self._up_btn.setFixedHeight(28)
        self._up_btn.setToolTip("Di chuyển lên (Ctrl+↑)")
        self._up_btn.setAccessibleName("Di chuyển action lên")
        self._up_btn.clicked.connect(self.move_up_requested.emit)
        btn_layout.addWidget(self._up_btn)

        self._down_btn = QToolButton()
        self._down_btn.setText("⬇ Xuống")
        self._down_btn.setFixedHeight(28)
        self._down_btn.setToolTip("Di chuyển xuống (Ctrl+↓)")
        self._down_btn.setAccessibleName("Di chuyển action xuống")
        self._down_btn.clicked.connect(self.move_down_requested.emit)
        btn_layout.addWidget(self._down_btn)

        self._dup_btn = QToolButton()
        self._dup_btn.setText("📋 Bản")
        self._dup_btn.setFixedHeight(28)
        self._dup_btn.setToolTip("Nhân bản action (Ctrl+D)")
        self._dup_btn.setAccessibleName("Nhân bản action")
        self._dup_btn.clicked.connect(self.duplicate_requested.emit)
        btn_layout.addWidget(self._dup_btn)

        self._copy_btn = QToolButton()
        self._copy_btn.setText("📄 Chép")
        self._copy_btn.setFixedHeight(28)
        self._copy_btn.setToolTip("Sao chép action (Ctrl+C)")
        self._copy_btn.setAccessibleName("Sao chép action")
        self._copy_btn.clicked.connect(self.copy_requested.emit)
        btn_layout.addWidget(self._copy_btn)

        self._paste_btn = QToolButton()
        self._paste_btn.setText("📥 Dán")
        self._paste_btn.setFixedHeight(28)
        self._paste_btn.setToolTip("Dán action từ clipboard (Ctrl+V)")
        self._paste_btn.setAccessibleName("Dán action")
        self._paste_btn.clicked.connect(self.paste_requested.emit)
        btn_layout.addWidget(self._paste_btn)

        self._del_btn = QToolButton()
        self._del_btn.setText("🗑 Xóa")
        self._del_btn.setFixedHeight(28)
        self._del_btn.setToolTip("Xóa action (Delete)")
        self._del_btn.setAccessibleName("Xóa action")
        self._del_btn.setObjectName("dangerButton")
        self._del_btn.clicked.connect(self.delete_requested.emit)
        btn_layout.addWidget(self._del_btn)

        btn_layout.addStretch()

        # Stats label
        self._stats_label = QLabel("")
        self._stats_label.setObjectName("subtitleLabel")
        btn_layout.addWidget(self._stats_label)

        layout.addLayout(btn_layout)
    def _show_column_menu(self, pos: object) -> None:
        """Show column visibility toggle menu on header right-click."""
        from PyQt6.QtWidgets import QMenu

        menu = QMenu(self)
        header = self._tree.header()
        col_names = ["# (STT)", "✓ (Bật)", "Loại", "Chi tiết", "Delay", "Mô tả", "⏱ Thực tế"]
        for i, name in enumerate(col_names):
            action = menu.addAction(name)
            action.setCheckable(True)
            action.setChecked(not self._tree.isColumnHidden(i))
            action.toggled.connect(
                lambda checked, col=i: self._tree.setColumnHidden(col, not checked)
            )
        menu.exec(header.mapToGlobal(pos))  # type: ignore[arg-type]

    def _on_filter_text_changed(self, text: str) -> None:
        """Update proxy filter and emit signal for external consumers."""
        self._filter_proxy.setFilterFixedString(text.strip())
        self.filter_changed.emit(text)
        # Auto-expand when filtering so matches are visible
        if text.strip():
            self._tree.expandAll()

    def _on_type_filter_changed(self, index: int) -> None:
        """Update proxy type filter when combo box selection changes."""
        type_key = self._type_combo.itemData(index) or ""
        self._filter_proxy.set_type_filter(type_key)
        # Auto-expand when type filtering so all matches are visible
        if type_key:
            self._tree.expandAll()

    @property
    def tree(self) -> QTreeView:
        return self._tree

    @property
    def tree_model(self) -> ActionTreeModel:
        return self._tree_model

    @property
    def filter_proxy(self) -> ActionTreeFilterProxy:
        return self._filter_proxy

    @property
    def filter_edit(self) -> QLineEdit:
        return self._filter_edit

    @property
    def stats_label(self) -> QLabel:
        return self._stats_label

    @property
    def empty_overlay(self) -> QLabel:
        return self._empty_overlay

    # ── Expand/Collapse state persistence ──
    def _set_expand_all(self) -> None:
        """Set mode to expand all and apply."""
        self._expand_mode = "all"
        self._tree.expandAll()

    def _set_collapse_all(self) -> None:
        """Set mode to collapse all and apply."""
        self._expand_mode = "collapsed"
        self._tree.collapseAll()

    def _set_expand_level_1(self) -> None:
        """Set mode to expand level 1 only and apply."""
        self._expand_mode = "level1"
        self._tree.collapseAll()
        self._tree.expandToDepth(0)

    def save_expand_state(self) -> dict[str, bool]:
        """Snapshot which action nodes are expanded (by action ID).
        Recursively saves state for all composite nodes, not just root-level.
        """
        state: dict[str, bool] = {}
        self._save_expand_recursive(QModelIndex(), state)
        return state

    def _save_expand_recursive(self, parent: QModelIndex, state: dict[str, bool]) -> None:
        """Recursively save expand state for all composite nodes."""
        row_count = self._filter_proxy.rowCount(parent)
        for i in range(row_count):
            proxy_idx = self._filter_proxy.index(i, 0, parent)
            if not proxy_idx.isValid():
                continue
            src_idx = self._filter_proxy.mapToSource(proxy_idx)
            node = self._tree_model.node_at(src_idx)
            if node and node.action.is_composite:
                state[node.action.id] = self._tree.isExpanded(proxy_idx)
                # Recurse into children
                self._save_expand_recursive(proxy_idx, state)

    def restore_expand_state(self, state: dict[str, bool]) -> None:
        """Restore expanded nodes after tree rebuild.
        Respects current expand mode: if 'all' mode, always expandAll.
        """
        if self._expand_mode == "all":
            self._tree.expandAll()
            return
        if self._expand_mode == "collapsed":
            self._tree.collapseAll()
            return
        if self._expand_mode == "level1":
            self._tree.collapseAll()
            self._tree.expandToDepth(0)
            return
        # Manual mode: restore per-node state
        if not state:
            self._tree.expandAll()
            return
        self._restore_expand_recursive(QModelIndex(), state)

    def _restore_expand_recursive(self, parent: QModelIndex, state: dict[str, bool]) -> None:
        """Recursively restore expand state for all composite nodes."""
        row_count = self._filter_proxy.rowCount(parent)
        for i in range(row_count):
            proxy_idx = self._filter_proxy.index(i, 0, parent)
            if not proxy_idx.isValid():
                continue
            src_idx = self._filter_proxy.mapToSource(proxy_idx)
            node = self._tree_model.node_at(src_idx)
            if node and node.action.is_composite:
                expanded = state.get(node.action.id, True)  # Default: expanded
                self._tree.setExpanded(proxy_idx, expanded)
                # Recurse into children
                self._restore_expand_recursive(proxy_idx, state)

    def update_breadcrumb(self, node) -> None:
        """P6: Update breadcrumb label based on selected tree node.

        Shows path from root for nested actions, e.g.:
        "📍 Loop (3x) > If score >= 50 > [THEN]"
        Hidden when a root-level action or nothing is selected.
        """
        if node is None or node.parent is None:
            self._breadcrumb_label.setVisible(False)
            return

        # Walk up ancestor chain to build path
        parts: list[str] = []
        cur = node
        while cur is not None:
            label = cur.action.get_display_name()
            # Truncate long labels
            if len(label) > 35:
                label = label[:32] + "..."
            if cur.branch_label:
                label = f"[{cur.branch_label}] {label}"
            parts.insert(0, label)
            cur = cur.parent

        path_text = " › ".join(parts)
        self._breadcrumb_label.setText(f"📍 {path_text}")
        self._breadcrumb_label.setVisible(True)
