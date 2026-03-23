"""
ActionTreeModel — QAbstractItemModel for hierarchical action display.

Provides a tree structure for QTreeView:
  - Root level: flat _actions list
  - Children of composites: action.children (via v3.0 composite interface)
  - Columns: [✓] [Type] [Details] [Delay]

This model is read-write: supports drag-drop reorder and reparenting.
"""

import logging
from typing import Any, Optional

from PyQt6.QtCore import (
    QAbstractItemModel, QModelIndex, Qt, QMimeData,
    QPersistentModelIndex,
)
from PyQt6.QtGui import QIcon

from core.action import Action

logger = logging.getLogger(__name__)

# Column indices
COL_ENABLED = 0
COL_TYPE = 1
COL_DETAILS = 2
COL_DELAY = 3
NUM_COLUMNS = 4

_COLUMN_HEADERS = ["✓", "Loại", "Chi tiết", "Delay"]

# Icons for action types (matches main_window._TYPE_ICONS)
_TYPE_ICONS: dict[str, str] = {
    "mouse_click": "🖱", "mouse_double_click": "🖱",
    "mouse_right_click": "🖱", "mouse_move": "🖱",
    "mouse_drag": "🖱", "mouse_scroll": "🖱",
    "key_press": "⌨", "key_combo": "⌨",
    "type_text": "⌨", "hotkey": "⌨",
    "delay": "⏱",
    "wait_for_image": "🖼", "click_on_image": "🖼",
    "image_exists": "🖼", "take_screenshot": "📸",
    "check_pixel_color": "🎨", "wait_for_color": "🎨",
    "loop_block": "🔁",
    "if_image_found": "❓", "if_pixel_color": "🎯", "if_variable": "📏",
    "set_variable": "📊", "split_string": "✂️",
    "comment": "💬",
    "activate_window": "🖥", "log_to_file": "📝",
    "read_clipboard": "📋", "read_file_line": "📂",
    "write_to_file": "💾",
    "secure_type_text": "🔒", "run_macro": "▶️", "capture_text": "🔍",
}


class _TreeNode:
    """Internal tree node wrapping an Action.

    Maintains parent/children relationships for efficient QModelIndex lookup.
    """
    __slots__ = ('action', 'parent', 'children', 'row', 'branch_label')

    def __init__(self, action: Action, parent: Optional['_TreeNode'] = None,
                 row: int = 0, branch_label: str = "") -> None:
        self.action = action
        self.parent = parent
        self.row = row  # row within parent's children list
        self.branch_label = branch_label  # "THEN", "ELSE", or ""
        self.children: list['_TreeNode'] = []

    def child_count(self) -> int:
        return len(self.children)


class ActionTreeModel(QAbstractItemModel):
    """Tree model that presents Action hierarchy for QTreeView.

    Usage:
        model = ActionTreeModel(actions_list)
        tree_view.setModel(model)

    When actions change externally, call rebuild() to re-sync.
    """

    def __init__(self, actions: list[Action],
                 parent: Any = None) -> None:
        super().__init__(parent)
        self._actions = actions  # Reference to MainWindow._actions
        self._root_nodes: list[_TreeNode] = []
        self._rebuild_tree()

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def rebuild(self) -> None:
        """Rebuild the tree structure from the action list."""
        self.beginResetModel()
        self._rebuild_tree()
        self.endResetModel()

    def action_at(self, index: QModelIndex) -> Action | None:
        """Get the Action object for a given model index."""
        if not index.isValid():
            return None
        node: _TreeNode = index.internalPointer()  # type: ignore
        return node.action if node else None

    def node_at(self, index: QModelIndex) -> _TreeNode | None:
        """Get the internal tree node for a model index."""
        if not index.isValid():
            return None
        return index.internalPointer()  # type: ignore

    # ------------------------------------------------------------------ #
    # Internal tree construction
    # ------------------------------------------------------------------ #
    def _rebuild_tree(self) -> None:
        """Build tree nodes from the action list."""
        self._root_nodes = []
        for i, action in enumerate(self._actions):
            node = self._build_node(action, parent=None, row=i)
            self._root_nodes.append(node)

    def _build_node(self, action: Action,
                    parent: _TreeNode | None,
                    row: int,
                    branch_label: str = "") -> _TreeNode:
        """Recursively build a tree node from an action."""
        node = _TreeNode(action, parent=parent, row=row,
                         branch_label=branch_label)

        if action.is_composite:
            # For If* actions, show THEN/ELSE branches as separate groups
            if action.has_branches:
                for j, child in enumerate(action.then_children):
                    child_node = self._build_node(
                        child, parent=node, row=j, branch_label="THEN"
                    )
                    node.children.append(child_node)
                for j, child in enumerate(action.else_children):
                    child_node = self._build_node(
                        child, parent=node,
                        row=len(action.then_children) + j,
                        branch_label="ELSE"
                    )
                    node.children.append(child_node)
            else:
                # LoopBlock: direct children
                for j, child in enumerate(action.children):
                    child_node = self._build_node(
                        child, parent=node, row=j
                    )
                    node.children.append(child_node)
        return node

    # ------------------------------------------------------------------ #
    # QAbstractItemModel required overrides
    # ------------------------------------------------------------------ #
    def index(self, row: int, column: int,
              parent: QModelIndex = QModelIndex()) -> QModelIndex:
        if not self.hasIndex(row, column, parent):
            return QModelIndex()

        if not parent.isValid():
            # Root level
            if 0 <= row < len(self._root_nodes):
                return self.createIndex(row, column, self._root_nodes[row])
            return QModelIndex()

        parent_node: _TreeNode = parent.internalPointer()  # type: ignore
        if 0 <= row < parent_node.child_count():
            return self.createIndex(row, column, parent_node.children[row])
        return QModelIndex()

    def parent(self, index: QModelIndex) -> QModelIndex:  # type: ignore[override]
        if not index.isValid():
            return QModelIndex()

        node: _TreeNode = index.internalPointer()  # type: ignore
        if node is None or node.parent is None:
            return QModelIndex()

        parent_node = node.parent
        return self.createIndex(parent_node.row, 0, parent_node)

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.column() > 0:
            return 0

        if not parent.isValid():
            return len(self._root_nodes)

        node: _TreeNode = parent.internalPointer()  # type: ignore
        return node.child_count() if node else 0

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return NUM_COLUMNS

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
            return None

        node: _TreeNode = index.internalPointer()  # type: ignore
        if node is None:
            return None

        action = node.action
        col = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            if col == COL_ENABLED:
                return "✓" if action.enabled else ""
            elif col == COL_TYPE:
                prefix = _TYPE_ICONS.get(action.ACTION_TYPE, "")
                branch = f"[{node.branch_label}] " if node.branch_label else ""
                return f"{branch}{prefix} {action.ACTION_TYPE}"
            elif col == COL_DETAILS:
                return action.get_display_name()
            elif col == COL_DELAY:
                return f"{action.delay_after}ms" if action.delay_after > 0 else ""

        elif role == Qt.ItemDataRole.CheckStateRole:
            if col == COL_ENABLED:
                return (Qt.CheckState.Checked if action.enabled
                        else Qt.CheckState.Unchecked)

        elif role == Qt.ItemDataRole.ToolTipRole:
            if col == COL_TYPE and action.is_composite:
                n = len(action.children)
                return f"Composite: {n} child action{'s' if n != 1 else ''}"

        elif role == Qt.ItemDataRole.ForegroundRole:
            if not action.enabled:
                from PyQt6.QtGui import QColor
                return QColor(120, 120, 140)
            if node.branch_label == "ELSE":
                from PyQt6.QtGui import QColor
                return QColor(255, 160, 100)  # Orange for ELSE branch

        elif role == Qt.ItemDataRole.BackgroundRole:
            if action.is_composite:
                from PyQt6.QtGui import QColor
                return QColor(40, 42, 70, 50)  # Subtle highlight for composites

        return None

    def headerData(self, section: int, orientation: Qt.Orientation,
                   role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if orientation == Qt.Orientation.Horizontal and \
                role == Qt.ItemDataRole.DisplayRole:
            if 0 <= section < len(_COLUMN_HEADERS):
                return _COLUMN_HEADERS[section]
        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        if not index.isValid():
            return Qt.ItemFlag.ItemIsDropEnabled  # Allow drops on root

        default = (Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
                   | Qt.ItemFlag.ItemIsDragEnabled)

        node: _TreeNode = index.internalPointer()  # type: ignore
        if node and node.action.is_composite:
            default |= Qt.ItemFlag.ItemIsDropEnabled

        if index.column() == COL_ENABLED:
            default |= Qt.ItemFlag.ItemIsUserCheckable

        return default

    # ------------------------------------------------------------------ #
    # Editable: toggle enabled via checkbox
    # ------------------------------------------------------------------ #
    def setData(self, index: QModelIndex, value: Any,
                role: int = Qt.ItemDataRole.EditRole) -> bool:
        if not index.isValid():
            return False

        if role == Qt.ItemDataRole.CheckStateRole and \
                index.column() == COL_ENABLED:
            node: _TreeNode = index.internalPointer()  # type: ignore
            if node:
                checked = (value == Qt.CheckState.Checked.value
                           or value == Qt.CheckState.Checked)
                node.action.enabled = checked
                self.dataChanged.emit(index, index, [role])
                return True
        return False

    # ------------------------------------------------------------------ #
    # Drag & Drop support
    # ------------------------------------------------------------------ #
    def supportedDropActions(self) -> Qt.DropAction:
        return Qt.DropAction.MoveAction

    def mimeTypes(self) -> list[str]:
        return ["application/x-action-tree-rows"]

    def mimeData(self, indexes: list[QModelIndex]) -> QMimeData:
        mime = QMimeData()
        # Store row paths for each selected item
        rows = []
        for idx in indexes:
            if idx.column() == 0:  # Only process once per row
                path = self._index_path(idx)
                rows.append(path)
        import json
        mime.setData("application/x-action-tree-rows",
                     json.dumps(rows).encode())
        return mime

    def _index_path(self, index: QModelIndex) -> list[int]:
        """Get the path of row indices from root to this index."""
        path: list[int] = []
        current = index
        while current.isValid():
            path.insert(0, current.row())
            current = current.parent()
        return path

    # ------------------------------------------------------------------ #
    # Utility
    # ------------------------------------------------------------------ #
    def get_root_actions(self) -> list[Action]:
        """Return the root-level action list."""
        return self._actions
