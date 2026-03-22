"""
Undo/Redo commands for the action list, using Qt's QUndoCommand.

Each command stores the minimal data needed to reverse itself.
All commands operate on a shared list[Action] reference (MainWindow._actions).
Table refresh is handled externally via QUndoStack.indexChanged signal.
"""

from __future__ import annotations

from PyQt6.QtGui import QUndoCommand

from core.action import Action


class AddActionCommand(QUndoCommand):
    """Undo-able: insert a single action at a position."""

    def __init__(self, actions: list[Action], pos: int,
                 action: Action) -> None:
        super().__init__(f"Add {action.get_display_name()}")
        self._actions = actions
        self._pos = pos
        self._action = action

    def redo(self) -> None:
        self._actions.insert(self._pos, self._action)

    def undo(self) -> None:
        self._actions.pop(self._pos)


class EditActionCommand(QUndoCommand):
    """Undo-able: replace action at a row."""

    def __init__(self, actions: list[Action], row: int,
                 old_action: Action, new_action: Action) -> None:
        super().__init__(f"Edit {new_action.get_display_name()}")
        self._actions = actions
        self._row = row
        self._old = old_action
        self._new = new_action

    def redo(self) -> None:
        self._actions[self._row] = self._new

    def undo(self) -> None:
        self._actions[self._row] = self._old


class DeleteActionsCommand(QUndoCommand):
    """Undo-able: delete one or more actions by row indices."""

    def __init__(self, actions: list[Action],
                 rows: list[int]) -> None:
        count = len(rows)
        text = (f"Delete {actions[rows[0]].get_display_name()}"
                if count == 1
                else f"Delete {count} actions")
        super().__init__(text)
        self._actions = actions
        # Store (row, action) pairs sorted ascending for undo re-insertion
        self._deleted: list[tuple[int, Action]] = [
            (r, actions[r]) for r in sorted(rows)
        ]

    def redo(self) -> None:
        # Delete in reverse order so indices don't shift
        for row, _ in reversed(self._deleted):
            self._actions.pop(row)

    def undo(self) -> None:
        # Re-insert in ascending order to restore original positions
        for row, action in self._deleted:
            self._actions.insert(row, action)


class MoveActionCommand(QUndoCommand):
    """Undo-able: swap two adjacent actions."""

    def __init__(self, actions: list[Action],
                 from_row: int, to_row: int) -> None:
        direction = "up" if to_row < from_row else "down"
        super().__init__(
            f"Move {actions[from_row].get_display_name()} {direction}")
        self._actions = actions
        self._from = from_row
        self._to = to_row

    def redo(self) -> None:
        a = self._actions
        a[self._from], a[self._to] = a[self._to], a[self._from]

    def undo(self) -> None:
        # Swap back
        a = self._actions
        a[self._from], a[self._to] = a[self._to], a[self._from]


class DuplicateActionCommand(QUndoCommand):
    """Undo-able: insert a duplicate after the source row."""

    def __init__(self, actions: list[Action], source_row: int,
                 duplicate: Action) -> None:
        super().__init__(
            f"Duplicate {actions[source_row].get_display_name()}")
        self._actions = actions
        self._insert_pos = source_row + 1
        self._dup = duplicate

    def redo(self) -> None:
        self._actions.insert(self._insert_pos, self._dup)

    def undo(self) -> None:
        self._actions.pop(self._insert_pos)


class ToggleEnabledCommand(QUndoCommand):
    """Undo-able: toggle enabled for selected rows. Self-inverse."""

    def __init__(self, actions: list[Action],
                 rows: list[int]) -> None:
        super().__init__(f"Toggle {len(rows)} action(s)")
        self._actions = actions
        self._rows = list(rows)

    def _flip(self) -> None:
        for r in self._rows:
            self._actions[r].enabled = not self._actions[r].enabled

    def redo(self) -> None:
        self._flip()

    def undo(self) -> None:
        self._flip()


class AddBatchCommand(QUndoCommand):
    """Undo-able: append a batch of recorded actions."""

    def __init__(self, actions: list[Action],
                 batch: list[Action]) -> None:
        super().__init__(f"Record {len(batch)} actions")
        self._actions = actions
        self._batch = batch
        self._insert_pos = len(actions)  # will be appended at end

    def redo(self) -> None:
        self._actions.extend(self._batch)

    def undo(self) -> None:
        del self._actions[self._insert_pos:]


class ReorderActionsCommand(QUndoCommand):
    """Undo-able: reorder actions (e.g. via drag-drop)."""

    def __init__(self, actions: list[Action],
                 old_order: list[Action],
                 new_order: list[Action]) -> None:
        super().__init__("Reorder actions (drag)")
        self._actions = actions
        self._old_order = list(old_order)
        self._new_order = list(new_order)

    def redo(self) -> None:
        self._actions[:] = self._new_order

    def undo(self) -> None:
        self._actions[:] = self._old_order

