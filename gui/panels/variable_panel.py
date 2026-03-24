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
        self._group.setVisible(True)
        self._timer.start()

    def stop(self) -> None:
        """Hide panel and stop polling."""
        self._timer.stop()
        self._group.setVisible(False)

    # -- Internal -----------------------------------------------------------

    def _refresh(self) -> None:
        """Poll variables and update table."""
        if not self._get_vars_fn:
            return
        try:
            variables = self._get_vars_fn()
        except Exception:
            return
        self._var_table.setRowCount(len(variables))
        for row, (name, value) in enumerate(sorted(variables.items())):
            self._var_table.setItem(row, 0, QTableWidgetItem(str(name)))
            self._var_table.setItem(row, 1, QTableWidgetItem(str(value)))
            self._var_table.setItem(row, 2, QTableWidgetItem(type(value).__name__))
