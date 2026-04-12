"""
Multi-Run Dashboard — manage concurrent macro executions.

Each EngineSlot wraps a MacroEngine (QThread) with its own
ExecutionContext, stop_event, and signal routing.
Max 4 concurrent slots.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.engine import MacroEngine

logger = logging.getLogger(__name__)


MAX_SLOTS = 4


@dataclass
class EngineSlot:
    """One concurrent macro execution slot."""

    macro_name: str = ""
    macro_path: str = ""
    actions: list = field(default_factory=list)
    engine: Optional[MacroEngine] = None
    status: str = "idle"  # idle | running | paused | error
    progress: tuple[int, int] = (0, 0)  # (current, total)
    loop_info: tuple[int, int] = (0, 0)  # (current_loop, total_loops)
    last_error: str = ""


class MultiRunPanel(QWidget):
    """Dashboard panel for managing concurrent macro executions."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._slots: list[EngineSlot] = []
        self._setup_ui()
        self._setup_refresh_timer()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Header
        header = QHBoxLayout()
        title = QLabel("🚀 Multi-Run Dashboard")
        title.setStyleSheet("font-weight: bold; font-size: 13px;")
        header.addWidget(title)

        header.addStretch()

        self._add_btn = QPushButton("+ Thêm Macro")
        self._add_btn.setToolTip(f"Thêm macro file (tối đa {MAX_SLOTS})")
        self._add_btn.clicked.connect(self._on_add_macro)
        header.addWidget(self._add_btn)

        self._start_all_btn = QPushButton("▶ All")
        self._start_all_btn.setToolTip("Chạy tất cả macro")
        self._start_all_btn.clicked.connect(self._on_start_all)
        header.addWidget(self._start_all_btn)

        self._stop_all_btn = QPushButton("⏹ All")
        self._stop_all_btn.setToolTip("Dừng tất cả macro")
        self._stop_all_btn.clicked.connect(self._on_stop_all)
        header.addWidget(self._stop_all_btn)

        layout.addLayout(header)

        # Table
        self._table = QTableWidget(0, 6)
        self._table.setHorizontalHeaderLabels(
            ["Macro", "Actions", "Trạng thái", "Tiến trình", "Loop", "Điều khiển"]
        )
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)

        # Column sizing
        h = self._table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)  # Macro name
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)

        layout.addWidget(self._table)

        # Help label
        help_label = QLabel(
            "💡 Mỗi macro chạy trên thread riêng. "
            "Kết hợp với Stealth Click để chạy đồng thời không xung đột."
        )
        help_label.setWordWrap(True)
        help_label.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(help_label)

    def _setup_refresh_timer(self) -> None:
        """Timer to refresh table every 500ms during execution."""
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._refresh_table)
        self._refresh_timer.setInterval(500)

    # ── Public API ────────────────────────────────────────

    def add_macro_file(self, filepath: str) -> bool:
        """Load a macro from file and add to a new slot.

        Returns True if added, False if max slots reached or load error.
        """
        if len(self._slots) >= MAX_SLOTS:
            QMessageBox.warning(
                self,
                "Đã đạt giới hạn",
                f"Tối đa {MAX_SLOTS} macro chạy đồng thời.",
            )
            return False

        try:
            actions, settings = MacroEngine.load_macro(filepath)
        except (ValueError, OSError) as e:
            QMessageBox.critical(
                self, "Lỗi tải macro", f"Không thể mở file:\n{e}"
            )
            return False

        slot = EngineSlot(
            macro_name=settings.get("name", Path(filepath).stem),
            macro_path=filepath,
            actions=actions,
        )
        self._slots.append(slot)
        self._sync_table()
        self._update_buttons()

        # Start refresh timer if not running
        if not self._refresh_timer.isActive():
            self._refresh_timer.start()

        logger.info("Multi-run: added '%s' (%d actions)", slot.macro_name, len(actions))
        return True

    @property
    def slot_count(self) -> int:
        return len(self._slots)

    @property
    def running_count(self) -> int:
        return sum(1 for s in self._slots if s.status in ("running", "paused"))

    # ── Slot control ──────────────────────────────────────

    def _start_slot(self, idx: int) -> None:
        """Start or resume the engine in a slot."""
        if idx >= len(self._slots):
            return
        slot = self._slots[idx]

        if slot.status == "paused" and slot.engine and slot.engine.isRunning():
            slot.engine.resume()
            slot.status = "running"
            return

        # Create fresh engine
        engine = MacroEngine()
        engine.load_actions(slot.actions)
        if slot.macro_path:
            engine.set_macro_file(slot.macro_path)
        engine.set_loop(count=0)  # Infinite by default for multi-run

        # Wire signals — using lambda with idx captured
        engine.started_signal.connect(lambda i=idx: self._on_slot_started(i))
        engine.stopped_signal.connect(lambda i=idx: self._on_slot_stopped(i))
        engine.error_signal.connect(lambda msg, i=idx: self._on_slot_error(i, msg))
        engine.progress_signal.connect(
            lambda cur, tot, i=idx: self._on_slot_progress(i, cur, tot)
        )
        engine.loop_signal.connect(
            lambda cur, tot, i=idx: self._on_slot_loop(i, cur, tot)
        )

        slot.engine = engine
        slot.status = "running"
        slot.last_error = ""
        engine.start()
        logger.info("Multi-run: started slot %d '%s'", idx, slot.macro_name)

    def _pause_slot(self, idx: int) -> None:
        """Pause/resume engine in a slot."""
        if idx >= len(self._slots):
            return
        slot = self._slots[idx]
        if not slot.engine or not slot.engine.isRunning():
            return

        if slot.status == "paused":
            slot.engine.resume()
            slot.status = "running"
        else:
            slot.engine.pause()
            slot.status = "paused"

    def _stop_slot(self, idx: int) -> None:
        """Stop engine in a slot."""
        if idx >= len(self._slots):
            return
        slot = self._slots[idx]
        if slot.engine and slot.engine.isRunning():
            slot.engine.stop()

    def _remove_slot(self, idx: int) -> None:
        """Remove a slot (must be stopped first)."""
        if idx >= len(self._slots):
            return
        slot = self._slots[idx]
        if slot.engine and slot.engine.isRunning():
            QMessageBox.warning(
                self, "Không thể xoá",
                "Dừng macro trước khi xoá.",
            )
            return

        self._slots.pop(idx)
        self._sync_table()
        self._update_buttons()

        # Stop timer if no slots
        if not self._slots and self._refresh_timer.isActive():
            self._refresh_timer.stop()

        logger.info("Multi-run: removed slot %d", idx)

    # ── Signal handlers ───────────────────────────────────

    def _on_slot_started(self, idx: int) -> None:
        if idx < len(self._slots):
            self._slots[idx].status = "running"

    def _on_slot_stopped(self, idx: int) -> None:
        if idx < len(self._slots):
            slot = self._slots[idx]
            slot.status = "idle"
            slot.progress = (0, 0)
            slot.loop_info = (0, 0)

    def _on_slot_error(self, idx: int, msg: str) -> None:
        if idx < len(self._slots):
            self._slots[idx].last_error = msg

    def _on_slot_progress(self, idx: int, current: int, total: int) -> None:
        if idx < len(self._slots):
            self._slots[idx].progress = (current, total)

    def _on_slot_loop(self, idx: int, current: int, total: int) -> None:
        if idx < len(self._slots):
            self._slots[idx].loop_info = (current, total)

    # ── UI events ─────────────────────────────────────────

    def _on_add_macro(self) -> None:
        """Open file dialog to add a macro."""
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Chọn Macro File", "", "Macro Files (*.json);;All Files (*)"
        )
        if filepath:
            self.add_macro_file(filepath)

    def _on_start_all(self) -> None:
        """Start all idle slots."""
        for i, slot in enumerate(self._slots):
            if slot.status == "idle":
                self._start_slot(i)

    def _on_stop_all(self) -> None:
        """Stop all running slots."""
        for i, slot in enumerate(self._slots):
            if slot.status in ("running", "paused"):
                self._stop_slot(i)

    # ── Table management ──────────────────────────────────

    def _sync_table(self) -> None:
        """Rebuild table rows from slots."""
        self._table.setRowCount(len(self._slots))
        for row, slot in enumerate(self._slots):
            self._set_row(row, slot)

    def _set_row(self, row: int, slot: EngineSlot) -> None:
        """Set/update a single table row."""
        # Col 0: Macro name
        name_item = QTableWidgetItem(slot.macro_name)
        name_item.setToolTip(slot.macro_path)
        self._table.setItem(row, 0, name_item)

        # Col 1: Action count
        self._table.setItem(row, 1, QTableWidgetItem(str(len(slot.actions))))

        # Col 2: Status
        status_text = {
            "idle": "⏹ Idle",
            "running": "▶ Running",
            "paused": "⏸ Paused",
            "error": "❌ Error",
        }.get(slot.status, slot.status)
        status_item = QTableWidgetItem(status_text)
        self._table.setItem(row, 2, status_item)

        # Col 3: Progress
        if slot.progress[1] > 0:
            ptext = f"{slot.progress[0]}/{slot.progress[1]}"
        else:
            ptext = "—"
        self._table.setItem(row, 3, QTableWidgetItem(ptext))

        # Col 4: Loop
        if slot.loop_info[0] > 0:
            total = slot.loop_info[1]
            ltext = f"#{slot.loop_info[0]}" + ("" if total < 0 else f"/{total}")
        else:
            ltext = "—"
        self._table.setItem(row, 4, QTableWidgetItem(ltext))

        # Col 5: Control buttons
        ctrl_widget = self._make_control_buttons(row, slot)
        self._table.setCellWidget(row, 5, ctrl_widget)

    def _make_control_buttons(self, row: int, slot: EngineSlot) -> QWidget:
        """Create play/pause/stop/remove buttons for a slot."""
        w = QWidget()
        layout = QHBoxLayout(w)
        layout.setContentsMargins(2, 0, 2, 0)
        layout.setSpacing(2)

        if slot.status == "idle":
            play = QPushButton("▶")
            play.setToolTip("Chạy")
            play.setFixedWidth(28)
            play.clicked.connect(lambda _, i=row: self._start_slot(i))
            layout.addWidget(play)
        elif slot.status == "running":
            pause = QPushButton("⏸")
            pause.setToolTip("Tạm dừng")
            pause.setFixedWidth(28)
            pause.clicked.connect(lambda _, i=row: self._pause_slot(i))
            layout.addWidget(pause)

            stop = QPushButton("⏹")
            stop.setToolTip("Dừng")
            stop.setFixedWidth(28)
            stop.clicked.connect(lambda _, i=row: self._stop_slot(i))
            layout.addWidget(stop)
        elif slot.status == "paused":
            resume = QPushButton("▶")
            resume.setToolTip("Tiếp tục")
            resume.setFixedWidth(28)
            resume.clicked.connect(lambda _, i=row: self._start_slot(i))
            layout.addWidget(resume)

            stop = QPushButton("⏹")
            stop.setToolTip("Dừng")
            stop.setFixedWidth(28)
            stop.clicked.connect(lambda _, i=row: self._stop_slot(i))
            layout.addWidget(stop)

        remove = QPushButton("🗑")
        remove.setToolTip("Xoá slot")
        remove.setFixedWidth(28)
        remove.clicked.connect(lambda _, i=row: self._remove_slot(i))
        layout.addWidget(remove)

        return w

    def _refresh_table(self) -> None:
        """Periodic refresh of status/progress columns (lightweight)."""
        for row, slot in enumerate(self._slots):
            if row >= self._table.rowCount():
                break
            # Status
            status_text = {
                "idle": "⏹ Idle",
                "running": "▶ Running",
                "paused": "⏸ Paused",
                "error": "❌ Error",
            }.get(slot.status, slot.status)
            item = self._table.item(row, 2)
            if item and item.text() != status_text:
                item.setText(status_text)
                # Rebuild control buttons on status change
                ctrl = self._make_control_buttons(row, slot)
                self._table.setCellWidget(row, 5, ctrl)

            # Progress
            if slot.progress[1] > 0:
                ptext = f"{slot.progress[0]}/{slot.progress[1]}"
            else:
                ptext = "—"
            item = self._table.item(row, 3)
            if item and item.text() != ptext:
                item.setText(ptext)

            # Loop
            if slot.loop_info[0] > 0:
                total = slot.loop_info[1]
                ltext = f"#{slot.loop_info[0]}" + ("" if total < 0 else f"/{total}")
            else:
                ltext = "—"
            item = self._table.item(row, 4)
            if item and item.text() != ltext:
                item.setText(ltext)

    def _update_buttons(self) -> None:
        """Update add button state based on slot count."""
        self._add_btn.setEnabled(len(self._slots) < MAX_SLOTS)

    # ── Cleanup ───────────────────────────────────────────

    def stop_all_and_wait(self, timeout_ms: int = 3000) -> None:
        """Stop all engines and wait for termination. Called on app exit."""
        for slot in self._slots:
            if slot.engine and slot.engine.isRunning():
                slot.engine.stop()
        for slot in self._slots:
            if slot.engine and slot.engine.isRunning():
                slot.engine.wait(timeout_ms)
        self._refresh_timer.stop()
        logger.info("Multi-run: all engines stopped")
