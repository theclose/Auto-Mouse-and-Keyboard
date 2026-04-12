"""
Sprint 1: ActionTreeModel Tests — v3.0 tree model coverage.

Run: python -m pytest tests/test_action_tree_model.py -v
"""

import os
import sys
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtCore import QModelIndex, Qt
from PyQt6.QtWidgets import QApplication

_app = QApplication.instance() or QApplication([])

# Force-register all action types
import core.action  # noqa: F401
import core.scheduler  # noqa: F401
import modules.image  # noqa: F401
import modules.keyboard  # noqa: F401
import modules.mouse  # noqa: F401
import modules.pixel  # noqa: F401
from gui.action_tree_model import (
    COL_DELAY,
    COL_DETAILS,
    COL_ENABLED,
    COL_TYPE,
    NUM_COLUMNS,
    ActionTreeModel,
)

# ============================================================
# Helpers
# ============================================================

def _delay(ms: int = 100) -> Any:
    return core.action.DelayAction(duration_ms=ms)


def _loop(n: int, children: list | None = None) -> Any:
    loop = core.scheduler.LoopBlock(iterations=n)
    for c in (children or []):
        loop.add_action(c)
    return loop


def _if_image(then: list | None = None, else_: list | None = None) -> Any:
    cond = core.scheduler.IfImageFound(image_path="test.png")
    for a in (then or []):
        cond.add_then_action(a)
    for a in (else_ or []):
        cond.add_else_action(a)
    return cond


# ============================================================
# 1. Empty model
# ============================================================

class TestEmptyModel:
    def test_empty_actions(self) -> None:
        model = ActionTreeModel([])
        assert model.rowCount() == 0
        assert model.columnCount() == NUM_COLUMNS

    def test_invalid_index_returns_none(self) -> None:
        model = ActionTreeModel([])
        assert model.action_at(QModelIndex()) is None
        assert model.node_at(QModelIndex()) is None


# ============================================================
# 2. Flat actions
# ============================================================

class TestFlatActions:
    def test_row_count_matches_actions(self) -> None:
        actions = [_delay(i) for i in range(5)]
        model = ActionTreeModel(actions)
        assert model.rowCount() == 5

    def test_root_has_no_parent(self) -> None:
        model = ActionTreeModel([_delay()])
        idx = model.index(0, 0)
        assert idx.isValid()
        parent = model.parent(idx)
        assert not parent.isValid()

    def test_action_at_returns_correct(self) -> None:
        a1, a2 = _delay(100), _delay(200)
        model = ActionTreeModel([a1, a2])
        idx0 = model.index(0, 0)
        idx1 = model.index(1, 0)
        assert model.action_at(idx0) is a1
        assert model.action_at(idx1) is a2

    def test_display_data_enabled(self) -> None:
        model = ActionTreeModel([_delay(100)])
        idx = model.index(0, COL_ENABLED)
        assert model.data(idx, Qt.ItemDataRole.DisplayRole) == "✓"

    def test_display_data_disabled(self) -> None:
        d = _delay(100)
        d.enabled = False
        model = ActionTreeModel([d])
        idx = model.index(0, COL_ENABLED)
        assert model.data(idx, Qt.ItemDataRole.DisplayRole) == ""

    def test_display_data_type_icon(self) -> None:
        model = ActionTreeModel([_delay(100)])
        idx = model.index(0, COL_TYPE)
        text = model.data(idx, Qt.ItemDataRole.DisplayRole)
        assert "⏱" in text  # delay icon
        assert "delay" in text

    def test_display_data_details(self) -> None:
        d = _delay(500)
        model = ActionTreeModel([d])
        idx = model.index(0, COL_DETAILS)
        text = model.data(idx, Qt.ItemDataRole.DisplayRole)
        assert "500" in text

    def test_display_data_delay_column(self) -> None:
        d = _delay(100)
        d.delay_after = 50
        model = ActionTreeModel([d])
        idx = model.index(0, COL_DELAY)
        assert model.data(idx, Qt.ItemDataRole.DisplayRole) == "50ms"

    def test_delay_column_empty_when_zero(self) -> None:
        d = _delay(100)
        d.delay_after = 0
        model = ActionTreeModel([d])
        idx = model.index(0, COL_DELAY)
        assert model.data(idx, Qt.ItemDataRole.DisplayRole) == ""


# ============================================================
# 3. Composite: LoopBlock with children
# ============================================================

class TestLoopBlockTree:
    def test_loop_has_children(self) -> None:
        loop = _loop(3, [_delay(1), _delay(2)])
        model = ActionTreeModel([loop])
        assert model.rowCount() == 1  # 1 root
        root_idx = model.index(0, 0)
        assert model.rowCount(root_idx) == 2  # 2 children

    def test_child_parent_link(self) -> None:
        loop = _loop(3, [_delay(1)])
        model = ActionTreeModel([loop])
        root_idx = model.index(0, 0)
        child_idx = model.index(0, 0, root_idx)
        assert child_idx.isValid()
        parent = model.parent(child_idx)
        assert parent.isValid()
        assert parent.row() == 0

    def test_child_action_at(self) -> None:
        d = _delay(42)
        loop = _loop(3, [d])
        model = ActionTreeModel([loop])
        root_idx = model.index(0, 0)
        child_idx = model.index(0, 0, root_idx)
        assert model.action_at(child_idx) is d

    def test_nested_loop(self) -> None:
        """Loop inside loop: 2 levels deep."""
        inner = _loop(2, [_delay(1)])
        outer = _loop(3, [inner])
        model = ActionTreeModel([outer])
        # Root → outer
        root_idx = model.index(0, 0)
        assert model.rowCount(root_idx) == 1  # 1 child (inner loop)
        # inner → delay
        inner_idx = model.index(0, 0, root_idx)
        assert model.rowCount(inner_idx) == 1


# ============================================================
# 4. Composite: IfImageFound with THEN/ELSE
# ============================================================

class TestIfImageTree:
    def test_then_else_children(self) -> None:
        then_d = _delay(1)
        else_d = _delay(2)
        cond = _if_image(then=[then_d], else_=[else_d])
        model = ActionTreeModel([cond])
        root_idx = model.index(0, 0)
        # Should have 2 children: THEN + ELSE
        assert model.rowCount(root_idx) == 2

    def test_branch_labels(self) -> None:
        cond = _if_image(then=[_delay(1)], else_=[_delay(2)])
        model = ActionTreeModel([cond])
        root_idx = model.index(0, 0)
        then_idx = model.index(0, COL_TYPE, root_idx)
        else_idx = model.index(1, COL_TYPE, root_idx)
        then_text = model.data(then_idx, Qt.ItemDataRole.DisplayRole)
        else_text = model.data(else_idx, Qt.ItemDataRole.DisplayRole)
        assert "[THEN]" in then_text
        assert "[ELSE]" in else_text


# ============================================================
# 5. rebuild()
# ============================================================

class TestRebuild:
    def test_rebuild_updates_rows(self) -> None:
        actions: list = [_delay(1)]
        model = ActionTreeModel(actions)
        assert model.rowCount() == 1
        actions.append(_delay(2))
        model.rebuild()
        assert model.rowCount() == 2

    def test_rebuild_empty_to_populated(self) -> None:
        actions: list = []
        model = ActionTreeModel(actions)
        assert model.rowCount() == 0
        actions.extend([_delay(1), _delay(2), _delay(3)])
        model.rebuild()
        assert model.rowCount() == 3


# ============================================================
# 6. setData — toggle enabled
# ============================================================

class TestSetData:
    def test_toggle_enabled_via_setdata(self) -> None:
        d = _delay(100)
        assert d.enabled is True
        model = ActionTreeModel([d])
        idx = model.index(0, COL_ENABLED)
        model.setData(idx, Qt.CheckState.Unchecked,
                       Qt.ItemDataRole.CheckStateRole)
        assert d.enabled is False

    def test_setdata_invalid_index(self) -> None:
        model = ActionTreeModel([_delay()])
        result = model.setData(QModelIndex(), True)
        assert result is False


# ============================================================
# 7. flags
# ============================================================

class TestFlags:
    def test_composite_is_droppable(self) -> None:
        loop = _loop(3, [_delay(1)])
        model = ActionTreeModel([loop])
        idx = model.index(0, 0)
        flags = model.flags(idx)
        assert flags & Qt.ItemFlag.ItemIsDropEnabled

    def test_leaf_is_draggable(self) -> None:
        model = ActionTreeModel([_delay()])
        idx = model.index(0, 0)
        flags = model.flags(idx)
        assert flags & Qt.ItemFlag.ItemIsDragEnabled

    def test_enabled_column_is_checkable(self) -> None:
        model = ActionTreeModel([_delay()])
        idx = model.index(0, COL_ENABLED)
        flags = model.flags(idx)
        assert flags & Qt.ItemFlag.ItemIsUserCheckable


# ============================================================
# 8. Headers
# ============================================================

class TestHeaders:
    def test_column_headers(self) -> None:
        model = ActionTreeModel([])
        h0 = model.headerData(0, Qt.Orientation.Horizontal)
        h1 = model.headerData(1, Qt.Orientation.Horizontal)
        assert h0 == "#"
        assert h1 == "✓"

    def test_invalid_section_returns_none(self) -> None:
        model = ActionTreeModel([])
        assert model.headerData(99, Qt.Orientation.Horizontal) is None


# ============================================================
# 9. Tooltip and color roles
# ============================================================

class TestRoles:
    def test_composite_tooltip(self) -> None:
        loop = _loop(3, [_delay(1), _delay(2)])
        model = ActionTreeModel([loop])
        idx = model.index(0, COL_TYPE)
        tip = model.data(idx, Qt.ItemDataRole.ToolTipRole)
        assert "2" in tip  # 2 children
        assert "Composite" in tip

    def test_disabled_foreground_dim(self) -> None:
        d = _delay(100)
        d.enabled = False
        model = ActionTreeModel([d])
        idx = model.index(0, COL_TYPE)
        color = model.data(idx, Qt.ItemDataRole.ForegroundRole)
        assert color is not None
        assert color.red() == 120  # dim grey

    def test_composite_background(self) -> None:
        loop = _loop(3)
        model = ActionTreeModel([loop])
        idx = model.index(0, COL_TYPE)
        bg = model.data(idx, Qt.ItemDataRole.BackgroundRole)
        assert bg is not None


# ============================================================
# 10. get_root_actions
# ============================================================

class TestGetRootActions:
    def test_returns_original_list(self) -> None:
        actions = [_delay(1), _delay(2)]
        model = ActionTreeModel(actions)
        assert model.get_root_actions() is actions

    def test_oob_index_returns_invalid(self) -> None:
        model = ActionTreeModel([_delay()])
        idx = model.index(99, 0)
        assert not idx.isValid()
