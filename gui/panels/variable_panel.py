"""
Variable inspector panel — extracted from main_window.py.
Shows live variable values during macro execution.
"""

from typing import Callable, Optional

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QGroupBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class VariablePanel(QWidget):
    """Live variable inspector — auto-shows during engine run."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._get_vars_fn: Optional[Callable[[], dict]] = None
        self._last_snapshot: dict[str, tuple[str, str]] = {}  # P3-B: cache for diff-based updates
        self._setup_ui()
        self._setup_timer()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._group = QGroupBox("🔍 Biến")
        var_layout = QVBoxLayout(self._group)

        self._var_table = QTableWidget(0, 3)
        self._var_table.setHorizontalHeaderLabels(["Tên", "Giá trị", "Kiểu"])
        self._var_table.horizontalHeader().setStretchLastSection(True)  # type: ignore[union-attr]
        self._var_table.setMaximumHeight(120)
        self._var_table.setAlternatingRowColors(True)
        self._var_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._var_table.setAccessibleName("Bảng biến")
        var_layout.addWidget(self._var_table)

        layout.addWidget(self._group)
        self._group.setVisible(False)

    def _setup_timer(self) -> None:
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.setInterval(500)

    # -- Public API ---------------------------------------------------------

    def set_var_source(self, fn: Callable[[], dict]) -> None:
        """Set the function that returns current variables dict."""
        self._get_vars_fn = fn

    def start(self) -> None:
        """Show panel and start polling variables."""
        self._last_snapshot.clear()  # P3-B: reset cache on start
        self._group.setVisible(True)
        self._timer.start()

    def stop(self) -> None:
        """Hide panel and stop polling."""
        self._timer.stop()
        self._group.setVisible(False)

    # -- Internal -----------------------------------------------------------

    def _refresh(self) -> None:
        """P3-B: Diff-based refresh — only update cells that changed."""
        if not self._get_vars_fn:
            return
        try:
            variables = self._get_vars_fn()
        except Exception:
            return

        # Build new snapshot: {name: (str_value, type_name)}
        new_snap: dict[str, tuple[str, str]] = {}
        for name, value in sorted(variables.items()):
            new_snap[name] = (str(value), type(value).__name__)

        # Compare keys — if set of variable names changed, rebuild rows
        old_keys = set(self._last_snapshot.keys())
        new_keys = set(new_snap.keys())

        if old_keys != new_keys:
            # Keys changed — full rebuild (rare: only on new variable or deletion)
            self._var_table.setRowCount(len(new_snap))
            for row, (name, (val, typ)) in enumerate(new_snap.items()):
                self._var_table.setItem(row, 0, QTableWidgetItem(name))
                self._var_table.setItem(row, 1, QTableWidgetItem(val))
                self._var_table.setItem(row, 2, QTableWidgetItem(typ))
        else:
            # Same keys — only update values that changed (hot path)
            for row, (name, (val, typ)) in enumerate(new_snap.items()):
                old_val, old_typ = self._last_snapshot.get(name, ("", ""))
                if val != old_val:
                    item = self._var_table.item(row, 1)
                    if item:
                        item.setText(val)
                    else:
                        self._var_table.setItem(row, 1, QTableWidgetItem(val))
                if typ != old_typ:
                    item = self._var_table.item(row, 2)
                    if item:
                        item.setText(typ)
                    else:
                        self._var_table.setItem(row, 2, QTableWidgetItem(typ))

        self._last_snapshot = dict(new_snap)

