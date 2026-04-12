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
    QAbstractItemModel,
    QMimeData,
    QModelIndex,
    QSortFilterProxyModel,
    Qt,
)

from core.action import Action

logger = logging.getLogger(__name__)

# Column indices
COL_INDEX = 0
COL_ENABLED = 1
COL_TYPE = 2
COL_DETAILS = 3
COL_DELAY = 4
COL_DESC = 5
COL_DURATION = 6
NUM_COLUMNS = 7

_COLUMN_HEADERS = ["#", "✓", "Loại", "Chi tiết", "Delay", "Mô tả", "⏱ Thực tế"]

from gui.constants import COLOR_PRESETS as _COLOR_PRESETS
from gui.constants import TYPE_ICONS as _TYPE_ICONS


class _TreeNode:
    """Internal tree node wrapping an Action.

    Maintains parent/children relationships for efficient QModelIndex lookup.
    """

    __slots__ = ("action", "parent", "children", "row", "branch_label")

    def __init__(
        self, action: Action, parent: Optional["_TreeNode"] = None, row: int = 0, branch_label: str = ""
    ) -> None:
        self.action = action
        self.parent = parent
        self.row = row  # row within parent's children list
        self.branch_label = branch_label  # "THEN", "ELSE", or ""
        self.children: list["_TreeNode"] = []

    def child_count(self) -> int:
        return len(self.children)


class ActionTreeModel(QAbstractItemModel):
    """Tree model that presents Action hierarchy for QTreeView.

    Usage:
        model = ActionTreeModel(actions_list)
        tree_view.setModel(model)

    When actions change externally, call rebuild() to re-sync.
    """

    def __init__(self, actions: list[Action], parent: Any = None) -> None:
        super().__init__(parent)
        self._actions = actions  # Reference to MainWindow._actions
        self._root_nodes: list[_TreeNode] = []
        self._executing_row: int = -1  # Currently executing root-level row
        self._error_row: int = -1  # Row that failed (error highlight)
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

    def set_executing_row(self, row: int) -> None:
        """Highlight the currently executing root-level action.
        
        Pass -1 to clear the highlight (e.g. when engine stops).
        Only repaints the old and new rows for efficiency.
        """
        old = self._executing_row
        self._executing_row = row
        # Repaint old row
        if 0 <= old < len(self._root_nodes):
            tl = self.index(old, 0)
            br = self.index(old, NUM_COLUMNS - 1)
            self.dataChanged.emit(tl, br)
        # Repaint new row
        if 0 <= row < len(self._root_nodes):
            tl = self.index(row, 0)
            br = self.index(row, NUM_COLUMNS - 1)
            self.dataChanged.emit(tl, br)

    def set_error_row(self, row: int) -> None:
        """Highlight a row as failed (red). Pass -1 to clear."""
        old = self._error_row
        self._error_row = row
        if 0 <= old < len(self._root_nodes):
            tl = self.index(old, 0)
            br = self.index(old, NUM_COLUMNS - 1)
            self.dataChanged.emit(tl, br)
        if 0 <= row < len(self._root_nodes):
            tl = self.index(row, 0)
            br = self.index(row, NUM_COLUMNS - 1)
            self.dataChanged.emit(tl, br)

    # ------------------------------------------------------------------ #
    # Internal tree construction
    # ------------------------------------------------------------------ #
    def _rebuild_tree(self) -> None:
        """Build tree nodes from the action list."""
        self._root_nodes = []
        for i, action in enumerate(self._actions):
            node = self._build_node(action, parent=None, row=i)
            self._root_nodes.append(node)

    def _build_node(self, action: Action, parent: _TreeNode | None, row: int, branch_label: str = "") -> _TreeNode:
        """Recursively build a tree node from an action."""
        node = _TreeNode(action, parent=parent, row=row, branch_label=branch_label)

        if action.is_composite:
            # For If* actions, show THEN/ELSE branches as separate groups
            if action.has_branches:
                if action.then_children:
                    for j, child in enumerate(action.then_children):
                        child_node = self._build_node(child, parent=node, row=j, branch_label="THEN")
                        node.children.append(child_node)
                else:
                    # Placeholder for empty THEN branch
                    placeholder = _TreeNode(None, parent=node, row=0, branch_label="THEN_EMPTY")
                    node.children.append(placeholder)

                offset = len(node.children)
                if action.else_children:
                    for j, child in enumerate(action.else_children):
                        child_node = self._build_node(
                            child, parent=node, row=offset + j, branch_label="ELSE"
                        )
                        node.children.append(child_node)
                else:
                    # Placeholder for empty ELSE branch
                    placeholder = _TreeNode(None, parent=node, row=offset, branch_label="ELSE_EMPTY")
                    node.children.append(placeholder)
            else:
                # LoopBlock/Group: direct children
                if action.children:
                    for j, child in enumerate(action.children):
                        child_node = self._build_node(child, parent=node, row=j)
                        node.children.append(child_node)
                else:
                    # Placeholder for empty children
                    placeholder = _TreeNode(None, parent=node, row=0, branch_label="CHILDREN_EMPTY")
                    node.children.append(placeholder)
        return node

    # ------------------------------------------------------------------ #
    # QAbstractItemModel required overrides
    # ------------------------------------------------------------------ #
    def index(self, row: int, column: int, parent: QModelIndex = QModelIndex()) -> QModelIndex:
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

        # ── Placeholder nodes (empty branch hints) ──
        if action is None:
            if role == Qt.ItemDataRole.DisplayRole:
                if col == COL_TYPE:
                    if "THEN" in node.branch_label:
                        return "[THEN] 📭 (trống — right-click hoặc kéo action vào đây)"
                    elif "ELSE" in node.branch_label:
                        return "[ELSE] 📭 (trống — right-click hoặc kéo action vào đây)"
                    else:
                        return "📭 (trống — right-click hoặc kéo action vào đây)"
                return ""
            elif role == Qt.ItemDataRole.ForegroundRole:
                from PyQt6.QtGui import QColor
                return QColor(100, 100, 130)  # Muted gray-purple
            elif role == Qt.ItemDataRole.FontRole:
                from PyQt6.QtGui import QFont
                font = QFont()
                font.setItalic(True)
                return font
            elif role == Qt.ItemDataRole.BackgroundRole:
                from PyQt6.QtGui import QColor
                return QColor(45, 45, 65, 30)  # Very subtle hint bg
            return None

        if role == Qt.ItemDataRole.DisplayRole:
            if col == COL_INDEX:
                # P7: Deep hierarchical numbering: 1, 1.1, 1.1.1, etc.
                bm = "🔖" if getattr(action, "bookmarked", False) else ""
                parts: list[int] = []
                cur = node
                while cur is not None:
                    parts.insert(0, cur.row + 1)
                    cur = cur.parent
                return ".".join(str(p) for p in parts) + bm
            elif col == COL_ENABLED:
                return "✓" if action.enabled else ""
            elif col == COL_TYPE:
                prefix = _TYPE_ICONS.get(action.ACTION_TYPE, "")
                branch = f"[{node.branch_label}] " if node.branch_label else ""
                return f"{branch}{prefix} {action.ACTION_TYPE}"
            elif col == COL_DETAILS:
                return action.get_display_name()
            elif col == COL_DELAY:
                return f"{action.delay_after}ms" if action.delay_after > 0 else ""
            elif col == COL_DESC:
                return action.description or ""
            elif col == COL_DURATION:
                dur = getattr(action, "last_duration_ms", 0)
                if dur > 0:
                    if dur >= 1000:
                        return f"{dur / 1000:.1f}s"
                    return f"{dur}ms"
                return ""

        elif role == Qt.ItemDataRole.TextAlignmentRole:
            if col in (COL_INDEX, COL_DELAY, COL_DURATION):
                return Qt.AlignmentFlag.AlignCenter

        elif role == Qt.ItemDataRole.CheckStateRole:
            if col == COL_ENABLED:
                return Qt.CheckState.Checked if action.enabled else Qt.CheckState.Unchecked

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
            # Error highlight (highest priority — red)
            if node.parent is None and node.row == self._error_row:
                from PyQt6.QtGui import QColor

                return QColor(231, 76, 60, 80)  # Red for error
            # Execution highlight
            if node.parent is None and node.row == self._executing_row:
                from PyQt6.QtGui import QColor

                return QColor(39, 174, 96, 80)  # Green, stronger alpha
            # Per-action color coding
            if hasattr(action, 'color') and action.color and action.color in _COLOR_PRESETS:
                from PyQt6.QtGui import QColor

                r, g, b, a = _COLOR_PRESETS[action.color]
                return QColor(r, g, b, a)
            if action.is_composite:
                from PyQt6.QtGui import QColor

                return QColor(40, 42, 70, 50)  # Subtle highlight for composites

        return None

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            if 0 <= section < len(_COLUMN_HEADERS):
                return _COLUMN_HEADERS[section]
        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        if not index.isValid():
            return Qt.ItemFlag.ItemIsDropEnabled  # Allow drops on root

        node: _TreeNode = index.internalPointer()  # type: ignore

        # Placeholder nodes: enabled + droppable only (not selectable/draggable)
        if node and node.action is None:
            return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsDropEnabled

        default = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsDragEnabled

        if node and node.action.is_composite:
            default |= Qt.ItemFlag.ItemIsDropEnabled

        if index.column() == COL_ENABLED:
            default |= Qt.ItemFlag.ItemIsUserCheckable

        return default

    # ------------------------------------------------------------------ #
    # Editable: toggle enabled via checkbox
    # ------------------------------------------------------------------ #
    def setData(self, index: QModelIndex, value: Any, role: int = Qt.ItemDataRole.EditRole) -> bool:
        if not index.isValid():
            return False

        if role == Qt.ItemDataRole.CheckStateRole and index.column() == COL_ENABLED:
            node: _TreeNode = index.internalPointer()  # type: ignore
            if node and node.action is not None:
                checked = value == Qt.CheckState.Checked.value or value == Qt.CheckState.Checked
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

    def mimeData(self, indexes: list[QModelIndex]) -> QMimeData:  # type: ignore[override]
        mime = QMimeData()
        # Store row paths for each selected item
        rows = []
        for idx in indexes:
            if idx.column() == 0:  # Only process once per row
                path = self._index_path(idx)
                rows.append(path)
        import json

        mime.setData("application/x-action-tree-rows", json.dumps(rows).encode())
        return mime

    def _index_path(self, index: QModelIndex) -> list[int]:
        """Get the path of row indices from root to this index."""
        path: list[int] = []
        current = index
        while current.isValid():
            path.insert(0, current.row())
            current = current.parent()
        return path

    def dropMimeData(
        self, data: QMimeData, action: Qt.DropAction,
        row: int, column: int, parent: QModelIndex,
    ) -> bool:
        """Handle drop: move actions within tree (reorder + reparent).

        P1: Reorder within same level (root or inside composite)
        P3: Move action into/out of composite (reparent)
        P10: Multi-select drag (multiple source paths)
        """
        if not data.hasFormat("application/x-action-tree-rows"):
            return False

        import json
        paths = json.loads(bytes(data.data("application/x-action-tree-rows")).decode())
        if not paths:
            return False

        # Resolve target container
        if parent.isValid():
            target_node = self.node_at(parent)
            if target_node is None:
                return False
            target_action = target_node.action

            # Drop on placeholder → reroute to parent composite's branch
            if target_action is None:
                placeholder_label = target_node.branch_label  # THEN_EMPTY / ELSE_EMPTY / CHILDREN_EMPTY
                parent_of_placeholder = target_node.parent
                if parent_of_placeholder is None or parent_of_placeholder.action is None:
                    return False
                target_action = parent_of_placeholder.action
                if not target_action.is_composite:
                    return False
                # Override branch determination from placeholder label
                if "THEN" in placeholder_label:
                    row = 0  # insert at position 0 in THEN branch
                elif "ELSE" in placeholder_label:
                    row = len(target_action.then_children)  # after THEN children
                else:
                    row = 0  # children branch position 0

            if not target_action.is_composite:
                return False

            # Determine which child list to drop into
            if target_action.has_branches:
                # For If-actions: use THEN branch by default;
                # if dropping below THEN children count, use ELSE
                then_count = len(target_action.then_children)
                if row >= 0 and row > then_count:
                    target_list = list(target_action.else_children)
                    branch = "else"
                    adj_row = row - then_count if row >= 0 else len(target_list)
                else:
                    target_list = list(target_action.then_children)
                    branch = "then"
                    adj_row = row if row >= 0 else len(target_list)
            else:
                # Loop/Group: direct children
                target_list = list(target_action.children)
                branch = "children"
                adj_row = row if row >= 0 else len(target_list)
        else:
            # Drop at root level
            target_list = self._actions
            target_action = None
            branch = "root"
            adj_row = row if row >= 0 else len(target_list)

        # Resolve source actions (collect before removing)
        sources = []
        for path in paths:
            action_obj = self._resolve_action_at_path(path)
            if action_obj is None:
                continue
            # Safety: prevent dropping into own descendant (circular)
            if target_action and self._is_descendant(action_obj, target_action):
                logger.warning("D&D blocked: cannot drop parent into own child")
                return False
            sources.append((path, action_obj))

        if not sources:
            return False

        # Remove sources in reverse path order to avoid index shifts
        for path, _ in sorted(sources, key=lambda s: s[0], reverse=True):
            self._remove_action_at_path(path)

        # Recalculate target list reference (may have changed after removals)
        if branch == "root":
            target_list = self._actions
        elif target_action is not None:
            if branch == "then":
                target_list = list(target_action.then_children)
            elif branch == "else":
                target_list = list(target_action.else_children)
            else:
                target_list = list(target_action.children)

        # Clamp insert position
        adj_row = max(0, min(adj_row, len(target_list)))

        # Insert removed actions at target position
        for i, (_, action_obj) in enumerate(sources):
            if branch == "root":
                self._actions.insert(adj_row + i, action_obj)
            elif branch == "then" and target_action is not None:
                children = list(target_action.then_children)
                children.insert(adj_row + i, action_obj)
                target_action.then_children = children
            elif branch == "else" and target_action is not None:
                children = list(target_action.else_children)
                children.insert(adj_row + i, action_obj)
                target_action.else_children = children
            elif target_action is not None:
                children = list(target_action.children)
                children.insert(adj_row + i, action_obj)
                target_action.children = children

        self.rebuild()
        logger.info("D&D: moved %d action(s) to %s row %d", len(sources), branch, adj_row)
        return True

    def _resolve_action_at_path(self, path: list[int]) -> Action | None:
        """Resolve an action object from a tree path [root_idx, child_idx, ...]."""
        if not path:
            return None
        idx = path[0]
        if idx < 0 or idx >= len(self._actions):
            return None
        action = self._actions[idx]
        for level in path[1:]:
            children = []
            if action.is_composite:
                if action.has_branches:
                    children = list(action.then_children) + list(action.else_children)
                else:
                    children = list(action.children)
            if level < 0 or level >= len(children):
                return None
            action = children[level]
        return action

    def _remove_action_at_path(self, path: list[int]) -> bool:
        """Remove an action from the tree at the given path."""
        if not path:
            return False
        if len(path) == 1:
            idx = path[0]
            if 0 <= idx < len(self._actions):
                self._actions.pop(idx)
                return True
            return False

        # Navigate to parent
        parent_action = self._actions[path[0]]
        for level in path[1:-1]:
            children = []
            if parent_action.is_composite:
                if parent_action.has_branches:
                    children = list(parent_action.then_children) + list(parent_action.else_children)
                else:
                    children = list(parent_action.children)
            if level < 0 or level >= len(children):
                return False
            parent_action = children[level]

        # Remove from parent
        child_idx = path[-1]
        if parent_action.has_branches:
            then_list = list(parent_action.then_children)
            if child_idx < len(then_list):
                then_list.pop(child_idx)
                parent_action.then_children = then_list
            else:
                else_idx = child_idx - len(then_list)
                else_list = list(parent_action.else_children)
                if 0 <= else_idx < len(else_list):
                    else_list.pop(else_idx)
                    parent_action.else_children = else_list
        else:
            children = list(parent_action.children)
            if 0 <= child_idx < len(children):
                children.pop(child_idx)
                parent_action.children = children
        return True

    def _is_descendant(self, potential_ancestor: Action, target: Action) -> bool:
        """Check if target is nested inside potential_ancestor (prevents circular drops)."""
        if potential_ancestor is target:
            return True
        if not potential_ancestor.is_composite:
            return False
        children = []
        if potential_ancestor.has_branches:
            children = list(potential_ancestor.then_children) + list(potential_ancestor.else_children)
        else:
            children = list(potential_ancestor.children)
        for child in children:
            if self._is_descendant(child, target):
                return True
        return False

    # ------------------------------------------------------------------ #
    # Utility
    # ------------------------------------------------------------------ #
    def get_root_actions(self) -> list[Action]:
        """Return the root-level action list."""
        return self._actions


class ActionTreeFilterProxy(QSortFilterProxyModel):
    """Recursive filter proxy for the action tree.

    Shows a row if its name/description matches OR any descendant matches.
    Parent nodes of matching children stay visible for context.
    Supports optional action-type filtering via set_type_filter().
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._type_filter: str = ""  # Empty = show all types

    def set_type_filter(self, action_type: str) -> None:
        """Filter by ACTION_TYPE. Pass empty string to show all."""
        self._type_filter = action_type
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        model = self.sourceModel()
        if model is None:
            return True

        # Get the node to access action data
        idx = model.index(source_row, 0, source_parent)
        node = model.node_at(idx) if hasattr(model, "node_at") else None

        # Type filter check (applied before text filter)
        if self._type_filter and node:
            atype = getattr(node.action, "ACTION_TYPE", "")
            if atype != self._type_filter:
                # Still show if any child matches the type
                child_count = model.rowCount(idx)
                has_matching_child = False
                for i in range(child_count):
                    if self.filterAcceptsRow(i, idx):
                        has_matching_child = True
                        break
                if not has_matching_child:
                    return False

        pattern = self.filterRegularExpression().pattern().lower()
        if not pattern:
            return True  # No text filter → show all

        # Check this row's Details and Description columns
        details_idx = model.index(source_row, COL_DETAILS, source_parent)
        desc_idx = model.index(source_row, COL_DESC, source_parent)
        type_idx = model.index(source_row, COL_TYPE, source_parent)

        details = (model.data(details_idx) or "").lower()
        desc = (model.data(desc_idx) or "").lower()
        type_text = (model.data(type_idx) or "").lower()

        if pattern in details or pattern in desc or pattern in type_text:
            return True

        # Recursively check children — if any child matches, show this parent
        child_count = model.rowCount(model.index(source_row, 0, source_parent))
        for i in range(child_count):
            if self.filterAcceptsRow(i, model.index(source_row, 0, source_parent)):
                return True

        return False
