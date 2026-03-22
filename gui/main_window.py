"""
Main application window for AutoPilot.

Layout:
  ┌──────────────────────────────────────────┐
  │  Toolbar   [New][Open][Save] [Rec][▶][⏹] │
  ├───────────────────────┬──────────────────┤
  │   Action List (table) │  Right Panel     │
  │   - Drag/drop reorder │  - Recording     │
  │   - Enable/disable    │  - Properties    │
  │   - Add / Edit / Del  │                  │
  ├───────────────────────┴──────────────────┤
  │  Status Bar: state • progress • info     │
  └──────────────────────────────────────────┘
"""

import datetime as _dt
import json
import logging
import os
from pathlib import Path

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QPushButton, QToolBar, QStatusBar, QLabel, QFileDialog,
    QMessageBox, QSpinBox, QGroupBox, QFormLayout, QProgressBar,
    QApplication, QCheckBox, QListWidget, QPlainTextEdit,
    QDoubleSpinBox,
)
from PyQt6.QtCore import Qt, QSize, QTimer, QObject, pyqtSignal
from PyQt6.QtGui import QAction as QMenuAction, QKeySequence, QCloseEvent, QUndoStack
from typing import Any, Optional

from core.action import Action
from core.engine import MacroEngine
from gui.action_editor import ActionEditorDialog
from gui.recording_panel import RecordingPanel
from gui.image_capture import ImageCaptureOverlay
from gui.coordinate_picker import CoordinatePickerOverlay
from gui.tray import TrayManager
from gui.settings_dialog import SettingsDialog, load_config, save_config
from gui.styles import DARK_THEME
from version import __version__, __app_name__, __author__, __build_date__

logger = logging.getLogger(__name__)

# Ensure modules are registered
import modules.mouse       # noqa: F401
import modules.keyboard    # noqa: F401
import modules.image       # noqa: F401
import modules.pixel       # noqa: F401
import core.scheduler       # noqa: F401
from core.autosave import AutoSaveManager


# ---------------------------------------------------------------------------
# Thread-safe logging handler for GUI
# ---------------------------------------------------------------------------
class _LogSignalBridge(QObject):
    """Bridge: logging.Handler cannot have pyqtSignal, QObject can."""
    log_record = pyqtSignal(str)


class QLogHandler(logging.Handler):
    """Emits formatted log records as Qt signals (thread-safe)."""

    def __init__(self) -> None:
        super().__init__()
        self._bridge = _LogSignalBridge()
        self.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%H:%M:%S",
        ))

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            self._bridge.log_record.emit(msg)
        except Exception:
            self.handleError(record)


class MainWindow(QMainWindow):

    def __init__(self) -> None:
        super().__init__()
        self._actions: list[Action] = []
        self._engine = MacroEngine()
        self._config = load_config()
        self._current_file: str = ""
        self._macro_dir = str(Path("macros").resolve())
        QTimer.singleShot(0, lambda: os.makedirs(self._macro_dir, exist_ok=True))

        self.setWindowTitle("AutoMacro (by TungDo) – New Macro")
        w = self._config.get("ui", {}).get("window_width", 900)
        h = self._config.get("ui", {}).get("window_height", 650)
        self.resize(w, h)
        self.setStyleSheet(DARK_THEME)

        self._undo_stack = QUndoStack(self)
        self._undo_stack.indexChanged.connect(self._on_undo_index_changed)
        self._undo_stack.cleanChanged.connect(self._on_clean_changed)

        self._setup_toolbar()
        self._setup_central()
        self._setup_statusbar()
        self._setup_tray()
        self._connect_engine()
        self._setup_autosave()

    def _setup_autosave(self) -> None:
        """Start background auto-save (prevents data loss on crash)."""
        self._autosave = AutoSaveManager(interval_s=60, max_backups=5)
        self._autosave.start(
            save_callback=self._autosave_callback,
            backup_dir=Path(self._macro_dir),
        )

    def _autosave_callback(self) -> bool:
        """Called by AutoSaveManager when dirty flag is set."""
        if not self._current_file:
            return False  # no file to save to
        try:
            MacroEngine.save_macro(
                self._current_file, self._actions,
                name=Path(self._current_file).stem,
                loop_count=self._loop_spin.value(),
                loop_delay_ms=self._loop_delay_spin.value(),
            )
            logger.info("AutoSave completed: %s", Path(self._current_file).name)
            return True
        except Exception as e:
            logger.warning("AutoSave failed: %s", e)
            return False

    def _mark_dirty(self) -> None:
        """Mark that unsaved changes exist."""
        self._autosave.mark_dirty()

    def _on_undo_index_changed(self) -> None:
        """Refresh table whenever undo/redo changes actions."""
        if getattr(self, '_refreshing', False):
            return
        self._refreshing = True
        try:
            self._refresh_table()
        finally:
            self._refreshing = False

    def _on_clean_changed(self, clean: bool) -> None:
        """Sync undo stack clean state with autosave."""
        if clean:
            self._autosave.mark_clean()
        else:
            self._autosave.mark_dirty()

    # ------------------------------------------------------------------ #
    # Toolbar
    # ------------------------------------------------------------------ #
    def _setup_toolbar(self) -> None:
        # --- Row 1: File & Edit actions ---
        tb = QToolBar("File & Edit")
        tb.setIconSize(QSize(20, 20))
        tb.setMovable(False)
        self.addToolBar(tb)

        new_act = QMenuAction("📄 New", self)
        new_act.setShortcut(QKeySequence("Ctrl+N"))
        new_act.setToolTip("Tạo macro mới (Ctrl+N)")
        new_act.triggered.connect(self._on_new)
        tb.addAction(new_act)

        open_act = QMenuAction("📂 Open", self)
        open_act.setShortcut(QKeySequence("Ctrl+O"))
        open_act.setToolTip("Mở file macro (Ctrl+O)")
        open_act.triggered.connect(self._on_open)
        tb.addAction(open_act)

        save_act = QMenuAction("💾 Save", self)
        save_act.setShortcut(QKeySequence("Ctrl+S"))
        save_act.setToolTip("Lưu macro hiện tại (Ctrl+S)")
        save_act.triggered.connect(self._on_save)
        tb.addAction(save_act)

        undo_act = self._undo_stack.createUndoAction(self, "↩ Undo")
        undo_act.setShortcut(QKeySequence.StandardKey.Undo)
        tb.addAction(undo_act)

        redo_act = self._undo_stack.createRedoAction(self, "↪ Redo")
        redo_act.setShortcut(QKeySequence.StandardKey.Redo)
        tb.addAction(redo_act)

        tb.addSeparator()

        self._add_act = QMenuAction("➕ Add", self)
        self._add_act.setToolTip("Thêm action mới")
        self._add_act.triggered.connect(self._on_add_action)
        tb.addAction(self._add_act)

        self._edit_act = QMenuAction("✏️ Edit", self)
        self._edit_act.setToolTip("Sửa action đang chọn")
        self._edit_act.triggered.connect(self._on_edit_action)
        tb.addAction(self._edit_act)

        self._del_act = QMenuAction("🗑️ Delete", self)
        self._del_act.setShortcut(QKeySequence.StandardKey.Delete)
        self._del_act.setToolTip("Xóa action (Delete)")
        self._del_act.triggered.connect(self._on_delete_action)
        tb.addAction(self._del_act)

        tb.addSeparator()

        # Tools
        capture_act = QMenuAction("📸 Capture", self)
        capture_act.setToolTip("Capture a screen region as template image")
        capture_act.triggered.connect(self._on_capture)
        tb.addAction(capture_act)

        coord_act = QMenuAction("🎯 Pick XY", self)
        coord_act.setShortcut(QKeySequence("Ctrl+G"))
        coord_act.setToolTip(
            "Pick coordinates from screen (Ctrl+G)\n"
            "Click anywhere → X,Y shown in status bar & copied to clipboard")
        coord_act.triggered.connect(self._on_pick_coordinate)
        tb.addAction(coord_act)

        settings_act = QMenuAction("⚙ Settings", self)
        settings_act.setToolTip("Mở cài đặt ứng dụng")
        settings_act.triggered.connect(self._on_settings)
        tb.addAction(settings_act)

        about_act = QMenuAction("ℹ️ About", self)
        about_act.setToolTip("Thông tin ứng dụng")
        about_act.triggered.connect(self._on_about)
        tb.addAction(about_act)

    # ------------------------------------------------------------------ #
    # Central Widget
    # ------------------------------------------------------------------ #
    def _setup_central(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(8, 8, 8, 8)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: Action table
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        header_label = QLabel("Action List")
        header_label.setObjectName("headerLabel")
        left_layout.addWidget(header_label)

        self._table = QTableWidget(0, 6)
        self._table.setAccessibleName("Action list table")
        self._table.setHorizontalHeaderLabels(
            ["#", "", "Action", "Delay", "✓", "Description"])
        h_header = self._table.horizontalHeader()
        assert h_header is not None
        h_header.setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents)  # #
        h_header.setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents)  # Icon
        h_header.setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch)           # Action name
        h_header.setSectionResizeMode(
            3, QHeaderView.ResizeMode.ResizeToContents)  # Delay
        h_header.setSectionResizeMode(
            4, QHeaderView.ResizeMode.ResizeToContents)  # Enabled
        h_header.setSectionResizeMode(
            5, QHeaderView.ResizeMode.Stretch)           # Description
        self._table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection)
        # Drag-drop reorder
        self._table.setDragDropMode(
            QAbstractItemView.DragDropMode.InternalMove)
        self._table.setDragEnabled(True)
        self._table.setAcceptDrops(True)
        self._table.setDropIndicatorShown(True)
        vert_header = self._table.verticalHeader()
        assert vert_header is not None
        vert_header.setVisible(False)
        self._table.setShowGrid(False)
        self._table.setAlternatingRowColors(True)
        self._table.doubleClicked.connect(self._on_edit_action)
        # Right-click context menu
        self._table.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(
            self._show_context_menu)
        # Drag-drop undo: snapshot order before drop
        self._pre_drag_order: list[Action] = []
        self._table.viewport().installEventFilter(self)
        left_layout.addWidget(self._table)

        # Empty state overlay (shown when no actions)
        self._empty_overlay = QLabel(
            "🎬 Welcome to AutoMacro\n\n"
            "⏺  Click Record to start capturing\n"
            "➕  Or click + to add steps manually\n"
            "📂  Open a macro: Ctrl+O\n\n"
            "Hotkeys: F6=Play  F7=Pause  F8=Stop")
        self._empty_overlay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_overlay.setObjectName("emptyOverlay")
        self._empty_overlay.setWordWrap(True)
        left_layout.addWidget(self._empty_overlay)

        # Move Up/Down buttons with keyboard shortcuts
        move_layout = QHBoxLayout()
        self._up_btn = QPushButton("⬆ Up")
        self._up_btn.setShortcut(QKeySequence("Ctrl+Up"))
        self._up_btn.setToolTip("Move action up (Ctrl+↑)")
        self._up_btn.clicked.connect(self._on_move_up)
        move_layout.addWidget(self._up_btn)
        self._down_btn = QPushButton("⬇ Down")
        self._down_btn.setShortcut(QKeySequence("Ctrl+Down"))
        self._down_btn.setToolTip("Move action down (Ctrl+↓)")
        self._down_btn.clicked.connect(self._on_move_down)
        move_layout.addWidget(self._down_btn)
        self._dup_btn = QPushButton("📋 Duplicate")
        self._dup_btn.setShortcut(QKeySequence("Ctrl+D"))
        self._dup_btn.setToolTip("Duplicate action (Ctrl+D)")
        self._dup_btn.clicked.connect(self._on_duplicate)
        move_layout.addWidget(self._dup_btn)
        self._copy_btn = QPushButton("📄 Copy")
        self._copy_btn.setShortcut(QKeySequence("Ctrl+C"))
        self._copy_btn.setToolTip("Copy selected actions (Ctrl+C)")
        self._copy_btn.clicked.connect(self._on_copy_actions)
        move_layout.addWidget(self._copy_btn)
        self._paste_btn = QPushButton("📥 Paste")
        self._paste_btn.setShortcut(QKeySequence("Ctrl+V"))
        self._paste_btn.setToolTip("Paste actions from clipboard (Ctrl+V)")
        self._paste_btn.clicked.connect(self._on_paste_actions)
        move_layout.addWidget(self._paste_btn)
        move_layout.addStretch()

        # Stats bar
        self._stats_label = QLabel("")
        self._stats_label.setObjectName("subtitleLabel")
        move_layout.addWidget(self._stats_label)

        left_layout.addLayout(move_layout)

        splitter.addWidget(left_widget)

        # Right panel
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        # ── 1. Playback controls (prominent) ──────────────────
        play_group = QGroupBox("Playback")
        play_vbox = QVBoxLayout(play_group)

        self._play_btn = QPushButton("▶  P L A Y")
        self._play_btn.setObjectName("playButton")
        self._play_btn.setMinimumHeight(48)
        self._play_btn.setToolTip("Bắt đầu chạy macro (F6)")
        self._play_btn.setAccessibleName("Play macro")
        self._play_btn.clicked.connect(self._on_play)
        play_vbox.addWidget(self._play_btn)

        ctrl_row = QHBoxLayout()
        self._pause_btn = QPushButton("⏸ Pause")
        self._pause_btn.setObjectName("controlButton")
        self._pause_btn.setEnabled(False)
        self._pause_btn.setToolTip("Tạm dừng (F7)")
        self._pause_btn.setAccessibleName("Pause macro")
        self._pause_btn.clicked.connect(self._on_pause)
        ctrl_row.addWidget(self._pause_btn)

        self._stop_btn = QPushButton("⏹ Stop")
        self._stop_btn.setObjectName("dangerButton")
        self._stop_btn.setEnabled(False)
        self._stop_btn.setToolTip("Dừng hoàn toàn (F8)")
        self._stop_btn.setAccessibleName("Stop macro")
        self._stop_btn.clicked.connect(self._on_stop)
        ctrl_row.addWidget(self._stop_btn)
        play_vbox.addLayout(ctrl_row)

        right_layout.addWidget(play_group)

        # ── 2. Loop settings ──────────────────────────────────
        self._loop_group = QGroupBox("Loop Settings")
        loop_form = QFormLayout(self._loop_group)

        self._loop_spin = QSpinBox()
        self._loop_spin.setRange(0, 999999)
        self._loop_spin.setValue(1)
        self._loop_spin.setSpecialValueText("∞ Infinite")
        loop_form.addRow("Loop Count:", self._loop_spin)

        self._loop_delay_spin = QSpinBox()
        self._loop_delay_spin.setRange(0, 60000)
        self._loop_delay_spin.setSuffix(" ms")
        self._loop_delay_spin.setValue(0)
        loop_form.addRow("Loop Delay:", self._loop_delay_spin)

        self._stop_on_error_check = QCheckBox("Stop on Error")
        self._stop_on_error_check.setToolTip(
            "Stop execution when an action fails instead of continuing")
        self._stop_on_error_check.setChecked(False)
        loop_form.addRow("", self._stop_on_error_check)

        self._speed_spin = QDoubleSpinBox()
        self._speed_spin.setRange(0.1, 5.0)
        self._speed_spin.setValue(1.0)
        self._speed_spin.setSingleStep(0.1)
        self._speed_spin.setDecimals(1)
        self._speed_spin.setSuffix("×")
        self._speed_spin.setToolTip("Playback speed (0.1× slow → 5× fast)")
        loop_form.addRow("Speed:", self._speed_spin)

        right_layout.addWidget(self._loop_group)

        # ── 3. Recording panel ────────────────────────────────
        self._rec_panel = RecordingPanel()
        self._rec_panel.recording_finished.connect(self._on_recording_done)
        right_layout.addWidget(self._rec_panel)

        # ── 4. Execution (progress + log merged) ──────────────
        exec_group = QGroupBox("Execution")
        exec_layout = QVBoxLayout(exec_group)

        self._action_label = QLabel("Idle")
        self._action_label.setObjectName("subtitleLabel")
        exec_layout.addWidget(self._action_label)

        self._progress_bar = QProgressBar()
        self._progress_bar.setFormat("%v / %m")
        exec_layout.addWidget(self._progress_bar)

        self._loop_label = QLabel("")
        self._loop_label.setObjectName("subtitleLabel")
        exec_layout.addWidget(self._loop_label)

        self._exec_log = QListWidget()
        self._exec_log.setObjectName("execLog")
        self._exec_log.setMaximumHeight(150)
        exec_layout.addWidget(self._exec_log)

        right_layout.addWidget(exec_group)

        right_layout.addStretch()

        splitter.addWidget(right_widget)
        splitter.setSizes([600, 300])

        # ── Vertical splitter: content on top, log panel on bottom ──
        v_splitter = QSplitter(Qt.Orientation.Vertical)
        v_splitter.addWidget(splitter)

        self._setup_log_panel(v_splitter)

        v_splitter.setSizes([500, 150])
        v_splitter.setCollapsible(1, True)  # log panel collapsible

        layout.addWidget(v_splitter)

    # ------------------------------------------------------------------ #
    # Application Log Panel (bottom)
    # ------------------------------------------------------------------ #
    def _setup_log_panel(self, parent_splitter: QSplitter) -> None:
        """Add a collapsible log panel at the bottom of the main layout."""
        log_widget = QWidget()
        log_layout = QVBoxLayout(log_widget)
        log_layout.setContentsMargins(0, 4, 0, 0)
        log_layout.setSpacing(2)

        # Header with clear button
        header_row = QHBoxLayout()
        header_label = QLabel("📝 Application Log")
        header_label.setObjectName("subtitleLabel")
        header_row.addWidget(header_label)
        header_row.addStretch()
        clear_btn = QPushButton("🗑 Clear")
        clear_btn.setFixedHeight(22)
        clear_btn.setFixedWidth(70)
        clear_btn.clicked.connect(self._clear_log)
        header_row.addWidget(clear_btn)
        log_layout.addLayout(header_row)

        # Log text area
        self._app_log = QPlainTextEdit()
        self._app_log.setObjectName("appLog")
        self._app_log.setReadOnly(True)
        self._app_log.setMaximumBlockCount(1000)  # auto-trim for performance
        log_layout.addWidget(self._app_log)

        parent_splitter.addWidget(log_widget)

        # Attach logging handler to root logger
        self._log_handler = QLogHandler()
        self._log_handler._bridge.log_record.connect(self._append_log)
        logging.getLogger().addHandler(self._log_handler)

        # Replay startup summary (these logs fired before handler existed)
        logger.info("Application Log panel attached — showing live logs")
        logger.info("Hotkeys: F6=Start/Stop, F7=Pause, F8=Emergency Stop")

    def _append_log(self, text: str) -> None:
        """Slot: append a log line (called via signal, thread-safe)."""
        self._app_log.appendPlainText(text)

    def _clear_log(self) -> None:
        self._app_log.clear()

    # ------------------------------------------------------------------ #
    # Status Bar
    # ------------------------------------------------------------------ #
    def _setup_statusbar(self) -> None:
        self._statusbar = QStatusBar()
        self.setStatusBar(self._statusbar)
        self._status_label = QLabel("Ready")
        self._statusbar.addWidget(self._status_label)

        self._ram_label = QLabel("RAM: --")
        self._ram_label.setObjectName("subtitleLabel")
        self._statusbar.addPermanentWidget(self._ram_label)

        self._hotkey_label = QLabel(
            f"  Start/Stop: {self._config['hotkeys']['start_stop']}  |  "
            f"Pause: {self._config['hotkeys']['pause_resume']}  |  "
            f"Stop: {self._config['hotkeys']['emergency_stop']}")
        self._hotkey_label.setObjectName("subtitleLabel")
        self._statusbar.addPermanentWidget(self._hotkey_label)

        # Periodic RAM update (every 5s)
        self._ram_timer = QTimer()
        self._ram_timer.timeout.connect(self._update_ram_display)
        self._ram_timer.start(5000)
        self._update_ram_display()

    # ------------------------------------------------------------------ #
    # System Tray
    # ------------------------------------------------------------------ #
    def _setup_tray(self) -> None:
        self._tray = TrayManager(self)
        self._tray.show_requested.connect(self._show_from_tray)
        self._tray.play_requested.connect(self._on_play)
        self._tray.stop_requested.connect(self._on_stop)
        self._tray.pause_requested.connect(self._on_pause)
        self._tray.quit_requested.connect(self._on_quit)
        self._tray.show()

    # ------------------------------------------------------------------ #
    # Drag-drop undo support
    # ------------------------------------------------------------------ #
    def eventFilter(self, obj: QObject, event: Any) -> bool:
        """Intercept drag-drop on table viewport to push undo command."""
        from PyQt6.QtCore import QEvent
        if obj is self._table.viewport():
            if event.type() == QEvent.Type.DragEnter:
                # Snapshot order before drop
                self._pre_drag_order = list(self._actions)
            elif event.type() == QEvent.Type.Drop:
                # Schedule post-drop comparison (drop hasn't been applied yet)
                QTimer.singleShot(0, self._check_drag_reorder)
        return super().eventFilter(obj, event)

    def _check_drag_reorder(self) -> None:
        """Compare post-drop order with snapshot and push undo if changed."""
        if not self._pre_drag_order:
            return
        # Rebuild _actions from current table row order
        new_order: list[Action] = []
        for r in range(self._table.rowCount()):
            item = self._table.item(r, 0)
            if item:
                idx = int(item.text()) - 1  # "#" column = 1-based index
                if 0 <= idx < len(self._pre_drag_order):
                    new_order.append(self._pre_drag_order[idx])
        if len(new_order) == len(self._pre_drag_order) and \
                new_order != self._pre_drag_order:
            from core.undo_commands import ReorderActionsCommand
            cmd = ReorderActionsCommand(
                self._actions, self._pre_drag_order, new_order)
            self._undo_stack.push(cmd)
            logger.info("Drag-drop reorder (undoable)")
        self._pre_drag_order = []

    # ------------------------------------------------------------------ #
    # Error message helper
    # ------------------------------------------------------------------ #
    _ERROR_MAP: dict[str, str] = {
        "FileNotFoundError": "File không tồn tại hoặc đã bị xóa.",
        "PermissionError": "Không đủ quyền truy cập file.",
        "IsADirectoryError": "Đường dẫn là thư mục, không phải file.",
        "json.decoder.JSONDecodeError": "File không đúng định dạng JSON.",
        "JSONDecodeError": "File không đúng định dạng JSON.",
        "UnicodeDecodeError": "File chứa ký tự không hợp lệ.",
        "OSError": "Lỗi hệ thống khi truy cập file.",
        "IOError": "Lỗi đọc/ghi file.",
        "KeyError": "File macro thiếu trường dữ liệu bắt buộc.",
        "ValueError": "Dữ liệu trong file không hợp lệ.",
        "TypeError": "Kiểu dữ liệu trong file không đúng.",
    }

    @staticmethod
    def _friendly_error_msg(context: str, exc: Exception) -> str:
        """Build a user-friendly error message from an exception."""
        exc_name = type(exc).__name__
        friendly = MainWindow._ERROR_MAP.get(exc_name, "")
        if not friendly:
            # Fallback: use qualified name
            qname = f"{type(exc).__module__}.{exc_name}"
            friendly = MainWindow._ERROR_MAP.get(qname, "Đã xảy ra lỗi không xác định.")
        detail = str(exc)
        if len(detail) > 200:
            detail = detail[:200] + "..."
        return f"{context}\n\nNguyên nhân: {friendly}\nChi tiết: {detail}"

    # ------------------------------------------------------------------ #
    # Engine connections
    # ------------------------------------------------------------------ #
    def _connect_engine(self) -> None:
        self._engine.started_signal.connect(self._on_engine_started)
        self._engine.stopped_signal.connect(self._on_engine_stopped)
        self._engine.error_signal.connect(self._on_engine_error)
        self._engine.progress_signal.connect(self._on_engine_progress)
        self._engine.action_signal.connect(self._on_engine_action)
        self._engine.loop_signal.connect(self._on_engine_loop)

    def _set_ui_locked(self, locked: bool) -> None:
        """Disable/enable all editing controls when engine is running."""
        editable = not locked
        # Table & action editing
        self._table.setEnabled(editable)
        self._add_act.setEnabled(editable)
        self._edit_act.setEnabled(editable)
        self._del_act.setEnabled(editable)
        self._up_btn.setEnabled(editable)
        self._down_btn.setEnabled(editable)
        self._dup_btn.setEnabled(editable)
        # Loop settings
        self._loop_group.setEnabled(editable)
        # Recording
        self._rec_panel.setEnabled(editable)
        # Playback buttons
        self._play_btn.setEnabled(editable)
        self._pause_btn.setEnabled(locked)
        self._stop_btn.setEnabled(locked)

    def _on_engine_started(self) -> None:
        self._set_ui_locked(True)
        self._status_label.setText("▶ Running")
        self.setWindowTitle("▶ Running... — AutoMacro (by TungDo)")
        self._tray.update_state(True, False)
        logger.info("Engine started (%d actions, loop=%s)",
                    len(self._actions),
                    self._loop_spin.value() or '∞')

    def _on_engine_stopped(self) -> None:
        self._set_ui_locked(False)
        self._status_label.setText("⏹ Stopped")
        self._action_label.setText("Idle")
        self._loop_label.setText("")
        self._progress_bar.reset()
        self._tray.update_state(False, False)
        # Reset window title
        name = Path(self._current_file).stem if self._current_file else "New Macro"
        self.setWindowTitle(f"AutoMacro (by TungDo) – {name}")
        # Clear row highlight
        self._table.clearSelection()
        logger.info("Engine stopped")

    def _on_engine_error(self, msg: str) -> None:
        self._status_label.setText(f"⚠ Error: {msg[:80]}")
        logger.error("Engine error: %s", msg)

    def _on_engine_progress(self, current: int, total: int) -> None:
        self._progress_bar.setMaximum(total)
        self._progress_bar.setValue(current)
        # Highlight current action row
        if 0 < current <= self._table.rowCount():
            self._table.selectRow(current - 1)

    def _on_engine_action(self, name: str) -> None:
        self._action_label.setText(f"▶ {name}")
        ts = _dt.datetime.now().strftime("%H:%M:%S")
        self._exec_log.addItem(f"[{ts}] {name}")
        self._exec_log.scrollToBottom()
        # Keep log manageable (max 500 entries)
        while self._exec_log.count() > 500:
            self._exec_log.takeItem(0)

    def _on_engine_loop(self, current: int, total: int) -> None:
        if total < 0:
            self._loop_label.setText(f"Loop: {current} / ∞")
        else:
            self._loop_label.setText(f"Loop: {current} / {total}")

    # ------------------------------------------------------------------ #
    # Action list management
    # ------------------------------------------------------------------ #
    # Icon map for action types
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
        "loop_block": "🔁", "if_image_found": "❓",
    }

    def _refresh_table(self) -> None:
        self._table.blockSignals(True)
        self._table.setSortingEnabled(False)
        self._table.setRowCount(0)                   # clear stale items
        self._table.setRowCount(len(self._actions))
        no_edit = Qt.ItemFlag.ItemIsEditable
        for i, action in enumerate(self._actions):
            # Column 0: row number
            num_item = QTableWidgetItem(str(i + 1))
            num_item.setFlags(num_item.flags() & ~no_edit)
            num_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(i, 0, num_item)

            # Column 1: type icon
            atype = getattr(action, 'ACTION_TYPE', '')
            icon_item = QTableWidgetItem(
                self._TYPE_ICONS.get(atype, '•'))
            icon_item.setFlags(icon_item.flags() & ~no_edit)
            icon_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(i, 1, icon_item)

            # Column 2: display name
            name_item = QTableWidgetItem(action.get_display_name())
            name_item.setFlags(name_item.flags() & ~no_edit)
            self._table.setItem(i, 2, name_item)

            # Column 3: delay
            delay_item = QTableWidgetItem(f"{action.delay_after}ms")
            delay_item.setFlags(delay_item.flags() & ~no_edit)
            delay_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(i, 3, delay_item)

            # Column 4: enabled
            en_item = QTableWidgetItem("✓" if action.enabled else "✗")
            en_item.setFlags(en_item.flags() & ~no_edit)
            en_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(i, 4, en_item)

            # Column 5: description
            desc = action.description or ""
            desc_item = QTableWidgetItem(desc)
            desc_item.setFlags(desc_item.flags() & ~no_edit)
            self._table.setItem(i, 5, desc_item)
        self._table.blockSignals(False)
        # Update empty state overlay
        has_actions = len(self._actions) > 0
        self._table.setVisible(has_actions)
        self._empty_overlay.setVisible(not has_actions)
        # Update stats bar
        self._update_stats()

    def _update_stats(self) -> None:
        """Update action count and estimated runtime in stats bar."""
        total = len(self._actions)
        if total == 0:
            self._stats_label.setText("")
            return
        est_ms = 0
        for a in self._actions:
            est_ms += a.delay_after
            if hasattr(a, 'duration_ms'):
                est_ms += a.duration_ms
        loops = self._loop_spin.value() or 1
        total_ms = est_ms * loops
        self._stats_label.setText(
            f"\ud83d\udcca {total} actions | \u23f1 ~{est_ms / 1000:.1f}s"
            f" | \ud83d\udd04 {loops}\u00d7 = ~{total_ms / 1000:.1f}s")

    def _selected_row(self) -> int:
        sel_model = self._table.selectionModel()
        assert sel_model is not None
        rows = sel_model.selectedRows()
        return rows[0].row() if rows else -1

    def _selected_rows(self) -> list[int]:
        """Return all selected row indices (sorted)."""
        sel_model = self._table.selectionModel()
        assert sel_model is not None
        return sorted(idx.row() for idx in sel_model.selectedRows())

    def _show_context_menu(self, pos: Any) -> None:
        """Right-click context menu for action table."""
        from PyQt6.QtWidgets import QMenu
        vp = self._table.viewport()
        assert vp is not None
        global_pos = vp.mapToGlobal(pos)

        menu = QMenu(self)
        rows = self._selected_rows()
        if not rows:
            add_act = menu.addAction("➕ Add Action")
            assert add_act is not None
            add_act.triggered.connect(self._on_add_action)
            menu.exec(global_pos)
            return

        edit_act = menu.addAction("✏️ Edit")
        assert edit_act is not None
        edit_act.triggered.connect(self._on_edit_action)
        edit_act.setEnabled(len(rows) == 1)

        dup_act = menu.addAction("📋 Duplicate")
        assert dup_act is not None
        dup_act.triggered.connect(self._on_duplicate)
        dup_act.setEnabled(len(rows) == 1)

        copy_act = menu.addAction("📄 Copy (Ctrl+C)")
        assert copy_act is not None
        copy_act.triggered.connect(self._on_copy_actions)

        paste_act = menu.addAction("📥 Paste (Ctrl+V)")
        assert paste_act is not None
        paste_act.triggered.connect(self._on_paste_actions)

        toggle_act = menu.addAction(
            "✗ Disable" if self._actions[rows[0]].enabled else "✓ Enable")
        assert toggle_act is not None
        toggle_act.triggered.connect(self._on_toggle_enabled)

        menu.addSeparator()

        del_act = menu.addAction("🗑️ Delete")
        assert del_act is not None
        del_act.triggered.connect(self._on_delete_action)

        menu.exec(global_pos)

    def _on_toggle_enabled(self) -> None:
        """Toggle enabled/disabled for selected actions."""
        try:
            rows = self._selected_rows()
            if not rows:
                return
            from core.undo_commands import ToggleEnabledCommand
            cmd = ToggleEnabledCommand(self._actions, rows)
            self._undo_stack.push(cmd)
            logger.info("Toggled enabled for %d action(s)", len(rows))
        except Exception:
            logger.exception("Failed to toggle enabled")

    # ------------------------------------------------------------------ #
    # Toolbar handlers
    # ------------------------------------------------------------------ #
    def _on_new(self) -> None:
        if self._actions:
            r = QMessageBox.question(
                self, "New Macro",
                "Discard current macro?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if r != QMessageBox.StandardButton.Yes:
                return
        logger.info("New macro created (cleared %d actions)", len(self._actions))
        self._actions.clear()
        self._current_file = ""
        self._refresh_table()
        self.setWindowTitle("AutoMacro (by TungDo) – New Macro")
        self._autosave.set_current_file(None)
        self._autosave.mark_clean()

    def _on_open(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Macro", self._macro_dir,
            "JSON Macros (*.json);;All Files (*)")
        if not path:
            return
        try:
            self._actions, settings = MacroEngine.load_macro(path)
            self._loop_spin.setValue(settings.get("loop_count", 1))
            self._loop_delay_spin.setValue(
                settings.get("delay_between_loops", 0))
            self._current_file = path
            self._refresh_table()
            name = settings.get("name", Path(path).stem)
            self.setWindowTitle(f"AutoMacro (by TungDo) – {name}")
            self._status_label.setText(f"Opened: {Path(path).name}")
            logger.info("Opened macro: %s (%d actions)", Path(path).name, len(self._actions))
            self._autosave.set_current_file(Path(path))
            self._autosave.mark_clean()
        except Exception as e:
            QMessageBox.critical(
                self, "Lỗi Mở File",
                self._friendly_error_msg(
                    "Không thể mở file macro.", e))

    def _on_save(self) -> None:
        if not self._current_file:
            path, _ = QFileDialog.getSaveFileName(
                self, "Save Macro", self._macro_dir,
                "JSON Macros (*.json)")
            if not path:
                return
            if not path.endswith(".json"):
                path += ".json"
            self._current_file = path

        try:
            MacroEngine.save_macro(
                self._current_file,
                self._actions,
                name=Path(self._current_file).stem,
                loop_count=self._loop_spin.value(),
                loop_delay_ms=self._loop_delay_spin.value(),
            )
            self._status_label.setText(
                f"Saved: {Path(self._current_file).name}")
            logger.info("Saved macro: %s (%d actions)",
                        Path(self._current_file).name, len(self._actions))
            self._autosave.set_current_file(Path(self._current_file))
            self._autosave.mark_clean()
        except Exception as e:
            QMessageBox.critical(
                self, "Lỗi Lưu File",
                self._friendly_error_msg(
                    "Không thể lưu file macro.", e))

    def _on_add_action(self) -> None:
        dialog = ActionEditorDialog(self, macro_dir=self._macro_dir)
        # Use signal instead of get_action() — fires DURING exec() event loop,
        # before any dialog close lifecycle can corrupt the result.
        dialog.action_ready.connect(self._handle_action_added)
        dialog.exec()

    def _handle_action_added(self, action: Any) -> None:
        """Slot: called by ActionEditorDialog.action_ready signal."""
        try:
            row = self._selected_row()
            pos = row + 1 if row >= 0 else len(self._actions)
            from core.undo_commands import AddActionCommand
            cmd = AddActionCommand(self._actions, pos, action)
            self._undo_stack.push(cmd)  # auto-calls redo() → insert
            logger.info("Added action: %s (total: %d)",
                        action.get_display_name(), len(self._actions))
        except Exception:
            logger.exception("Failed to add action")

    def _on_edit_action(self) -> None:
        row = self._selected_row()
        if row < 0:
            return
        action = self._actions[row]
        dialog = ActionEditorDialog(self, action=action,
                                    macro_dir=self._macro_dir)
        # Capture row in closure for the signal handler
        dialog.action_ready.connect(
            lambda new_action, r=row: self._handle_action_edited(r, new_action))
        dialog.exec()

    def _handle_action_edited(self, row: int, new_action: Any) -> None:
        """Slot: called by ActionEditorDialog.action_ready signal."""
        try:
            if row < len(self._actions):
                old_action = self._actions[row]
                from core.undo_commands import EditActionCommand
                cmd = EditActionCommand(self._actions, row,
                                        old_action, new_action)
                self._undo_stack.push(cmd)
                logger.info("Edited action [%d]: %s",
                            row + 1, new_action.get_display_name())
        except Exception:
            logger.exception("Failed to edit action at row %d", row)

    def _on_delete_action(self) -> None:
        rows = self._selected_rows()
        if not rows:
            return

        # Build confirmation message
        if len(rows) == 1:
            msg = f"Delete \"{self._actions[rows[0]].get_display_name()}\"?"
        else:
            msg = f"Delete {len(rows)} selected actions?"

        reply = QMessageBox.question(
            self, "Delete Action", msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            from core.undo_commands import DeleteActionsCommand
            cmd = DeleteActionsCommand(self._actions, rows)
            self._undo_stack.push(cmd)
            logger.info("Deleted %d action(s)", len(rows))

    def _on_move_up(self) -> None:
        try:
            row = self._selected_row()
            if row <= 0:
                return
            from core.undo_commands import MoveActionCommand
            cmd = MoveActionCommand(self._actions, row, row - 1)
            self._undo_stack.push(cmd)
            self._table.selectRow(row - 1)
            logger.info("Moved action [%d] up", row + 1)
        except Exception:
            logger.exception("Failed to move action up")

    def _on_move_down(self) -> None:
        try:
            row = self._selected_row()
            if row < 0 or row >= len(self._actions) - 1:
                return
            from core.undo_commands import MoveActionCommand
            cmd = MoveActionCommand(self._actions, row, row + 1)
            self._undo_stack.push(cmd)
            self._table.selectRow(row + 1)
            logger.info("Moved action [%d] down", row + 1)
        except Exception:
            logger.exception("Failed to move action down")

    def _on_duplicate(self) -> None:
        try:
            row = self._selected_row()
            if row < 0:
                return
            from core.action import Action as BaseAction
            dup = BaseAction.from_dict(self._actions[row].to_dict())
            from core.undo_commands import DuplicateActionCommand
            cmd = DuplicateActionCommand(self._actions, row, dup)
            self._undo_stack.push(cmd)
            logger.info("Duplicated action [%d]", row + 1)
        except Exception:
            logger.exception("Failed to duplicate action")

    def _on_copy_actions(self) -> None:
        """Copy selected actions to clipboard as JSON."""
        try:
            rows = self._selected_rows()
            if not rows:
                return
            data = [self._actions[r].to_dict() for r in sorted(rows)]
            clipboard = QApplication.clipboard()
            assert clipboard is not None
            clipboard.setText(json.dumps(
                {"automacro_actions": data}, indent=2, ensure_ascii=False))
            self._status_label.setText(
                f"📄 Copied {len(rows)} action(s) to clipboard")
            logger.info("Copied %d action(s) to clipboard", len(rows))
        except Exception:
            logger.exception("Failed to copy actions")

    def _on_paste_actions(self) -> None:
        """Paste actions from clipboard JSON."""
        try:
            clipboard = QApplication.clipboard()
            assert clipboard is not None
            text = clipboard.text()
            if not text:
                return
            data = json.loads(text)
            if not isinstance(data, dict) or "automacro_actions" not in data:
                return
            from core.action import Action as BaseAction
            from core.undo_commands import AddBatchCommand
            pasted: list[Action] = []
            for item in data["automacro_actions"]:
                pasted.append(BaseAction.from_dict(item))
            if pasted:
                cmd = AddBatchCommand(self._actions, pasted)
                self._undo_stack.push(cmd)
                self._refresh_table()
                self._status_label.setText(
                    f"📥 Pasted {len(pasted)} action(s)")
                logger.info("Pasted %d action(s) from clipboard", len(pasted))
        except (json.JSONDecodeError, ValueError, KeyError):
            self._status_label.setText("⚠ Clipboard does not contain actions")
        except Exception:
            logger.exception("Failed to paste actions")

    def _on_play(self) -> None:
        if not self._actions:
            self._status_label.setText("No actions to play")
            logger.info("Play blocked: no actions")
            return

        # Guard: check if at least one action is enabled
        enabled_count = sum(1 for a in self._actions if a.enabled)
        if enabled_count == 0:
            self._status_label.setText("⚠ All actions are disabled")
            logger.info("Play blocked: all %d actions disabled",
                        len(self._actions))
            return

        # Auto-save before play to prevent data loss
        if self._current_file and not self._undo_stack.isClean():
            try:
                MacroEngine.save_macro(
                    self._current_file, self._actions,
                    name=Path(self._current_file).stem,
                    loop_count=self._loop_spin.value(),
                    loop_delay_ms=self._loop_delay_spin.value())
                self._undo_stack.setClean()
                logger.info("Auto-saved before play: %s",
                            Path(self._current_file).name)
            except Exception:
                logger.warning("Auto-save before play failed",
                               exc_info=True)

        if self._engine.is_paused:
            self._engine.resume()
            self._status_label.setText("▶ Resumed")
            self._play_btn.setEnabled(False)
            self._tray.update_state(True, False)
            return

        # Async engine lifecycle: stop old, then start new in callback
        if self._engine.isRunning():
            self._engine.stop()
            self._engine.finished.connect(self._start_new_engine)
            return
        self._start_new_engine()

    def _start_new_engine(self) -> None:
        """Create and start a fresh engine (called directly or via signal)."""
        # Disconnect old finished signal if it triggered this
        try:
            self._engine.finished.disconnect(self._start_new_engine)
        except (TypeError, RuntimeError):
            pass
        self._engine = MacroEngine()
        self._connect_engine()
        self._engine.load_actions(self._actions)
        self._engine.set_loop(
            count=self._loop_spin.value(),
            delay_ms=self._loop_delay_spin.value(),
            stop_on_error=self._stop_on_error_check.isChecked(),
        )
        self._engine.set_speed_factor(self._speed_spin.value())
        self._exec_log.clear()
        self._engine.start()
        logger.info("Play started: %d actions, loop=%s, delay=%dms, speed=%.1f×",
                    len(self._actions),
                    self._loop_spin.value() or '∞',
                    self._loop_delay_spin.value(),
                    self._speed_spin.value())

    def _on_pause(self) -> None:
        if self._engine.is_running:
            if self._engine.is_paused:
                self._engine.resume()
                self._status_label.setText("▶ Resumed")
                self._play_btn.setEnabled(False)
                self._tray.update_state(True, False)
            else:
                self._engine.pause()
                self._status_label.setText("⏸ Paused")
                self._play_btn.setEnabled(True)  # allow resume via Play
                self._tray.update_state(True, True)
                logger.info("Paused by user")

    def _on_stop(self) -> None:
        logger.info("Stop requested by user")
        self._engine.stop()

    def _on_capture(self) -> None:
        assets_dir = os.path.join(self._macro_dir, "assets")
        overlay = ImageCaptureOverlay(save_dir=assets_dir, parent=None)
        overlay.image_captured.connect(self._on_image_captured)
        self.hide()
        QTimer.singleShot(300, overlay.start)
        logger.info("Image capture started")

    def _on_image_captured(self, path: str) -> None:
        self.show()
        self._status_label.setText(f"Captured: {Path(path).name}")
        logger.info("Image captured: %s", Path(path).name)

    def _on_pick_coordinate(self) -> None:
        """Launch standalone coordinate picker from toolbar."""
        self._coord_picker = CoordinatePickerOverlay()
        self._coord_picker.coordinate_picked.connect(self._on_coord_picked)
        self._coord_picker.cancelled.connect(self._on_coord_cancelled)
        self.hide()
        QTimer.singleShot(200, self._coord_picker.start)

    def _on_coord_picked(self, x: int, y: int) -> None:
        """Handle coordinate picked — show in status bar & copy to clipboard."""
        self.show()
        self.activateWindow()
        coord_text = f"X: {x}  Y: {y}"
        self._status_label.setText(f"🎯 {coord_text} (copied to clipboard)")
        clipboard = QApplication.clipboard()
        assert clipboard is not None
        clipboard.setText(f"{x}, {y}")
        logger.info("Coordinate picked: %d, %d", x, y)

    def _on_coord_cancelled(self) -> None:
        self.show()
        self.activateWindow()

    def _on_recording_done(self, actions: list[Action]) -> None:
        try:
            if actions:
                from core.undo_commands import AddBatchCommand
                cmd = AddBatchCommand(self._actions, actions)
                self._undo_stack.push(cmd)
                self._status_label.setText(
                    f"Added {len(actions)} recorded actions")
                logger.info("Recording finished: %d actions added (total: %d)",
                            len(actions), len(self._actions))
        except Exception:
            logger.exception("Failed to process recorded actions")

    def _on_settings(self) -> None:
        dialog = SettingsDialog(self._config, self)
        dialog.config_saved.connect(self._handle_settings_saved)
        dialog.exec()

    def _handle_settings_saved(self, config: Any) -> None:
        """Slot: called by SettingsDialog.config_saved signal."""
        try:
            self._config = config
            save_config(self._config)
            self._status_label.setText("Settings saved")
            logger.info("Settings saved")
        except Exception:
            logger.exception("Failed to save settings")

    def _update_ram_display(self) -> None:
        """Update RAM usage in status bar."""
        try:
            from core.memory_manager import MemoryManager
            stats = MemoryManager.instance().get_stats()
            self._ram_label.setText(
                f"RAM: {stats['current_mb']}MB (peak: {stats['peak_mb']}MB)")
        except Exception:
            pass

    def _on_about(self) -> None:
        import platform
        app_inst = QApplication.instance()
        qt_ver = app_inst.applicationVersion() if app_inst else 'PyQt6'
        QMessageBox.about(
            self,
            f"About {__app_name__}",
            f"<h2>{__app_name__} (by {__author__})</h2>"
            f"<p><b>Auto Mouse & Keyboard with Image Recognition</b></p>"
            f"<p>Version: {__version__}</p>"
            f"<p>Build: {__build_date__}</p>"
            f"<hr>"
            f"<p>OS: {platform.system()} {platform.release()}<br>"
            f"Python: {platform.python_version()}<br>"
            f"Qt: {qt_ver or 'PyQt6'}</p>"
            f"<hr>"
            f"<p>Designed for 24/7 automation.</p>"
        )

    def _on_quit(self) -> None:
        self._engine.stop()
        self._tray.hide()
        QApplication.quit()

    # ------------------------------------------------------------------ #
    # Window events
    # ------------------------------------------------------------------ #
    def _show_from_tray(self) -> None:
        self.showNormal()
        self.activateWindow()

    def closeEvent(self, event: Optional[QCloseEvent]) -> None:
        if self._config.get("ui", {}).get("minimize_to_tray", True):
            if event:
                event.ignore()
            self.hide()
            self._tray.show_message(
                "AutoMacro", "Minimized to tray. Double-click to open.")
        else:
            # Guard: prompt if unsaved changes exist
            if not self._undo_stack.isClean():
                reply = QMessageBox.question(
                    self, "Thay Đổi Chưa Lưu",
                    "Bạn có thay đổi chưa lưu. Lưu trước khi thoát?",
                    QMessageBox.StandardButton.Save |
                    QMessageBox.StandardButton.Discard |
                    QMessageBox.StandardButton.Cancel)
                if reply == QMessageBox.StandardButton.Save:
                    self._on_save()
                elif reply == QMessageBox.StandardButton.Cancel:
                    if event:
                        event.ignore()
                    return
            self._autosave.stop()
            self._on_quit()
