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
from typing import Any, Optional

from PyQt6.QtCore import QObject, QSize, Qt, QTimer
from PyQt6.QtGui import QAction as QMenuAction
from PyQt6.QtGui import QCloseEvent, QKeySequence, QUndoStack
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QStatusBar,
    QTableWidgetItem,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from core.action import Action
from core.engine import MacroEngine
from gui.action_editor import ActionEditorDialog
from gui.coordinate_picker import CoordinatePickerOverlay
from gui.help_dialog import HelpDialog
from gui.image_capture import ImageCaptureOverlay
from gui.recording_panel import RecordingPanel
from gui.settings_dialog import SettingsDialog, load_config, save_config
from gui.styles import get_theme
from gui.tray import TrayManager
from version import __app_name__, __author__, __build_date__, __version__

logger = logging.getLogger(__name__)

# Ensure modules are registered
import core.scheduler  # noqa: F401
import modules.image  # noqa: F401
import modules.keyboard  # noqa: F401
import modules.mouse  # noqa: F401
import modules.pixel  # noqa: F401
import modules.system  # noqa: F401
from core.autosave import AutoSaveManager


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
        cfg = load_config()
        theme_pref = cfg.get("theme", "auto")
        self.setStyleSheet(get_theme(theme_pref))

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
                self._current_file,
                self._actions,
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
        if getattr(self, "_refreshing", False):
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
        """Build the main toolbar with action buttons."""
        # --- Row 1: File & Edit actions ---
        tb = QToolBar("File & Edit")
        tb.setIconSize(QSize(20, 20))
        tb.setMovable(False)
        self.addToolBar(tb)

        new_act = QMenuAction("📄 Mới", self)
        new_act.setShortcut(QKeySequence("Ctrl+N"))
        new_act.setToolTip("Tạo macro mới (Ctrl+N)")
        new_act.triggered.connect(self._on_new)
        tb.addAction(new_act)

        open_act = QMenuAction("📂 Mở", self)
        open_act.setShortcut(QKeySequence("Ctrl+O"))
        open_act.setToolTip("Mở file macro (Ctrl+O)")
        open_act.triggered.connect(self._on_open)
        tb.addAction(open_act)

        # Recent Files dropdown (P2 #5)
        from PyQt6.QtWidgets import QMenu as QRecentMenu
        from PyQt6.QtWidgets import QToolButton

        self._recent_btn = QToolButton()
        self._recent_btn.setText("📋 Gần đây")
        self._recent_btn.setToolTip("Mở macro gần đây")
        self._recent_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._recent_menu = QRecentMenu(self)
        self._recent_btn.setMenu(self._recent_menu)
        self._build_recent_menu()
        tb.addWidget(self._recent_btn)

        save_act = QMenuAction("💾 Lưu", self)
        save_act.setShortcut(QKeySequence("Ctrl+S"))
        save_act.setToolTip("Lưu macro hiện tại (Ctrl+S)")
        save_act.triggered.connect(self._on_save)
        tb.addAction(save_act)

        undo_act = self._undo_stack.createUndoAction(self, "↩ Hoàn tác")
        undo_act.setShortcut(QKeySequence.StandardKey.Undo)  # type: ignore[union-attr]
        tb.addAction(undo_act)

        redo_act = self._undo_stack.createRedoAction(self, "↪ Làm lại")
        redo_act.setShortcut(QKeySequence.StandardKey.Redo)  # type: ignore[union-attr]
        tb.addAction(redo_act)

        tb.addSeparator()

        self._add_act = QMenuAction("➕ Thêm", self)
        self._add_act.setToolTip("Thêm action mới")
        self._add_act.triggered.connect(self._on_add_action)
        tb.addAction(self._add_act)

        self._edit_act = QMenuAction("✏️ Sửa", self)
        self._edit_act.setToolTip("Sửa action đang chọn")
        self._edit_act.triggered.connect(self._on_edit_action)
        tb.addAction(self._edit_act)

        self._del_act = QMenuAction("🗑️ Xóa", self)
        self._del_act.setShortcut(QKeySequence.StandardKey.Delete)
        self._del_act.setToolTip("Xóa action (Delete)")
        self._del_act.triggered.connect(self._on_delete_action)
        tb.addAction(self._del_act)

        tb.addSeparator()

        # Tools
        capture_act = QMenuAction("📸 Chụp", self)
        capture_act.setToolTip("Chụp vùng màn hình làm ảnh mẫu")
        capture_act.triggered.connect(self._on_capture)
        tb.addAction(capture_act)

        coord_act = QMenuAction("🎯 Tọa độ", self)
        coord_act.setShortcut(QKeySequence("Ctrl+G"))
        coord_act.setToolTip("Chọn tọa độ từ màn hình (Ctrl+G)\n" "Click bất kỳ → X,Y hiển thị trên thanh trạng thái")
        coord_act.triggered.connect(self._on_pick_coordinate)
        tb.addAction(coord_act)

        settings_act = QMenuAction("⚙ Cài đặt", self)
        settings_act.setToolTip("Mở cài đặt ứng dụng")
        settings_act.triggered.connect(self._on_settings)
        tb.addAction(settings_act)

        about_act = QMenuAction("ℹ️ Giới thiệu", self)
        about_act.setToolTip("Thông tin ứng dụng")
        about_act.triggered.connect(self._on_about)
        tb.addAction(about_act)

        help_act = QMenuAction("📖 Hướng dẫn", self)
        help_act.setShortcut(QKeySequence("F1"))
        help_act.setToolTip("Mở hướng dẫn sử dụng (F1)")
        help_act.triggered.connect(self._on_help)
        tb.addAction(help_act)

        tb.addSeparator()

        # Templates button
        template_act = QMenuAction("📦 Mẫu", self)
        template_act.setToolTip("Chèn macro mẫu (template)")
        template_act.triggered.connect(self._on_insert_template)
        tb.addAction(template_act)

        # Smart Hints button
        hints_act = QMenuAction("💡 Gợi ý", self)
        hints_act.setToolTip("Phân tích macro và hiển thị gợi ý")
        hints_act.triggered.connect(self._on_show_hints)
        tb.addAction(hints_act)

    # ------------------------------------------------------------------ #
    # Central Widget
    # ------------------------------------------------------------------ #
    def _setup_central(self) -> None:
        """Build the central widget: action table + tree + log panel."""
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(8, 8, 8, 8)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: Action List Panel (extracted — 1.1b)
        from gui.panels.action_list_panel import ActionListPanel

        self._action_list_panel = ActionListPanel(self._actions)
        self._action_list_panel.edit_requested.connect(self._on_edit_action)
        self._action_list_panel.context_menu_requested.connect(self._show_context_menu)
        self._action_list_panel.move_up_requested.connect(self._on_move_up)
        self._action_list_panel.move_down_requested.connect(self._on_move_down)
        self._action_list_panel.duplicate_requested.connect(self._on_duplicate)
        self._action_list_panel.copy_requested.connect(self._on_copy_actions)
        self._action_list_panel.paste_requested.connect(self._on_paste_actions)
        self._action_list_panel.filter_changed.connect(self._on_filter_changed)
        self._action_list_panel.view_mode_changed.connect(self._toggle_view_mode)

        # Backward-compat aliases for existing code references
        self._table = self._action_list_panel.table
        self._tree = self._action_list_panel.tree
        self._tree_model = self._action_list_panel.tree_model
        self._filter_edit = self._action_list_panel.filter_edit
        self._stats_label = self._action_list_panel.stats_label
        self._empty_overlay = self._action_list_panel.empty_overlay
        self._up_btn = self._action_list_panel._up_btn
        self._down_btn = self._action_list_panel._down_btn
        self._dup_btn = self._action_list_panel._dup_btn
        self._copy_btn = self._action_list_panel._copy_btn
        self._paste_btn = self._action_list_panel._paste_btn
        self._view_toggle_btn = self._action_list_panel._view_toggle_btn
        self._tree_mode = False

        # Drag-drop undo: snapshot order before drop
        self._pre_drag_order: list[Action] = []
        self._table.viewport().installEventFilter(self)  # type: ignore[union-attr]

        splitter.addWidget(self._action_list_panel)

        # Right panel
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        # ── 1. Playback controls (extracted panel) ─────────────
        from gui.panels.playback_panel import PlaybackPanel

        self._playback_panel = PlaybackPanel()
        self._playback_panel.play_requested.connect(self._on_play)
        self._playback_panel.pause_requested.connect(self._on_pause)
        self._playback_panel.stop_requested.connect(self._on_stop)
        self._playback_panel.step_toggled.connect(self._on_step_toggle)
        self._playback_panel.step_next_requested.connect(self._on_step_next)
        self._playback_panel.speed_changed.connect(self._on_speed_changed)
        right_layout.addWidget(self._playback_panel)

        # Backward-compat aliases for code that references old widgets
        self._play_btn = self._playback_panel._play_btn
        self._pause_btn = self._playback_panel._pause_btn
        self._stop_btn = self._playback_panel._stop_btn
        self._step_toggle = self._playback_panel._step_toggle
        self._step_next_btn = self._playback_panel._step_next_btn
        self._loop_spin = self._playback_panel._loop_spin
        self._loop_delay_spin = self._playback_panel._loop_delay_spin
        self._loop_group = self._playback_panel._loop_group
        self._stop_on_error_check = self._playback_panel._stop_on_error_check
        self._speed_spin = self._playback_panel._speed_spin

        # ── 2. Recording panel ────────────────────────────────
        self._rec_panel = RecordingPanel()
        self._rec_panel.recording_finished.connect(self._on_recording_done)
        self._rec_panel.recording_state_changed.connect(self._on_recording_state_changed)
        self._rec_panel.update_hotkeys(self._config)
        right_layout.addWidget(self._rec_panel)

        # ── 3. Execution panel (extracted) ─────────────────────
        from gui.panels.execution_panel import ExecutionPanel

        self._exec_panel = ExecutionPanel()
        right_layout.addWidget(self._exec_panel)
        # Backward-compat aliases
        self._action_label = self._exec_panel._action_label
        self._progress_bar = self._exec_panel._progress_bar
        self._loop_label = self._exec_panel._loop_label
        self._exec_log = self._exec_panel._exec_log

        # ── 4. Variable Inspector (extracted) ──────────────────
        from gui.panels.variable_panel import VariablePanel

        self._var_panel = VariablePanel()
        right_layout.addWidget(self._var_panel)
        # Backward-compat aliases
        self._var_group = self._var_panel._group
        self._var_table = self._var_panel._var_table
        self._var_timer = self._var_panel._timer

        # ── 5. Mini-Map (Phase 3) ──────────────────────────────
        from gui.panels.minimap_panel import MiniMapWidget

        self._minimap = MiniMapWidget()
        self._minimap.action_clicked.connect(
            lambda idx: self._table.selectRow(idx) if 0 <= idx < self._table.rowCount() else None
        )
        right_layout.addWidget(self._minimap)

        right_layout.addStretch()

        splitter.addWidget(right_widget)
        splitter.setSizes([600, 300])

        # ── Vertical splitter: content on top, log panel on bottom ──
        v_splitter = QSplitter(Qt.Orientation.Vertical)
        v_splitter.addWidget(splitter)

        # ── 5. Log panel (extracted) ───────────────────────────
        from gui.panels.log_panel import LogPanel

        self._log_panel = LogPanel()
        v_splitter.addWidget(self._log_panel)
        # Backward-compat aliases
        self._app_log = self._log_panel._app_log

        v_splitter.setSizes([500, 150])
        v_splitter.setCollapsible(1, True)  # log panel collapsible

        layout.addWidget(v_splitter)

        # ── 3.6: Keyboard UX shortcuts ─────────────────────────
        self._setup_keyboard_ux()

    # ------------------------------------------------------------------ #
    # Keyboard UX (3.6)
    # ------------------------------------------------------------------ #
    def _setup_keyboard_ux(self) -> None:
        """Add keyboard shortcuts for power users."""
        from PyQt6.QtGui import QKeySequence, QShortcut

        # Enter on table = Edit selected action
        enter_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Return), self._table)
        enter_shortcut.activated.connect(self._on_edit_action)

        # Space on table = Toggle enable/disable
        space_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Space), self._table)
        space_shortcut.activated.connect(self._on_toggle_selected)

        # Escape = Focus back to action table
        esc_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        esc_shortcut.activated.connect(lambda: self._table.setFocus())

        # Delete key = Delete selected actions
        del_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Delete), self._table)
        del_shortcut.activated.connect(self._on_delete_action)

        # Ctrl+Enter = Run from selected action (3.6b)
        ctrl_enter = QShortcut(QKeySequence("Ctrl+Return"), self._table)
        ctrl_enter.activated.connect(self._on_run_from_selected)

        # Tab order: table → playback → recording → log
        QWidget.setTabOrder(self._table, self._playback_panel)
        QWidget.setTabOrder(self._playback_panel, self._rec_panel)
        QWidget.setTabOrder(self._rec_panel, self._log_panel)

    def _on_toggle_selected(self) -> None:
        """Toggle enable/disable for selected actions (Space key)."""
        # Sub-action support in tree mode
        node = self._get_tree_selected_node()
        if node and node.parent is not None:
            from core.undo_commands import CompositeChildrenCommand

            parent_action = node.parent.action
            cmd = CompositeChildrenCommand(parent_action, f"Toggle {node.action.get_display_name()}")
            node.action.enabled = not node.action.enabled
            cmd.capture_new_state()
            self._undo_stack.push(cmd)
            self._refresh_table()
            return
        rows = self._selected_rows()
        if not rows:
            return
        for r in rows:
            if 0 <= r < len(self._actions):
                self._actions[r].enabled = not self._actions[r].enabled
        self._refresh_table()
        logger.info("Toggled %d action(s)", len(rows))

    def _on_run_from_selected(self) -> None:
        """Run macro starting from the selected action (Ctrl+Enter)."""
        rows = self._selected_rows()
        if not rows:
            return
        start_idx = min(rows)
        if 0 <= start_idx < len(self._actions):
            self._engine._resume_from_idx = start_idx
            self._on_play()
            logger.info("Running from action #%d", start_idx + 1)

    # ------------------------------------------------------------------ #
    # Theme Hot-Swap (3.5)
    # ------------------------------------------------------------------ #
    def _apply_theme_live(self, theme_pref: str, font_size: int = 0) -> None:
        """Apply theme immediately to all widgets."""
        if font_size > 0:
            qss = get_theme(theme_pref, font_size=font_size)
        else:
            qss = get_theme(theme_pref)
        self.setStyleSheet(qss)
        # 1.2: Notify via Event Bus
        from core.event_bus import AppEventBus

        AppEventBus.instance().theme_changed.emit(theme_pref)
        logger.info("Theme applied: %s", theme_pref)

    # ------------------------------------------------------------------ #
    # Smart Hints (3.3)
    # ------------------------------------------------------------------ #
    def _on_show_hints(self) -> None:
        """Analyze macro and show contextual hints."""
        from core.smart_hints import analyze_hints

        hints = analyze_hints(self._actions)
        if not hints:
            QMessageBox.information(self, "💡 Gợi ý", "✅ Macro trông tốt! Không có gợi ý nào.")
            return

        # Build rich hint text
        lines = []
        for h in hints:
            icon = h.get("icon", "•")
            msg = h.get("message", "")
            lines.append(f"{icon} {msg}")

        text = "\n\n".join(lines)
        QMessageBox.information(self, f"💡 Gợi ý ({len(hints)} mục)", text)

    # ------------------------------------------------------------------ #
    # Templates (4.2)
    # ------------------------------------------------------------------ #
    def _on_insert_template(self) -> None:
        """Show template selection dialog and insert chosen template."""
        from PyQt6.QtWidgets import QInputDialog

        from core.macro_templates import create_actions_from_template, get_templates

        templates = get_templates()
        if not templates:
            QMessageBox.information(self, "📦 Mẫu", "Không có template nào.")
            return

        display_names = [t["name"] for t in templates]

        name, ok = QInputDialog.getItem(self, "📦 Chọn Template", "Chọn macro mẫu để chèn:", display_names, 0, False)

        if not ok or not name:
            return

        # Find matching template
        idx = display_names.index(name)
        template = templates[idx]
        new_actions = create_actions_from_template(template)

        if not new_actions:
            QMessageBox.warning(self, "⚠ Lỗi", "Không tạo được action từ template.")
            return

        # Append to current action list
        self._actions.extend(new_actions)
        self._refresh_table()
        self._mark_dirty()
        logger.info("Inserted template '%s' with %d actions", template["name"], len(new_actions))
        self._status_label.setText(f"✅ Đã chèn {len(new_actions)} actions từ template")

    # ------------------------------------------------------------------ #
    # Status Bar
    # ------------------------------------------------------------------ #
    def _setup_statusbar(self) -> None:
        """Build the status bar with stats and memory labels."""
        self._statusbar = QStatusBar()
        self.setStatusBar(self._statusbar)
        self._status_label = QLabel("Sẵn sàng")
        self._statusbar.addWidget(self._status_label)

        self._ram_label = QLabel("RAM: --")
        self._ram_label.setObjectName("subtitleLabel")
        self._statusbar.addPermanentWidget(self._ram_label)

        self._hotkey_label = QLabel(
            f"  Chạy: {self._config['hotkeys']['start_stop']}  |  "
            f"Dừng tạm: {self._config['hotkeys']['pause_resume']}  |  "
            f"Dừng: {self._config['hotkeys']['emergency_stop']}  |  "
            f"Ghi: {self._config['hotkeys'].get('record', 'F9')}"
        )
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
        """Initialize the system tray icon and menu."""
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
    def eventFilter(self, obj: QObject, event: Any) -> bool:  # type: ignore[override]
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
                try:
                    idx = int(item.text()) - 1  # "#" column = 1-based
                except (ValueError, TypeError):
                    continue  # skip if column shifted after drag
                if 0 <= idx < len(self._pre_drag_order):
                    new_order.append(self._pre_drag_order[idx])
        if len(new_order) == len(self._pre_drag_order) and new_order != self._pre_drag_order:
            from core.undo_commands import ReorderActionsCommand

            cmd = ReorderActionsCommand(self._actions, self._pre_drag_order, new_order)
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
        """Wire engine signals to UI callback slots."""
        self._engine.started_signal.connect(self._on_engine_started)
        self._engine.stopped_signal.connect(self._on_engine_stopped)
        self._engine.error_signal.connect(self._on_engine_error)
        self._engine.progress_signal.connect(self._on_engine_progress)
        self._engine.action_signal.connect(self._on_engine_action)
        self._engine.loop_signal.connect(self._on_engine_loop)
        self._engine.step_signal.connect(self._on_engine_step)
        # 1.2: Bridge engine signals to Event Bus
        from core.event_bus import AppEventBus

        AppEventBus.instance().bridge_engine(self._engine)

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
        """Handle engine start: lock UI, show running status."""
        self._set_ui_locked(True)
        self._status_label.setText("▶ Đang chạy")
        self.setWindowTitle("▶ Đang chạy... — AutoMacro (by TungDo)")
        self._tray.update_state(True, False)
        self._var_timer.start()  # 2.1: start variable inspector
        self._var_group.setVisible(True)  # auto-show inspector
        self._step_next_btn.setEnabled(self._step_toggle.isChecked())
        # Phase 3: setup mini-map for execution tracking
        if hasattr(self, "_minimap"):
            self._minimap.set_actions(self._actions)
        logger.info("Engine started (%d actions, loop=%s)", len(self._actions), self._loop_spin.value() or "∞")

    def _on_engine_stopped(self) -> None:
        """Handle engine stop: unlock UI, reset status."""
        self._set_ui_locked(False)
        self._status_label.setText("⏹ Đã dừng")
        self._action_label.setText("Đang chờ")
        self._loop_label.setText("")
        self._progress_bar.reset()
        self._tray.update_state(False, False)
        self._var_timer.stop()  # 2.1: stop variable inspector
        self._var_group.setVisible(False)  # auto-hide inspector
        self._step_next_btn.setEnabled(False)
        # Reset window title
        name = Path(self._current_file).stem if self._current_file else "Macro mới"
        self.setWindowTitle(f"AutoMacro (by TungDo) – {name}")
        # Clear row highlight
        self._table.clearSelection()
        # Phase 3: reset mini-map
        if hasattr(self, "_minimap"):
            self._minimap.reset()
        logger.info("Engine stopped")

    def _on_engine_error(self, msg: str) -> None:
        """Handle engine error: show warning dialog."""
        self._status_label.setText(f"⚠ Lỗi: {msg[:80]}")
        logger.error("Engine error: %s", msg)
        # P1 #2: Error popup — chủ động thông báo, không để user phải tự phát hiện
        QMessageBox.warning(self, "⚠ Lỗi thực thi", f"Macro gặp lỗi:\n\n{msg}\n\n" "Kiểm tra action và thử lại.")

    def _on_engine_progress(self, current: int, total: int) -> None:
        """Update progress bar with current step."""
        self._progress_bar.setMaximum(total)
        self._progress_bar.setValue(current)
        # Highlight current action row
        if 0 < current <= self._table.rowCount():
            self._table.selectRow(current - 1)
        # Phase 3: update mini-map highlighting
        if hasattr(self, "_minimap"):
            self._minimap.highlight_action(current - 1)

    def _on_engine_action(self, name: str) -> None:
        """Display the currently executing action name."""
        self._action_label.setText(f"▶ {name}")
        ts = _dt.datetime.now().strftime("%H:%M:%S")
        self._exec_log.addItem(f"[{ts}] {name}")
        self._exec_log.scrollToBottom()
        # Keep log manageable (max 500 entries)
        while self._exec_log.count() > 500:
            self._exec_log.takeItem(0)

    def _on_engine_loop(self, current: int, total: int) -> None:
        """Display current loop iteration count."""
        if total < 0:
            self._loop_label.setText(f"Vòng lặp: {current} / ∞")
        else:
            self._loop_label.setText(f"Vòng lặp: {current} / {total}")

    # ------------------------------------------------------------------ #
    # Action list management
    # ------------------------------------------------------------------ #
    # Icon map for action types
    _TYPE_ICONS: dict[str, str] = {
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
        "check_pixel_color": "🎨",
        "wait_for_color": "🎨",
        "loop_block": "🔁",
        "if_image_found": "❓",
        "if_pixel_color": "🎯",
        "if_variable": "📏",
        "set_variable": "📊",
        "split_string": "✂️",
        "comment": "💬",
        "activate_window": "🖥",
        "log_to_file": "📝",
        "read_clipboard": "📋",
        "read_file_line": "📂",
        "write_to_file": "💾",
        "secure_type_text": "🔒",
        "run_macro": "▶️",
        "capture_text": "🔍",
    }

    def _refresh_table(self) -> None:
        """Rebuild the action table/tree from the _actions list."""
        self._table.blockSignals(True)
        self._table.setSortingEnabled(False)
        self._table.setRowCount(0)  # clear stale items
        self._table.setRowCount(len(self._actions))
        no_edit = Qt.ItemFlag.ItemIsEditable
        for i, action in enumerate(self._actions):
            # Column 0: row number
            num_item = QTableWidgetItem(str(i + 1))
            num_item.setFlags(num_item.flags() & ~no_edit)
            num_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(i, 0, num_item)

            # Column 1: type icon
            atype = getattr(action, "ACTION_TYPE", "")
            icon_item = QTableWidgetItem(self._TYPE_ICONS.get(atype, "•"))
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
        self._table.setVisible(has_actions and not self._tree_mode)
        self._tree.setVisible(has_actions and self._tree_mode)
        self._empty_overlay.setVisible(not has_actions)
        # v3.0: sync tree model
        if hasattr(self, "_tree_model"):
            self._tree_model.rebuild()
            if self._tree_mode:
                self._tree.expandAll()
        # Re-apply filter if active
        if hasattr(self, "_filter_edit") and self._filter_edit.text():
            self._on_filter_changed(self._filter_edit.text())
        # Update stats bar
        self._update_stats()
        # Phase 3: sync mini-map
        if hasattr(self, "_minimap"):
            self._minimap.set_actions(self._actions)

    def _toggle_view_mode(self, checked: bool) -> None:
        """v3.0: Switch between flat table and hierarchical tree view."""
        self._tree_mode = checked
        has_actions = len(self._actions) > 0
        self._table.setVisible(has_actions and not self._tree_mode)
        self._tree.setVisible(has_actions and self._tree_mode)
        if self._tree_mode:
            self._tree_model.rebuild()
            self._tree.expandAll()
            self._view_toggle_btn.setText("📋 Chế độ Bảng")
        else:
            self._refresh_table()
            self._view_toggle_btn.setText("🌳 Chế độ Cây")
        logger.info("View mode: %s", "tree" if self._tree_mode else "table")

    def _on_filter_changed(self, text: str) -> None:
        """Filter table rows by action name or description (P2 #4)."""
        needle = text.strip().lower()
        for row in range(self._table.rowCount()):
            if not needle:
                self._table.setRowHidden(row, False)
                continue
            name_item = self._table.item(row, 2)
            desc_item = self._table.item(row, 5)
            name = name_item.text().lower() if name_item else ""
            desc = desc_item.text().lower() if desc_item else ""
            self._table.setRowHidden(row, needle not in name and needle not in desc)

    def _update_stats(self) -> None:
        """Update action count and estimated runtime in stats bar."""
        total = len(self._actions)
        if total == 0:
            self._stats_label.setText("")
            return
        est_ms = 0
        for a in self._actions:
            est_ms += a.delay_after
            if hasattr(a, "duration_ms"):
                est_ms += a.duration_ms
        loops = self._loop_spin.value() or 1
        total_ms = est_ms * loops
        self._stats_label.setText(
            f"\ud83d\udcca {total} actions | \u23f1 ~{est_ms / 1000:.1f}s"
            f" | \ud83d\udd04 {loops}\u00d7 = ~{total_ms / 1000:.1f}s"
        )

    def _selected_row(self) -> int:
        """Return the single selected row index, or -1."""
        if self._tree_mode:
            sel = self._tree.selectionModel()
            if sel is None:
                return -1
            indexes = sel.selectedRows()
            if not indexes:
                return -1
            idx = indexes[0]
            if idx.parent().isValid():
                return -1  # Nested child — not a root-level action
            return idx.row()
        sel_model = self._table.selectionModel()
        assert sel_model is not None
        rows = sel_model.selectedRows()
        return rows[0].row() if rows else -1

    def _selected_rows(self) -> list[int]:
        """Return all selected row indices (sorted). Root-level only."""
        if self._tree_mode:
            sel = self._tree.selectionModel()
            if sel is None:
                return []
            return sorted(idx.row() for idx in sel.selectedRows() if not idx.parent().isValid())
        sel_model = self._table.selectionModel()
        assert sel_model is not None
        return sorted(idx.row() for idx in sel_model.selectedRows())

    def _get_tree_selected_node(self):
        """Return the tree node for the selected item (root or nested).

        Returns None if not in tree mode or nothing selected.
        """
        if not self._tree_mode:
            return None
        sel = self._tree.selectionModel()
        if sel is None:
            return None
        indexes = sel.selectedRows()
        if not indexes:
            return None
        idx = indexes[0]
        return self._tree_model.node_at(idx)

    def _show_context_menu(self, pos: Any) -> None:
        """Right-click context menu for action table/tree.

        Supports both root-level and nested sub-actions in tree mode.
        """
        from PyQt6.QtWidgets import QMenu

        if self._tree_mode:
            vp = self._tree.viewport()
        else:
            vp = self._table.viewport()
        assert vp is not None
        global_pos = vp.mapToGlobal(pos)

        menu = QMenu(self)

        # ── Tree mode: check if a sub-action is selected ──
        if self._tree_mode:
            sel = self._tree.selectionModel()
            selected_indexes = sel.selectedRows() if sel else []
            if selected_indexes:
                idx = selected_indexes[0]
                node = self._tree_model.node_at(idx)
                if node and idx.parent().isValid():
                    # This is a SUB-ACTION (nested inside a composite)
                    self._show_sub_action_context_menu(menu, global_pos, node, idx)
                    return

        # ── Standard context menu for root-level actions ──
        rows = self._selected_rows()
        if not rows:
            add_act = menu.addAction("➕ Thêm Action")
            assert add_act is not None
            add_act.triggered.connect(self._on_add_action)
            menu.exec(global_pos)
            return

        edit_act = menu.addAction("✏️ Sửa")
        assert edit_act is not None
        edit_act.triggered.connect(self._on_edit_action)
        edit_act.setEnabled(len(rows) == 1)

        dup_act = menu.addAction("📋 Nhân bản")
        assert dup_act is not None
        dup_act.triggered.connect(self._on_duplicate)
        dup_act.setEnabled(len(rows) == 1)

        copy_act = menu.addAction("📄 Sao chép (Ctrl+C)")
        assert copy_act is not None
        copy_act.triggered.connect(self._on_copy_actions)

        paste_act = menu.addAction("📥 Dán (Ctrl+V)")
        assert paste_act is not None
        paste_act.triggered.connect(self._on_paste_actions)

        toggle_act = menu.addAction("✗ Tắt" if self._actions[rows[0]].enabled else "✓ Bật")
        assert toggle_act is not None
        toggle_act.triggered.connect(self._on_toggle_enabled)

        # Composite sub-action items (LoopBlock, If*)
        if len(rows) == 1:
            action = self._actions[rows[0]]
            if action.is_composite:
                menu.addSeparator()
                if action.has_branches:
                    add_then = menu.addAction("➕ Thêm vào THEN")
                    assert add_then is not None
                    add_then.triggered.connect(lambda checked=False, r=rows[0]: self._add_sub_action(r, "then"))
                    add_else = menu.addAction("➕ Thêm vào ELSE")
                    assert add_else is not None
                    add_else.triggered.connect(lambda checked=False, r=rows[0]: self._add_sub_action(r, "else"))
                else:
                    add_child = menu.addAction("➕ Thêm sub-action")
                    assert add_child is not None
                    add_child.triggered.connect(lambda checked=False, r=rows[0]: self._add_sub_action(r, "children"))

        menu.addSeparator()

        del_act = menu.addAction("🗑️ Xóa")
        assert del_act is not None
        del_act.triggered.connect(self._on_delete_action)

        menu.exec(global_pos)

    def _show_sub_action_context_menu(self, menu, global_pos, node, idx) -> None:
        """Context menu for a sub-action (nested inside composite) in tree view."""
        action = node.action

        # Edit sub-action
        edit_act = menu.addAction("✏️ Sửa sub-action")
        assert edit_act is not None
        edit_act.triggered.connect(lambda checked=False, n=node: self._edit_sub_action(n))

        # Toggle enable/disable
        toggle_label = "✗ Tắt" if action.enabled else "✓ Bật"
        toggle_act = menu.addAction(toggle_label)
        assert toggle_act is not None

        def _toggle(checked=False, a=action):
            a.enabled = not a.enabled
            self._refresh_table()

        toggle_act.triggered.connect(_toggle)

        # If this sub-action is itself composite, show THEN/ELSE/sub-action options
        if action.is_composite:
            menu.addSeparator()
            if action.has_branches:
                add_then = menu.addAction("➕ Thêm vào THEN")
                assert add_then is not None
                add_then.triggered.connect(lambda checked=False, a=action: self._add_nested_sub_action(a, "then"))
                add_else = menu.addAction("➕ Thêm vào ELSE")
                assert add_else is not None
                add_else.triggered.connect(lambda checked=False, a=action: self._add_nested_sub_action(a, "else"))
            else:
                add_child = menu.addAction("➕ Thêm sub-action")
                assert add_child is not None
                add_child.triggered.connect(lambda checked=False, a=action: self._add_nested_sub_action(a, "children"))

        menu.addSeparator()

        # Delete sub-action
        del_act = menu.addAction("🗑️ Xóa sub-action")
        assert del_act is not None
        del_act.triggered.connect(lambda checked=False, n=node: self._delete_sub_action(n))

        menu.exec(global_pos)

    def _edit_sub_action(self, node) -> None:
        """Edit a nested sub-action via ActionEditor dialog."""
        action = node.action
        parent_node = node.parent
        if not parent_node:
            return

        dialog = ActionEditorDialog(self, action=action, macro_dir=self._macro_dir)

        def _handle_edited(new_action):
            try:
                parent_action = parent_node.action
                branch = node.branch_label  # "THEN", "ELSE", or ""
                row = node.row

                from core.undo_commands import CompositeChildrenCommand

                cmd = CompositeChildrenCommand(parent_action, f"Edit sub-action {new_action.get_display_name()}")

                if branch == "THEN" and hasattr(parent_action, "then_children"):
                    children = list(parent_action.then_children)
                    then_idx = row
                    if 0 <= then_idx < len(children):
                        children[then_idx] = new_action
                        parent_action.then_children = children
                elif branch == "ELSE" and hasattr(parent_action, "else_children"):
                    children = list(parent_action.else_children)
                    else_idx = row - len(parent_action.then_children)
                    if 0 <= else_idx < len(children):
                        children[else_idx] = new_action
                        parent_action.else_children = children
                else:
                    children = list(parent_action.children)
                    if 0 <= row < len(children):
                        children[row] = new_action
                        parent_action.children = children

                cmd.capture_new_state()
                self._undo_stack.push(cmd)
                self._mark_dirty()
                self._refresh_table()
                logger.info(
                    "Edited sub-action '%s' in %s", new_action.get_display_name(), parent_action.get_display_name()
                )
            except Exception:
                logger.exception("Failed to edit sub-action")

        dialog.action_ready.connect(_handle_edited)
        dialog.exec()

    def _delete_sub_action(self, node) -> None:
        """Delete a nested sub-action from its parent."""
        parent_node = node.parent
        if not parent_node:
            return

        parent_action = parent_node.action
        branch = node.branch_label
        row = node.row

        try:
            from core.undo_commands import CompositeChildrenCommand

            cmd = CompositeChildrenCommand(parent_action, "Delete sub-action")

            if branch == "THEN" and hasattr(parent_action, "then_children"):
                children = list(parent_action.then_children)
                then_idx = row
                if 0 <= then_idx < len(children):
                    children.pop(then_idx)
                    parent_action.then_children = children
            elif branch == "ELSE" and hasattr(parent_action, "else_children"):
                children = list(parent_action.else_children)
                else_idx = row - len(parent_action.then_children)
                if 0 <= else_idx < len(children):
                    children.pop(else_idx)
                    parent_action.else_children = children
            else:
                children = list(parent_action.children)
                if 0 <= row < len(children):
                    children.pop(row)
                    parent_action.children = children

            cmd.capture_new_state()
            self._undo_stack.push(cmd)
            self._mark_dirty()
            self._refresh_table()
            logger.info(
                "Deleted sub-action from %s (%s branch)", parent_action.get_display_name(), branch or "children"
            )
        except Exception:
            logger.exception("Failed to delete sub-action")

    def _add_nested_sub_action(self, parent_action, branch: str) -> None:
        """Add a sub-action to a nested composite action (any depth)."""
        if not parent_action.is_composite:
            return

        dialog = ActionEditorDialog(self, macro_dir=self._macro_dir)

        def _handle(new_action):
            try:
                from core.undo_commands import CompositeChildrenCommand

                cmd = CompositeChildrenCommand(parent_action, f"Add {new_action.get_display_name()} to {branch}")

                if branch == "then":
                    parent_action.then_children = parent_action.then_children + [new_action]
                elif branch == "else":
                    parent_action.else_children = parent_action.else_children + [new_action]
                else:
                    parent_action.children = parent_action.children + [new_action]

                cmd.capture_new_state()
                self._undo_stack.push(cmd)
                self._mark_dirty()
                self._refresh_table()
                logger.info(
                    "Added nested sub-action '%s' to %s (%s)",
                    new_action.get_display_name(),
                    parent_action.get_display_name(),
                    branch,
                )
            except Exception:
                logger.exception("Failed to add nested sub-action")

        dialog.action_ready.connect(_handle)
        dialog.exec()

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
        """Create a new empty macro, prompting to save if dirty."""
        if self._actions:
            r = QMessageBox.question(
                self, "Macro mới", "Bỏ macro hiện tại?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if r != QMessageBox.StandardButton.Yes:
                return
        logger.info("New macro created (cleared %d actions)", len(self._actions))
        self._actions.clear()
        self._undo_stack.clear()  # P1-2: Reset undo history for new file
        # P2-2: Reset action ID counter for compact IDs
        from core.action import reset_id_counter

        reset_id_counter()
        self._current_file = ""
        self._refresh_table()
        self.setWindowTitle("AutoMacro (by TungDo) – New Macro")
        self._autosave.set_current_file(None)
        self._autosave.mark_clean()

    def _on_open(self) -> None:
        """Open a macro file from disk."""
        path, _ = QFileDialog.getOpenFileName(self, "Mở Macro", self._macro_dir, "JSON Macros (*.json);;All Files (*)")
        if not path:
            return
        try:
            self._actions, settings = MacroEngine.load_macro(path)
            self._loop_spin.setValue(settings.get("loop_count", 1))
            self._loop_delay_spin.setValue(settings.get("delay_between_loops", 0))
            self._current_file = path
            self._refresh_table()
            name = settings.get("name", Path(path).stem)
            self.setWindowTitle(f"AutoMacro (by TungDo) – {name}")
            self._status_label.setText(f"Đã mở: {Path(path).name}")
            logger.info("Opened macro: %s (%d actions)", Path(path).name, len(self._actions))
            self._autosave.set_current_file(Path(path))
            self._autosave.mark_clean()
            self._add_to_recent(path)
        except Exception as e:
            QMessageBox.critical(self, "Lỗi Mở File", self._friendly_error_msg("Không thể mở file macro.", e))

    def _on_save(self) -> None:
        """Save the current macro to disk."""
        if not self._current_file:
            path, _ = QFileDialog.getSaveFileName(self, "Lưu Macro", self._macro_dir, "JSON Macros (*.json)")
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
            self._status_label.setText(f"Đã lưu: {Path(self._current_file).name}")
            logger.info("Saved macro: %s (%d actions)", Path(self._current_file).name, len(self._actions))
            self._autosave.set_current_file(Path(self._current_file))
            self._autosave.mark_clean()
            self._add_to_recent(self._current_file)
        except Exception as e:
            QMessageBox.critical(self, "Lỗi Lưu File", self._friendly_error_msg("Không thể lưu file macro.", e))

    # ── Recent Files (P2 #5) ──────────────────────────────

    def _build_recent_menu(self) -> None:
        """Populate the Recent Files dropdown from config."""
        self._recent_menu.clear()
        recent = self._config.get("recent_files", [])
        if not recent:
            empty_act = self._recent_menu.addAction("(không có file nào)")
            assert empty_act is not None
            empty_act.setEnabled(False)
            return
        for path in recent:
            short = Path(path).name
            act = self._recent_menu.addAction(f"📄 {short}")
            assert act is not None
            act.setToolTip(path)
            act.triggered.connect(lambda checked, p=path: self._open_recent(p))

    def _add_to_recent(self, path: str) -> None:
        """Add a file to the recent files list and persist."""
        path = str(Path(path).resolve())
        recent = self._config.get("recent_files", [])
        if path in recent:
            recent.remove(path)
        recent.insert(0, path)
        self._config["recent_files"] = recent[:8]  # keep max 8
        save_config(self._config)
        self._build_recent_menu()

    def _open_recent(self, path: str) -> None:
        """Open a macro from the recent files list."""
        if not Path(path).exists():
            QMessageBox.warning(self, "File không tồn tại", f"File không tìm thấy:\n{path}")
            # Remove from recent
            recent = self._config.get("recent_files", [])
            if path in recent:
                recent.remove(path)
                self._config["recent_files"] = recent
                save_config(self._config)
                self._build_recent_menu()
            return
        try:
            self._actions, settings = MacroEngine.load_macro(path)
            self._loop_spin.setValue(settings.get("loop_count", 1))
            self._loop_delay_spin.setValue(settings.get("delay_between_loops", 0))
            self._current_file = path
            self._refresh_table()
            name = settings.get("name", Path(path).stem)
            self.setWindowTitle(f"AutoMacro (by TungDo) – {name}")
            self._status_label.setText(f"Đã mở: {Path(path).name}")
            logger.info("Opened recent: %s", Path(path).name)
            self._add_to_recent(path)
        except Exception as e:
            QMessageBox.critical(self, "Lỗi Mở File", self._friendly_error_msg("Không thể mở file macro.", e))

    def _on_add_action(self) -> None:
        """Open the action editor to add a new action."""
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
            logger.info("Added action: %s (total: %d)", action.get_display_name(), len(self._actions))
        except Exception:
            logger.exception("Failed to add action")

    def _add_sub_action(self, parent_idx: int, branch: str) -> None:
        """Open ActionEditor to add a sub-action to a composite action.

        Args:
            parent_idx: Index of the parent composite action in self._actions.
            branch: "children" for LoopBlock, "then"/"else" for If* actions.
        """
        if parent_idx < 0 or parent_idx >= len(self._actions):
            return
        parent = self._actions[parent_idx]
        if not parent.is_composite:
            return

        dialog = ActionEditorDialog(self, macro_dir=self._macro_dir)

        def _handle_sub_action(new_action: Any) -> None:
            try:
                from core.undo_commands import CompositeChildrenCommand

                cmd = CompositeChildrenCommand(parent, f"Add {new_action.get_display_name()} to {branch}")

                if branch == "then":
                    parent.then_children = parent.then_children + [new_action]
                elif branch == "else":
                    parent.else_children = parent.else_children + [new_action]
                else:  # "children" — LoopBlock
                    parent.children = parent.children + [new_action]

                cmd.capture_new_state()
                self._undo_stack.push(cmd)
                self._mark_dirty()
                self._refresh_table()
                logger.info(
                    "Added sub-action '%s' to %s (%s branch)",
                    new_action.get_display_name(),
                    parent.get_display_name(),
                    branch,
                )
            except Exception:
                logger.exception("Failed to add sub-action")

        dialog.action_ready.connect(_handle_sub_action)
        dialog.exec()

    def _on_edit_action(self) -> None:
        """Open the action editor to edit the selected action."""
        # Sub-action support in tree mode
        node = self._get_tree_selected_node()
        if node and node.parent is not None:
            self._edit_sub_action(node)
            return
        row = self._selected_row()
        if row < 0:
            return
        action = self._actions[row]
        dialog = ActionEditorDialog(self, action=action, macro_dir=self._macro_dir)
        # Capture row in closure for the signal handler
        dialog.action_ready.connect(lambda new_action, r=row: self._handle_action_edited(r, new_action))
        dialog.exec()

    def _handle_action_edited(self, row: int, new_action: Any) -> None:
        """Slot: called by ActionEditorDialog.action_ready signal."""
        try:
            if row < len(self._actions):
                old_action = self._actions[row]
                from core.undo_commands import EditActionCommand

                cmd = EditActionCommand(self._actions, row, old_action, new_action)
                self._undo_stack.push(cmd)
                logger.info("Edited action [%d]: %s", row + 1, new_action.get_display_name())
        except Exception:
            logger.exception("Failed to edit action at row %d", row)

    def _on_delete_action(self) -> None:
        """Delete selected actions with confirmation."""
        # Sub-action support in tree mode
        node = self._get_tree_selected_node()
        if node and node.parent is not None:
            msg = f'Delete sub-action "{node.action.get_display_name()}"?'
            reply = QMessageBox.question(
                self,
                "Delete Sub-Action",
                msg,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._delete_sub_action(node)
            return

        rows = self._selected_rows()
        if not rows:
            return

        # Build confirmation message
        if len(rows) == 1:
            msg = f'Delete "{self._actions[rows[0]].get_display_name()}"?'
        else:
            msg = f"Delete {len(rows)} selected actions?"

        reply = QMessageBox.question(
            self,
            "Delete Action",
            msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            from core.undo_commands import DeleteActionsCommand

            cmd = DeleteActionsCommand(self._actions, rows)
            self._undo_stack.push(cmd)
            logger.info("Deleted %d action(s)", len(rows))

    def _on_move_up(self) -> None:
        """Move selected actions up in the list."""
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
        """Move selected actions down in the list."""
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
        """Duplicate selected actions."""
        try:
            # Sub-action support: duplicate within parent's branch
            node = self._get_tree_selected_node()
            if node and node.parent is not None:
                from core.action import Action as BaseAction
                from core.undo_commands import CompositeChildrenCommand

                dup = BaseAction.from_dict(node.action.to_dict())
                parent_action = node.parent.action
                branch = node.branch_label

                cmd = CompositeChildrenCommand(parent_action, f"Duplicate sub-action {dup.get_display_name()}")

                if branch == "THEN" and hasattr(parent_action, "then_children"):
                    parent_action.then_children = parent_action.then_children + [dup]
                elif branch == "ELSE" and hasattr(parent_action, "else_children"):
                    parent_action.else_children = parent_action.else_children + [dup]
                else:
                    parent_action.children = parent_action.children + [dup]

                cmd.capture_new_state()
                self._undo_stack.push(cmd)
                self._mark_dirty()
                self._refresh_table()
                logger.info("Duplicated sub-action '%s'", dup.get_display_name())
                return

            row = self._selected_row()
            if row < 0:
                return
            from core.action import Action as BaseAction

            dup = BaseAction.from_dict(self._actions[row].to_dict())
            from core.undo_commands import DuplicateActionCommand

            cmd = DuplicateActionCommand(self._actions, row, dup)  # type: ignore[assignment]
            self._undo_stack.push(cmd)
            logger.info("Duplicated action [%d]", row + 1)
        except Exception:
            logger.exception("Failed to duplicate action")

    def _on_copy_actions(self) -> None:
        """Copy selected actions to clipboard as JSON."""
        try:
            # Sub-action support: copy from tree node
            node = self._get_tree_selected_node()
            if node and node.parent is not None:
                data = [node.action.to_dict()]
                clipboard = QApplication.clipboard()
                assert clipboard is not None
                import json

                clipboard.setText(json.dumps({"automacro_actions": data}, ensure_ascii=False, indent=2))
                self._status_label.setText("📄 Copied sub-action")
                logger.info("Copied sub-action to clipboard")
                return

            rows = self._selected_rows()
            if not rows:
                return
            data = [self._actions[r].to_dict() for r in sorted(rows)]
            clipboard = QApplication.clipboard()
            assert clipboard is not None
            clipboard.setText(json.dumps({"automacro_actions": data}, indent=2, ensure_ascii=False))
            self._status_label.setText(f"📄 Copied {len(rows)} action(s) to clipboard")
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
                self._mark_dirty()
                self._refresh_table()
                self._status_label.setText(f"📥 Đã dán {len(pasted)} action")
                logger.info("Pasted %d action(s) from clipboard", len(pasted))
        except (json.JSONDecodeError, ValueError, KeyError):
            self._status_label.setText("⚠ Clipboard không chứa action hợp lệ")
        except Exception:
            logger.exception("Failed to paste actions")

    def _on_play(self) -> None:
        """Start or resume macro execution."""
        if not self._actions:
            self._status_label.setText("Chưa có action để chạy")
            logger.info("Play blocked: no actions")
            return

        # Guard: check if at least one action is enabled
        enabled_count = sum(1 for a in self._actions if a.enabled)
        if enabled_count == 0:
            self._status_label.setText("⚠ Tất cả action đều bị tắt")
            logger.info("Play blocked: all %d actions disabled", len(self._actions))
            return

        # Auto-save before play to prevent data loss
        if self._current_file and not self._undo_stack.isClean():
            try:
                MacroEngine.save_macro(
                    self._current_file,
                    self._actions,
                    name=Path(self._current_file).stem,
                    loop_count=self._loop_spin.value(),
                    loop_delay_ms=self._loop_delay_spin.value(),
                )
                self._undo_stack.setClean()
                logger.info("Auto-saved before play: %s", Path(self._current_file).name)
            except Exception:
                logger.warning("Auto-save before play failed", exc_info=True)

        if self._engine.is_paused:
            self._engine.resume()
            self._status_label.setText("▶ Tiếp tục")
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
        logger.info(
            "Play started: %d actions, loop=%s, delay=%dms, speed=%.1f×",
            len(self._actions),
            self._loop_spin.value() or "∞",
            self._loop_delay_spin.value(),
            self._speed_spin.value(),
        )

    def _on_speed_changed(self, value: float) -> None:
        """P0-2: Update engine speed in real-time (works mid-run)."""
        self._engine.set_speed_factor(value)

    def _on_pause(self) -> None:
        """Pause macro execution."""
        if self._engine.is_running:
            if self._engine.is_paused:
                self._engine.resume()
                self._status_label.setText("▶ Tiếp tục")
                self._play_btn.setEnabled(False)
                self._tray.update_state(True, False)
            else:
                self._engine.pause()
                self._status_label.setText("⏸ Tạm dừng")
                self._play_btn.setEnabled(True)  # allow resume via Play
                self._tray.update_state(True, True)
                logger.info("Paused by user")

    def _on_stop(self) -> None:
        """Stop macro execution."""
        logger.info("Stop requested by user")
        self._engine.stop()

    # ------------------------------------------------------------------ #
    # Step Debug & Variable Inspector (2.1)
    # ------------------------------------------------------------------ #
    def _on_step_toggle(self, checked: bool) -> None:
        """Toggle step-by-step execution mode."""
        if hasattr(self, "_engine"):
            self._engine.set_step_mode(checked)
        self._step_next_btn.setEnabled(checked and self._engine.is_running)
        logger.info("Step mode: %s", "ON" if checked else "OFF")

    def _on_step_next(self) -> None:
        """Advance one action in step mode."""
        if hasattr(self, "_engine"):
            self._engine.step_next()

    def _on_engine_step(self, idx: int, name: str) -> None:
        """Called when engine pauses in step mode after executing an action."""
        self._status_label.setText(f"🐛 Step {idx + 1}: {name[:40]}")
        self._step_next_btn.setEnabled(True)
        # Highlight the executed action row
        if 0 <= idx < self._table.rowCount():
            self._table.selectRow(idx)
        self._refresh_variables()

    def _refresh_variables(self) -> None:
        """Update the variable inspector table from execution context."""
        try:
            ctx = getattr(self._engine, "_exec_ctx", None)
            if not ctx:
                return
            snapshot = ctx.snapshot()
            variables = snapshot.get("variables", {})

            self._var_table.setRowCount(len(variables))
            for i, (name, value) in enumerate(sorted(variables.items())):
                self._var_table.setItem(i, 0, QTableWidgetItem(str(name)))
                val_str = str(value)[:100]
                self._var_table.setItem(i, 1, QTableWidgetItem(val_str))
                type_str = type(value).__name__
                self._var_table.setItem(i, 2, QTableWidgetItem(type_str))
        except (RuntimeError, AttributeError):
            pass  # Engine may be destroyed

    def _on_capture(self) -> None:
        assets_dir = os.path.join(self._macro_dir, "assets")
        overlay = ImageCaptureOverlay(save_dir=assets_dir, parent=None)
        overlay.image_captured.connect(self._on_image_captured)
        self.hide()
        QTimer.singleShot(300, overlay.start)
        logger.info("Image capture started")

    def _on_image_captured(self, path: str) -> None:
        self.show()
        self._status_label.setText(f"Đã chụp: {Path(path).name}")
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
                self._status_label.setText(f"Đã thêm {len(actions)} hành động ghi")
                logger.info("Recording finished: %d actions added (total: %d)", len(actions), len(self._actions))
        except Exception:
            logger.exception("Failed to process recorded actions")

    def _on_recording_state_changed(self, is_recording: bool) -> None:
        """Update tray icon when recording starts/stops."""
        self._tray.update_state(
            is_running=self._engine.isRunning(),
            is_paused=False,
            is_recording=is_recording,
        )

    def _on_settings(self) -> None:
        """Open the settings dialog."""
        dialog = SettingsDialog(self._config, self)
        dialog.config_saved.connect(self._handle_settings_saved)
        dialog.exec()

    def _handle_settings_saved(self, config: Any) -> None:
        """Slot: called by SettingsDialog.config_saved signal."""
        try:
            self._config = config
            save_config(self._config)
            # Apply theme + font size immediately (3.5: hot-swap)
            ui_cfg = config.get("ui", {})
            theme_pref = ui_cfg.get("theme", "auto")
            font_size = ui_cfg.get("font_size", 10)
            self._apply_theme_live(theme_pref, font_size=font_size)
            # Re-register hotkeys without restart
            if hasattr(self, "_hk_mgr") and self._hk_mgr:  # type: ignore[has-type]
                self._hk_mgr.stop()  # type: ignore[has-type]
            from main import setup_global_hotkeys

            self._hk_mgr = setup_global_hotkeys(config)
            # Update status bar hotkey display
            hk = config.get("hotkeys", {})
            self._hotkey_label.setText(
                f"  Chạy: {hk.get('start_stop', 'F6')}  |  "
                f"Dừng tạm: {hk.get('pause_resume', 'F7')}  |  "
                f"Dừng: {hk.get('emergency_stop', 'F8')}  |  "
                f"Ghi: {hk.get('record', 'F9')}"
            )
            # Update recording panel button labels
            self._rec_panel.update_hotkeys(config)
            self._status_label.setText("Cài đặt đã lưu ✅")
            logger.info("Settings saved — hotkeys re-registered")
        except Exception:
            logger.exception("Failed to save settings")

    def _update_ram_display(self) -> None:
        """Update RAM usage in status bar."""
        try:
            from core.memory_manager import MemoryManager

            stats = MemoryManager.instance().get_stats()
            self._ram_label.setText(f"RAM: {stats['current_mb']}MB (peak: {stats['peak_mb']}MB)")
        except Exception:
            logger.debug("Failed to update RAM display", exc_info=True)

    def _on_help(self) -> None:
        """Open the in-app help dialog."""
        dlg = HelpDialog(self)
        dlg.exec()

    def _on_about(self) -> None:
        import platform

        app_inst = QApplication.instance()
        qt_ver = app_inst.applicationVersion() if app_inst else "PyQt6"
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
            f"<p>Designed for 24/7 automation.</p>",
        )

    def _on_quit(self) -> None:
        self._rec_panel.cleanup()
        self._engine.stop()
        self._engine.wait(3000)  # Wait up to 3s for thread to finish
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
            self._tray.show_message("AutoMacro", "Minimized to tray. Double-click to open.")
        else:
            # Guard: prompt if unsaved changes exist
            if not self._undo_stack.isClean():
                reply = QMessageBox.question(
                    self,
                    "Thay Đổi Chưa Lưu",
                    "Bạn có thay đổi chưa lưu. Lưu trước khi thoát?",
                    QMessageBox.StandardButton.Save
                    | QMessageBox.StandardButton.Discard
                    | QMessageBox.StandardButton.Cancel,
                )
                if reply == QMessageBox.StandardButton.Save:
                    self._on_save()
                elif reply == QMessageBox.StandardButton.Cancel:
                    if event:
                        event.ignore()
                    return
            self._autosave.stop()
            self._on_quit()
