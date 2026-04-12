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
    QScrollArea,
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
        self._hk_mgr: Any = None  # set by main.py for restart-free rebind
        self._engine = MacroEngine()
        self._config = load_config()
        self._current_file: str = ""
        self._macro_dir = str(Path("macros").resolve())
        QTimer.singleShot(0, lambda: os.makedirs(self._macro_dir, exist_ok=True))
        # Trigger manager for schedule/window triggers
        from core.trigger_manager import TriggerManager
        self._trigger_mgr = TriggerManager(on_trigger_fire=self._on_trigger_fire)
        triggers_file = Path(self._macro_dir) / ".triggers.json"
        self._trigger_mgr.load_triggers(triggers_file)
        QTimer.singleShot(500, self._trigger_mgr.start)

        self.setWindowTitle("AutoMacro (by TungDo) – New Macro")
        self.setMinimumSize(1024, 640)
        self._restore_window_geometry()
        cfg = load_config()
        ui_cfg = cfg.get("ui", {})
        theme_pref = ui_cfg.get("theme", "auto") if "theme" in ui_cfg else cfg.get("theme", "auto")
        accent_pref = ui_cfg.get("accent_color", "Tím")
        self.setStyleSheet(get_theme(theme_pref, accent=accent_pref))

        self._undo_stack = QUndoStack(self)
        self._undo_stack.indexChanged.connect(self._on_undo_index_changed)
        self._undo_stack.cleanChanged.connect(self._on_clean_changed)

        # Batch engine progress updates — repaint max 10x/second
        self._pending_progress: tuple[int, int] | None = None
        self._pending_action_name: str = ""
        self._progress_timer = QTimer(self)
        self._progress_timer.setInterval(100)
        self._progress_timer.timeout.connect(self._flush_progress)

        self._setup_toolbar()
        self._setup_central()
        self._setup_statusbar()
        self._setup_tray()
        self._connect_engine()
        self._setup_autosave()
        self._check_for_updates()

    def _restore_window_geometry(self) -> None:
        """Restore window position, size, maximized state from config.

        When width/height are -1 (sentinel): auto-calculate from screen size
        (80% width × 85% height, min 900×600).
        """
        from PyQt6.QtWidgets import QApplication
        ui = self._config.get("ui", {})
        w = ui.get("window_width", -1)
        h = ui.get("window_height", -1)
        x = ui.get("window_x", -1)
        y = ui.get("window_y", -1)
        maximized = ui.get("window_maximized", False)

        screen = QApplication.primaryScreen()
        if screen:
            sg = screen.availableGeometry()
        else:
            sg = None

        # Auto-calculate size from screen if sentinel values
        if w <= 0 or h <= 0:
            if sg:
                w = max(900, int(sg.width() * 0.80))
                h = max(600, int(sg.height() * 0.85))
            else:
                w, h = 1000, 700
        # Guard: if saved size is at the bare minimum (1024×640), recalculate
        # to prevent cramped layout from old configs
        elif sg and w <= 1024 and h <= 640:
            w = max(w, int(sg.width() * 0.80))
            h = max(h, int(sg.height() * 0.85))

        self.resize(w, h)

        # Restore position if saved, or center on screen
        if x >= 0 and y >= 0 and sg:
            # Clamp to ensure at least 100px visible
            x = max(sg.left(), min(x, sg.right() - 100))
            y = max(sg.top(), min(y, sg.bottom() - 100))
            self.move(x, y)
        elif sg:
            # Center on screen for first launch
            cx = sg.left() + (sg.width() - w) // 2
            cy = sg.top() + (sg.height() - h) // 2
            self.move(cx, cy)

        if maximized:
            self.showMaximized()

    def _save_window_state(self) -> None:
        """Save window geometry and splitter sizes to config."""
        ui = self._config.setdefault("ui", {})
        ui["window_maximized"] = self.isMaximized()
        if not self.isMaximized():
            geo = self.geometry()
            ui["window_x"] = geo.x()
            ui["window_y"] = geo.y()
            ui["window_width"] = geo.width()
            ui["window_height"] = geo.height()
        # Save splitter sizes
        if hasattr(self, "_h_splitter"):
            ui["h_splitter_sizes"] = self._h_splitter.sizes()
        if hasattr(self, "_v_splitter"):
            ui["v_splitter_sizes"] = self._v_splitter.sizes()
        save_config(self._config)

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

    def _check_for_updates(self) -> None:
        """P3-C: Check for new version on GitHub (non-blocking, best-effort)."""
        try:
            from version import __version__
        except ImportError:
            return

        from core.update_checker import check_for_update

        def _on_update_result(has_update: bool, latest: str, url: str) -> None:
            if has_update:
                # Use QTimer.singleShot to safely update UI from main thread
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(0, lambda: self._show_update_hint(latest, url))

        check_for_update(__version__, on_result=_on_update_result)

    def _show_update_hint(self, latest: str, url: str) -> None:
        """Show update notification in status bar."""
        self._statusbar.showMessage(
            f"🆕 Phiên bản mới: v{latest} — Tải tại GitHub",
            30_000,  # Show for 30 seconds
        )

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
        self._add_act.setToolTip("Thêm action mới (Ins)")
        self._add_act.setShortcut(QKeySequence("Ins"))
        self._add_act.triggered.connect(self._on_add_action)
        tb.addAction(self._add_act)

        self._edit_act = QMenuAction("✏️ Sửa", self)
        self._edit_act.setToolTip("Sửa action đang chọn (Enter)")
        self._edit_act.triggered.connect(self._on_edit_action)
        tb.addAction(self._edit_act)

        self._del_act = QMenuAction("🗑️ Xóa", self)
        self._del_act.setToolTip("Xóa action (Delete)")
        self._del_act.triggered.connect(self._on_delete_action)
        tb.addAction(self._del_act)

        tb.addSeparator()

        # Tools
        capture_act = QMenuAction("📸 Chụp", self)
        capture_act.setToolTip("Chụp vùng màn hình làm ảnh mẫu (Ctrl+Shift+C)")
        capture_act.setShortcut(QKeySequence("Ctrl+Shift+C"))
        capture_act.triggered.connect(self._on_capture)
        tb.addAction(capture_act)

        coord_act = QMenuAction("🎯 Tọa độ", self)
        coord_act.setShortcut(QKeySequence("Ctrl+G"))
        coord_act.setToolTip("Chọn tọa độ từ màn hình (Ctrl+G)\n" "Click bất kỳ → X,Y hiển thị trên thanh trạng thái")
        coord_act.triggered.connect(self._on_pick_coordinate)
        tb.addAction(coord_act)

        # ── ≡ Menu dropdown (secondary actions) ──────────────
        from PyQt6.QtWidgets import QMenu as QDropdownMenu

        menu_btn = QToolButton()
        menu_btn.setText("≡ Menu")
        menu_btn.setToolTip("Cài đặt, Hướng dẫn, Mẫu, ...")
        menu_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        extra_menu = QDropdownMenu(self)

        settings_act = extra_menu.addAction("⚙ Cài đặt")
        settings_act.setToolTip("Mở cài đặt ứng dụng")
        settings_act.triggered.connect(self._on_settings)

        extra_menu.addSeparator()

        template_act = extra_menu.addAction("📦 Mẫu (Ctrl+T)")
        template_act.setShortcut(QKeySequence("Ctrl+T"))
        template_act.setToolTip("Chèn macro mẫu (Ctrl+T)")
        template_act.triggered.connect(self._on_insert_template)

        hints_act = extra_menu.addAction("💡 Gợi ý (Ctrl+H)")
        hints_act.setShortcut(QKeySequence("Ctrl+H"))
        hints_act.setToolTip("Phân tích macro và hiển thị gợi ý (Ctrl+H)")
        hints_act.triggered.connect(self._on_show_hints)

        trigger_act = extra_menu.addAction("⏰ Triggers")
        trigger_act.setToolTip("Quản lý trigger tự động (lịch trình, cửa sổ)")
        trigger_act.triggered.connect(self._on_manage_triggers)

        extra_menu.addSeparator()

        help_act = extra_menu.addAction("📖 Hướng dẫn (F1)")
        help_act.setShortcut(QKeySequence("F1"))
        help_act.setToolTip("Mở hướng dẫn sử dụng (F1)")
        help_act.triggered.connect(self._on_help)

        about_act = extra_menu.addAction("ℹ️ Giới thiệu")
        about_act.setToolTip("Thông tin ứng dụng")
        about_act.triggered.connect(self._on_about)

        menu_btn.setMenu(extra_menu)
        tb.addWidget(menu_btn)

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
        self._action_list_panel.delete_requested.connect(self._on_delete_action)
        self._action_list_panel.add_action_requested.connect(self._on_add_action)
        self._action_list_panel.record_requested.connect(lambda: self._rec_panel.toggle_recording())
        self._action_list_panel.open_file_requested.connect(self._on_open)
        self._action_list_panel.quick_add_requested.connect(self._on_quick_add)

        # R9: Keyboard shortcuts for action list
        from PyQt6.QtGui import QKeySequence, QShortcut
        QShortcut(QKeySequence("F2"), self._action_list_panel, self._on_edit_action)
        QShortcut(QKeySequence("Delete"), self._action_list_panel, self._on_delete_action)
        QShortcut(QKeySequence("Ctrl+D"), self._action_list_panel, self._on_duplicate)
        QShortcut(QKeySequence("Ctrl+Up"), self._action_list_panel, self._on_move_up)
        QShortcut(QKeySequence("Ctrl+Down"), self._action_list_panel, self._on_move_down)

        # Backward-compat aliases for existing code references
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

        # Drag-drop undo: snapshot order before drop
        self._pre_drag_order: list[Action] = []
        self._tree.viewport().installEventFilter(self)  # type: ignore[union-attr]

        splitter.addWidget(self._action_list_panel)

        # Right panel — tabbed layout for reduced scrolling
        from PyQt6.QtWidgets import QTabWidget

        right_tabs = QTabWidget()
        right_tabs.setDocumentMode(True)  # Fluent-style flat tabs

        # ── Tab 1: Điều khiển & Trạng thái ──
        tab1_widget = QWidget()
        tab1_layout = QVBoxLayout(tab1_widget)
        tab1_layout.setContentsMargins(0, 4, 0, 0)

        # ── 1. Playback controls (extracted panel) ─────────────
        from gui.panels.playback_panel import PlaybackPanel

        self._playback_panel = PlaybackPanel()
        self._playback_panel.play_requested.connect(self._on_play)
        self._playback_panel.pause_requested.connect(self._on_pause)
        self._playback_panel.stop_requested.connect(self._on_stop)
        self._playback_panel.step_toggled.connect(self._on_step_toggle)
        self._playback_panel.step_next_requested.connect(self._on_step_next)
        self._playback_panel.speed_changed.connect(self._on_speed_changed)
        tab1_layout.addWidget(self._playback_panel)

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
        tab1_layout.addWidget(self._rec_panel)

        # ── 3. Execution panel (extracted) ─────────────────────
        from gui.panels.execution_panel import ExecutionPanel

        self._exec_panel = ExecutionPanel()
        tab1_layout.addWidget(self._exec_panel)
        # Backward-compat aliases
        self._action_label = self._exec_panel._action_label
        self._progress_bar = self._exec_panel._progress_bar
        self._loop_label = self._exec_panel._loop_label
        self._exec_log = self._exec_panel._exec_log

        tab1_layout.addStretch()
        # Wrap Tab 1 in scroll for small screens
        tab1_scroll = QScrollArea()
        tab1_scroll.setWidget(tab1_widget)
        tab1_scroll.setWidgetResizable(True)
        tab1_scroll.setFrameShape(tab1_scroll.Shape.NoFrame)
        right_tabs.addTab(tab1_scroll, "▶ Điều khiển")

        # ── Tab 2: Công cụ ──
        tab2_widget = QWidget()
        tab2_layout = QVBoxLayout(tab2_widget)
        tab2_layout.setContentsMargins(0, 4, 0, 0)

        # ── 4. Variable Inspector (extracted) ──────────────────
        from gui.panels.variable_panel import VariablePanel

        self._var_panel = VariablePanel()
        tab2_layout.addWidget(self._var_panel)
        # Backward-compat aliases
        self._var_group = self._var_panel._group
        self._var_table = self._var_panel._var_table
        self._var_timer = self._var_panel._timer

        # ── 5. Mini-Map (Phase 3) ──────────────────────────────
        from gui.panels.minimap_panel import MiniMapWidget

        self._minimap = MiniMapWidget()
        self._minimap.action_clicked.connect(self._on_minimap_action_clicked)
        # Bidirectional sync: tree scroll → minimap viewport
        self._tree.verticalScrollBar().valueChanged.connect(self._sync_minimap_viewport)
        tab2_layout.addWidget(self._minimap)

        # ── 6. Inline Properties Panel ─────────────────────────
        from gui.panels.properties_panel import PropertiesPanel

        self._props_panel = PropertiesPanel()
        tab2_layout.addWidget(self._props_panel)
        # Connect tree selection to properties panel
        sel_model = self._tree.selectionModel()
        if sel_model:
            sel_model.selectionChanged.connect(self._on_tree_selection_changed)

        tab2_layout.addStretch()
        # Wrap Tab 2 in scroll for small screens
        tab2_scroll = QScrollArea()
        tab2_scroll.setWidget(tab2_widget)
        tab2_scroll.setWidgetResizable(True)
        tab2_scroll.setFrameShape(tab2_scroll.Shape.NoFrame)
        right_tabs.addTab(tab2_scroll, "🔧 Công cụ")

        # Tab 3: Multi-Run Dashboard
        from gui.panels.multi_run_panel import MultiRunPanel
        self._multi_run = MultiRunPanel()
        right_tabs.addTab(self._multi_run, "🚀 Multi-Run")

        self._right_tabs = right_tabs

        self._h_splitter = splitter
        splitter.addWidget(right_tabs)
        # Restore H-splitter sizes from config (proportional default: 60/40)
        h_sizes = self._config.get("ui", {}).get("h_splitter_sizes", [])
        if not h_sizes or len(h_sizes) != 2:
            # Use fixed sensible defaults: action list wide (680), controls panel (400)
            h_sizes = [680, 400]
        # Guard: right panel must be at least 350px for controls to display
        if h_sizes[1] < 350:
            total = sum(h_sizes)
            h_sizes = [total - 400, 400]
        splitter.setSizes(h_sizes)

        # ── Vertical splitter: content on top, log panel on bottom ──
        v_splitter = QSplitter(Qt.Orientation.Vertical)
        v_splitter.addWidget(splitter)

        # ── 5. Log panel (extracted) ───────────────────────────
        from gui.panels.log_panel import LogPanel

        self._log_panel = LogPanel()
        v_splitter.addWidget(self._log_panel)
        # Backward-compat aliases
        self._app_log = self._log_panel._app_log

        self._v_splitter = v_splitter
        # Restore V-splitter sizes from config (proportional default: 80/20)
        v_sizes = self._config.get("ui", {}).get("v_splitter_sizes", [])
        if not v_sizes or len(v_sizes) != 2:
            # Fixed default: large content area (560) + compact log panel (140)
            v_sizes = [560, 140]
        v_splitter.setSizes(v_sizes)
        v_splitter.setCollapsible(1, True)  # log panel collapsible

        layout.addWidget(v_splitter)

        # ── 3.6: Keyboard UX shortcuts ─────────────────────────
        self._setup_keyboard_ux()

    # ------------------------------------------------------------------ #
    # Keyboard UX (3.6)
    # ------------------------------------------------------------------ #
    def _setup_keyboard_ux(self) -> None:
        """Add keyboard shortcuts for power users.

        All shortcuts are scoped to self._tree with WidgetWithChildrenShortcut
        context so they fire when the tree view or its children have focus.
        This prevents conflicts with text editing in QLineEdit, etc.
        """
        from PyQt6.QtGui import QKeySequence, QShortcut

        ctx = Qt.ShortcutContext.WidgetWithChildrenShortcut

        # ── Single-key shortcuts via event filter ──
        # QTreeView with drag-drop InternalMove consumes Del/Enter/Space
        # in its keyPressEvent BEFORE QShortcut can fire.
        # Event filter has highest priority — intercepts keys before tree.
        from PyQt6.QtCore import QEvent, QObject

        class _TreeKeyFilter(QObject):
            """Event filter that intercepts single-key shortcuts on the tree."""

            def __init__(self, window: "MainWindow") -> None:
                super().__init__(window)
                self._w = window

            def eventFilter(self, obj: QObject, event: QEvent) -> bool:
                if event.type() == QEvent.Type.KeyPress:
                    key = event.key()  # type: ignore[union-attr]
                    if key == Qt.Key.Key_Delete:
                        self._w._on_delete_action()
                        return True  # consumed
                    if key == Qt.Key.Key_Return or key == Qt.Key.Key_Enter:
                        self._w._on_edit_action()
                        return True
                    if key == Qt.Key.Key_Space:
                        self._w._on_toggle_selected()
                        return True
                return False

        self._tree_key_filter = _TreeKeyFilter(self)
        self._tree.installEventFilter(self._tree_key_filter)

        # Escape = Focus back to action table (window-wide, intentional)
        esc_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        esc_shortcut.activated.connect(lambda: self._tree.setFocus())

        # Ctrl+Up / Ctrl+Down = Move action up/down
        up_shortcut = QShortcut(QKeySequence("Ctrl+Up"), self._tree)
        up_shortcut.setContext(ctx)
        up_shortcut.activated.connect(self._on_move_up)

        down_shortcut = QShortcut(QKeySequence("Ctrl+Down"), self._tree)
        down_shortcut.setContext(ctx)
        down_shortcut.activated.connect(self._on_move_down)

        # Ctrl+D = Duplicate selected action
        dup_shortcut = QShortcut(QKeySequence("Ctrl+D"), self._tree)
        dup_shortcut.setContext(ctx)
        dup_shortcut.activated.connect(self._on_duplicate)

        # Ctrl+C = Copy selected actions
        copy_shortcut = QShortcut(QKeySequence("Ctrl+C"), self._tree)
        copy_shortcut.setContext(ctx)
        copy_shortcut.activated.connect(self._on_copy_actions)

        # Ctrl+V = Paste actions from clipboard
        paste_shortcut = QShortcut(QKeySequence("Ctrl+V"), self._tree)
        paste_shortcut.setContext(ctx)
        paste_shortcut.activated.connect(self._on_paste_actions)

        # Ctrl+Enter = Run from selected action (3.6b)
        ctrl_enter = QShortcut(QKeySequence("Ctrl+Return"), self._tree)
        ctrl_enter.setContext(ctx)
        ctrl_enter.activated.connect(self._on_run_from_selected)

        # Ctrl+B = Toggle bookmark
        ctrl_b = QShortcut(QKeySequence("Ctrl+B"), self._tree)
        ctrl_b.setContext(ctx)
        ctrl_b.activated.connect(self._on_toggle_bookmark)

        # F2 = Jump to next bookmark
        f2_shortcut = QShortcut(QKeySequence(Qt.Key.Key_F2), self._tree)
        f2_shortcut.setContext(ctx)
        f2_shortcut.activated.connect(self._on_jump_next_bookmark)

        # Tab order: table → playback → recording → log
        QWidget.setTabOrder(self._tree, self._playback_panel)
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

    def _preflight_check(self) -> bool:
        """Run smart_hints preflight before engine start.

        Returns True if safe to proceed, False to block.
        - Errors: block execution completely
        - Warnings: show dialog, user must choose 'Run Anyway'
        """
        from core.smart_hints import analyze_hints

        hints = analyze_hints(self._actions)
        if not hints:
            return True

        errors = [h for h in hints if h.get("level") == "error"]
        warnings = [h for h in hints if h.get("level") == "warning"]

        if errors:
            # Block: show errors and prevent execution
            lines = [f"{h.get('icon', '❌')} {h.get('message', '')}" for h in errors]
            if warnings:
                lines.append("\n─── Cảnh báo ───")
                lines.extend(f"{h.get('icon', '⚠')} {h.get('message', '')}" for h in warnings)
            QMessageBox.critical(
                self,
                f"🚫 Không thể chạy ({len(errors)} lỗi)",
                "Macro có lỗi nghiêm trọng, cần sửa trước khi chạy:\n\n"
                + "\n\n".join(lines),
            )
            logger.warning("Preflight blocked: %d errors", len(errors))
            return False

        if warnings:
            # Warn: default Cancel, user can choose 'Run Anyway'
            lines = [f"{h.get('icon', '⚠')} {h.get('message', '')}" for h in warnings]
            reply = QMessageBox.warning(
                self,
                f"⚠ Cảnh báo ({len(warnings)} mục)",
                "Macro có cảnh báo:\n\n" + "\n\n".join(lines)
                + "\n\nBạn có muốn chạy tiếp?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,  # Default = Cancel
            )
            if reply != QMessageBox.StandardButton.Yes:
                logger.info("Preflight: user cancelled due to warnings")
                return False
            logger.info("Preflight: user acknowledged %d warnings", len(warnings))

        return True

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

        if obj is self._tree.viewport():
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
        for r in range(self._tree_model.rowCount()):
            node = self._tree_model.node_at(self._tree_model.index(r, 0))
            if node:
                new_order.append(node.action)
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
        self._engine.duration_signal.connect(self._on_action_duration)
        self._engine.report_signal.connect(self._on_engine_report)
        # 1.2: Bridge engine signals to Event Bus
        from core.event_bus import AppEventBus

        AppEventBus.instance().bridge_engine(self._engine)

    def _set_ui_locked(self, locked: bool) -> None:
        """Disable/enable all editing controls when engine is running."""
        editable = not locked
        # Table & action editing
        self._tree.setEnabled(editable)
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
        # Clear row highlights
        self._tree.clearSelection()
        if hasattr(self, "_tree_model"):
            self._tree_model.set_executing_row(-1)
            self._tree_model.set_error_row(-1)
        # Stop batch timer
        self._progress_timer.stop()
        self._pending_progress = None
        # Phase 3: reset mini-map
        if hasattr(self, "_minimap"):
            self._minimap.reset()
        logger.info("Engine stopped")

    def _on_engine_report(self, report) -> None:
        """Show run summary dialog after engine finishes."""
        from gui.run_summary_dialog import RunSummaryDialog

        dlg = RunSummaryDialog(report, self)
        dlg.exec()
        if dlg.result_action == "rerun":
            self._on_play()
        elif dlg.result_action == "goto_error":
            idx = report.first_error_idx
            if idx >= 0 and hasattr(self, "_tree_model"):
                from PyQt6.QtCore import QModelIndex
                index = self._tree_model.index(idx, 0, QModelIndex())
                self._tree.setCurrentIndex(index)
                self._tree.scrollTo(index)

    def _on_engine_error(self, msg: str) -> None:
        """Handle engine error: show warning dialog and highlight error row."""
        self._status_label.setText(f"⚠ Lỗi: {msg[:80]}")
        logger.error("Engine error: %s", msg)
        # Highlight the failed action row in red
        progress = self._progress_bar.value()
        if progress > 0 and hasattr(self, "_tree_model"):
            self._tree_model.set_error_row(progress - 1)
        # P1 #2: Error popup
        QMessageBox.warning(self, "⚠ Lỗi thực thi", f"Macro gặp lỗi:\n\n{msg}\n\n" "Kiểm tra action và thử lại.")

    def _on_engine_progress(self, current: int, total: int) -> None:
        """Buffer progress update — actual repaint via _flush_progress."""
        self._pending_progress = (current, total)
        if not self._progress_timer.isActive():
            self._progress_timer.start()

    def _flush_progress(self) -> None:
        """Batch repaint: update UI with buffered progress data (max 10 FPS)."""
        if self._pending_progress is None:
            self._progress_timer.stop()
            return

        current, total = self._pending_progress
        self._pending_progress = None

        # 1. Progress bar
        self._progress_bar.setMaximum(total)
        self._progress_bar.setValue(current)

        # 2. Action name
        if self._pending_action_name:
            self._action_label.setText(f"▶ {self._pending_action_name}")

        # 3. TreeView highlight (1 repaint instead of N)
        if 0 < current <= self._tree_model.rowCount():
            idx = self._tree_model.index(current - 1, 0)
            self._tree.setCurrentIndex(
                self._action_list_panel.filter_proxy.mapFromSource(idx))
            self._tree_model.set_executing_row(current - 1)

        # 4. MiniMap highlight
        if hasattr(self, "_minimap"):
            self._minimap.highlight_action(current - 1)

    def _on_engine_action(self, name: str) -> None:
        """Buffer action name — actual display via _flush_progress."""
        self._pending_action_name = name
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
    # Icon map -- single source of truth in gui/constants.py
    from gui.constants import TYPE_ICONS as _TYPE_ICONS

    def _refresh_table(self) -> None:
        """Rebuild the tree view from the _actions list."""
        has_actions = len(self._actions) > 0
        self._tree.setVisible(has_actions)
        self._empty_overlay.setVisible(not has_actions)
        # Save expand state before rebuild
        expand_state: dict[str, bool] = {}
        if hasattr(self, "_action_list_panel") and hasattr(self._action_list_panel, "save_expand_state"):
            expand_state = self._action_list_panel.save_expand_state()
        # Rebuild tree model (sync actions reference in case list was replaced)
        if hasattr(self, "_tree_model"):
            self._tree_model._actions = self._actions
            self._tree_model.rebuild()
        # Re-invalidate filter proxy
        if hasattr(self._action_list_panel, "_filter_proxy"):
            self._action_list_panel._filter_proxy.invalidateFilter()
        # Restore expand state (or expandAll if no prior state)
        if hasattr(self, "_action_list_panel") and hasattr(self._action_list_panel, "restore_expand_state"):
            self._action_list_panel.restore_expand_state(expand_state)
        # Update stats bar
        self._update_stats()
        # Phase 3: sync mini-map
        if hasattr(self, "_minimap"):
            self._minimap.set_actions(self._actions)

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
        sel = self._tree.selectionModel()
        if sel is None:
            return -1
        indexes = sel.selectedRows()
        if not indexes:
            return -1
        proxy_idx = indexes[0]
        source_idx = self._action_list_panel.filter_proxy.mapToSource(proxy_idx)
        if source_idx.parent().isValid():
            return -1  # Nested child — not a root-level action
        return source_idx.row()

    def _selected_rows(self) -> list[int]:
        """Return all selected row indices (sorted). Root-level only."""
        sel = self._tree.selectionModel()
        if sel is None:
            return []
        proxy = self._action_list_panel.filter_proxy
        return sorted(
            proxy.mapToSource(idx).row()
            for idx in sel.selectedRows()
            if not proxy.mapToSource(idx).parent().isValid()
        )

    def _get_tree_selected_node(self):
        """Return the tree node for the selected item (root or nested)."""
        sel = self._tree.selectionModel()
        if sel is None:
            return None
        indexes = sel.selectedRows()
        if not indexes:
            return None
        proxy_idx = indexes[0]
        source_idx = self._action_list_panel.filter_proxy.mapToSource(proxy_idx)
        return self._tree_model.node_at(source_idx)

    def _show_context_menu(self, pos: Any) -> None:
        """Right-click context menu for action tree."""
        from PyQt6.QtWidgets import QMenu

        vp = self._tree.viewport()
        if vp is None:
            return
        global_pos = vp.mapToGlobal(pos)

        menu = QMenu(self)

        # Check if a sub-action (nested) is selected
        sel = self._tree.selectionModel()
        selected_indexes = sel.selectedRows() if sel else []
        if selected_indexes:
            proxy_idx = selected_indexes[0]
            source_idx = self._action_list_panel.filter_proxy.mapToSource(proxy_idx)
            node = self._tree_model.node_at(source_idx)
            if node and source_idx.parent().isValid():
                # Placeholder node (empty branch) — show "add to branch" menu
                if node.action is None:
                    self._show_placeholder_context_menu(menu, global_pos, node)
                    return
                self._show_sub_action_context_menu(menu, global_pos, node, source_idx)
                return

        # Standard context menu for root-level actions
        rows = self._selected_rows()
        if not rows:
            add_act = menu.addAction("➕ Thêm Action")
            add_act.triggered.connect(self._on_add_action)
            menu.exec(global_pos)
            return

        edit_act = menu.addAction("✏️ Sửa")
        edit_act.triggered.connect(self._on_edit_action)
        edit_act.setEnabled(len(rows) == 1)

        dup_act = menu.addAction("📋 Nhân bản")
        dup_act.triggered.connect(self._on_duplicate)
        dup_act.setEnabled(len(rows) == 1)

        copy_act = menu.addAction("📄 Sao chép (Ctrl+C)")
        copy_act.triggered.connect(self._on_copy_actions)

        paste_act = menu.addAction("📥 Dán (Ctrl+V)")
        paste_act.triggered.connect(self._on_paste_actions)

        toggle_act = menu.addAction("✗ Tắt" if self._actions[rows[0]].enabled else "✓ Bật")
        toggle_act.triggered.connect(self._on_toggle_enabled)

        menu.addSeparator()

        # Wrap in group/loop/if submenu
        wrap_menu = menu.addMenu("📦 Bọc trong...")
        wrap_group_act = wrap_menu.addAction("📦 Group")
        wrap_group_act.triggered.connect(lambda: self._on_wrap_in("group"))
        wrap_loop_act = wrap_menu.addAction("🔁 Loop Block")
        wrap_loop_act.triggered.connect(lambda: self._on_wrap_in("loop_block"))
        wrap_if_act = wrap_menu.addAction("📊 If Variable")
        wrap_if_act.triggered.connect(lambda: self._on_wrap_in("if_variable"))

        # Color coding submenu
        color_menu = menu.addMenu("🎨 Đặt màu")
        _clabels = {
            "": "⬜ Xóa màu", "red": "🔴 Đỏ", "orange": "🟠 Cam",
            "yellow": "🟡 Vàng", "green": "🟢 Xanh lá", "teal": "🩵 Teal",
            "blue": "🔵 Xanh dương", "indigo": "🟣 Indigo",
            "purple": "💜 Tím", "pink": "🩷 Hồng",
        }
        for color_key, label in _clabels.items():
            act = color_menu.addAction(label)
            act.triggered.connect(lambda checked=False, c=color_key: self._on_set_color(c))

        # Bookmark toggle
        bm_label = "🔖 Bỏ đánh dấu" if self._actions[rows[0]].bookmarked else "🔖 Đánh dấu"
        bm_act = menu.addAction(bm_label)
        bm_act.triggered.connect(self._on_toggle_bookmark)

        # Composite sub-action items (LoopBlock, If*, Group)
        if len(rows) == 1:
            action = self._actions[rows[0]]
            if action.is_composite:
                menu.addSeparator()
                if action.has_branches:
                    add_then = menu.addAction("➕ Thêm vào THEN")
                    add_then.triggered.connect(lambda checked=False, r=rows[0]: self._add_sub_action(r, "then"))
                    add_else = menu.addAction("➕ Thêm vào ELSE")
                    add_else.triggered.connect(lambda checked=False, r=rows[0]: self._add_sub_action(r, "else"))
                else:
                    add_child = menu.addAction("➕ Thêm sub-action")
                    add_child.triggered.connect(lambda checked=False, r=rows[0]: self._add_sub_action(r, "children"))

        menu.addSeparator()

        del_act = menu.addAction("🗑️ Xóa")
        del_act.triggered.connect(self._on_delete_action)

        menu.exec(global_pos)

    def _on_wrap_in_group(self) -> None:
        """Backward compat: wrap in group."""
        self._on_wrap_in("group")

    def _on_wrap_in(self, wrapper_type: str) -> None:
        """Wrap selected root-level actions into a composite action."""
        rows = self._selected_rows()
        if not rows:
            return
        selected_actions = [self._actions[r] for r in sorted(rows)]

        if wrapper_type == "group":
            from core.scheduler import GroupAction
            wrapper = GroupAction(name="Group mới", children=selected_actions)
        elif wrapper_type == "loop_block":
            from core.scheduler import LoopBlock
            wrapper = LoopBlock(iterations=1, sub_actions=selected_actions)
        elif wrapper_type == "if_variable":
            from core.scheduler import IfVariable
            wrapper = IfVariable(
                var_name="", operator="==", compare_value="",
                then_actions=selected_actions, else_actions=[],
            )
        else:
            return

        for r in sorted(rows, reverse=True):
            self._actions.pop(r)
        insert_pos = min(rows)
        self._actions.insert(insert_pos, wrapper)
        self._refresh_table()
        self._select_tree_row(insert_pos)
        logger.info("Wrapped %d actions into %s at position %d", len(selected_actions), wrapper_type, insert_pos)

    def _on_set_color(self, color: str) -> None:
        """Set color tag on all selected actions."""
        rows = self._selected_rows()
        if not rows:
            return
        for r in rows:
            self._actions[r].color = color
        self._refresh_table()

    def _on_toggle_bookmark(self) -> None:
        """Toggle bookmark on selected actions."""
        rows = self._selected_rows()
        if not rows:
            return
        # Toggle: if first is bookmarked, un-bookmark all. Else bookmark all.
        new_state = not self._actions[rows[0]].bookmarked
        for r in rows:
            self._actions[r].bookmarked = new_state
        self._refresh_table()
        self._mark_dirty()
        bm_count = sum(1 for a in self._actions if a.bookmarked)
        self._status_label.setText(f"🔖 {'Đã đánh dấu' if new_state else 'Bỏ đánh dấu'} ({bm_count} bookmarks)")

    def _on_jump_next_bookmark(self) -> None:
        """Jump to the next bookmarked action (wraps around)."""
        if not self._actions:
            return
        current = self._selected_row()
        start = (current + 1) if current >= 0 else 0
        n = len(self._actions)
        for i in range(n):
            idx = (start + i) % n
            if self._actions[idx].bookmarked:
                self._select_tree_row(idx)
                self._status_label.setText(f"🔖 Bookmark #{idx + 1}")
                return
        self._status_label.setText("🔖 Không có bookmark nào")

    def _select_tree_row(self, row: int) -> None:
        """Select a root-level row in the tree view by index."""
        if 0 <= row < self._tree_model.rowCount():
            source_idx = self._tree_model.index(row, 0)
            proxy_idx = self._action_list_panel.filter_proxy.mapFromSource(source_idx)
            self._tree.setCurrentIndex(proxy_idx)

    def _on_tree_selection_changed(self, selected: Any, deselected: Any) -> None:
        """Update properties panel and breadcrumb when tree selection changes."""
        if not hasattr(self, "_props_panel"):
            return
        node = self._get_tree_selected_node()
        if node:
            self._props_panel.set_action(node.action)
        else:
            self._props_panel.clear()
        # P6: Update breadcrumb navigation
        self._action_list_panel.update_breadcrumb(node)

    def _on_minimap_action_clicked(self, idx: int) -> None:
        """Handle minimap click: select and scroll to the action."""
        self._select_tree_row(idx)

    def _sync_minimap_viewport(self) -> None:
        """Sync tree viewport to minimap visible range indicator."""
        if not hasattr(self, "_minimap"):
            return
        first_proxy = self._tree.indexAt(self._tree.viewport().rect().topLeft())
        last_proxy = self._tree.indexAt(self._tree.viewport().rect().bottomLeft())
        first_row = -1
        last_row = -1
        if first_proxy.isValid():
            src = self._action_list_panel.filter_proxy.mapToSource(first_proxy)
            if not src.parent().isValid():
                first_row = src.row()
        if last_proxy.isValid():
            src = self._action_list_panel.filter_proxy.mapToSource(last_proxy)
            if not src.parent().isValid():
                last_row = src.row()
        if first_row >= 0 and last_row >= 0:
            self._minimap.set_visible_range(first_row, last_row)

    def _show_sub_action_context_menu(self, menu, global_pos, node, idx) -> None:
        """Context menu for a sub-action (nested inside composite) in tree view."""
        action = node.action

        # Edit sub-action
        edit_act = menu.addAction("✏️ Sửa sub-action")
        edit_act.triggered.connect(lambda checked=False, n=node: self._edit_sub_action(n))

        # Toggle enable/disable
        toggle_label = "✗ Tắt" if action.enabled else "✓ Bật"
        toggle_act = menu.addAction(toggle_label)

        def _toggle(checked=False, a=action):
            a.enabled = not a.enabled
            self._refresh_table()

        toggle_act.triggered.connect(_toggle)

        # If this sub-action is itself composite, show THEN/ELSE/sub-action options
        if action.is_composite:
            menu.addSeparator()
            if action.has_branches:
                add_then = menu.addAction("➕ Thêm vào THEN")
                add_then.triggered.connect(lambda checked=False, a=action: self._add_nested_sub_action(a, "then"))
                add_else = menu.addAction("➕ Thêm vào ELSE")
                add_else.triggered.connect(lambda checked=False, a=action: self._add_nested_sub_action(a, "else"))
            else:
                add_child = menu.addAction("➕ Thêm sub-action")
                add_child.triggered.connect(lambda checked=False, a=action: self._add_nested_sub_action(a, "children"))

        menu.addSeparator()

        # Delete sub-action
        del_act = menu.addAction("🗑️ Xóa sub-action")
        del_act.triggered.connect(lambda checked=False, n=node: self._delete_sub_action(n))

        menu.exec(global_pos)

    def _show_placeholder_context_menu(self, menu, global_pos, node) -> None:
        """Context menu for a placeholder (empty branch) node.

        Shows 'Add action to [THEN/ELSE/sub]' option that opens ActionEditor
        and adds the new action directly to the parent composite's branch.
        """
        parent_node = node.parent
        if not parent_node or parent_node.action is None:
            return

        parent_action = parent_node.action
        label = node.branch_label  # THEN_EMPTY, ELSE_EMPTY, CHILDREN_EMPTY

        if "THEN" in label:
            branch = "then"
            menu_label = "➕ Thêm action vào THEN"
        elif "ELSE" in label:
            branch = "else"
            menu_label = "➕ Thêm action vào ELSE"
        else:
            branch = "children"
            menu_label = "➕ Thêm sub-action"

        add_act = menu.addAction(menu_label)
        add_act.triggered.connect(
            lambda checked=False, pa=parent_action, b=branch: self._add_nested_sub_action(pa, b)
        )
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
        self._exec_dialog(dialog)

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
        self._exec_dialog(dialog)

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
            empty_act.setEnabled(False)
            return
        for path in recent:
            short = Path(path).name
            act = self._recent_menu.addAction(f"📄 {short}")
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
        self._exec_dialog(dialog)

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

    def _on_quick_add(self, atype: str) -> None:
        """Open editor dialog pre-set to the selected action type."""
        try:
            dialog = ActionEditorDialog(self, macro_dir=self._macro_dir)
            # Pre-select the action type
            for i in range(dialog._type_combo.count()):
                if dialog._type_combo.itemData(i, Qt.ItemDataRole.UserRole) == atype:
                    dialog._type_combo.setCurrentIndex(i)
                    break
            dialog.action_ready.connect(self._handle_action_added)
            self._exec_dialog(dialog)
        except Exception:
            logger.exception("Quick-add failed for type: %s", atype)

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
        self._exec_dialog(dialog)

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
        self._exec_dialog(dialog)

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
            self._select_tree_row(row - 1)
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
            self._select_tree_row(row + 1)
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
            import json

            # Sub-action support: copy from tree node
            node = self._get_tree_selected_node()
            if node and node.parent is not None:
                data = [node.action.to_dict()]
                clipboard = QApplication.clipboard()
                if clipboard is None:
                    return

                clipboard.setText(json.dumps({"automacro_actions": data}, ensure_ascii=False, indent=2))
                self._status_label.setText("📄 Copied sub-action")
                logger.info("Copied sub-action to clipboard")
                return

            rows = self._selected_rows()
            if not rows:
                return
            data = [self._actions[r].to_dict() for r in sorted(rows)]
            clipboard = QApplication.clipboard()
            if clipboard is None:
                return
            clipboard.setText(json.dumps({"automacro_actions": data}, indent=2, ensure_ascii=False))
            self._status_label.setText(f"📄 Copied {len(rows)} action(s) to clipboard")
            logger.info("Copied %d action(s) to clipboard", len(rows))
        except Exception:
            logger.exception("Failed to copy actions")

    def _on_paste_actions(self) -> None:
        """Paste actions from clipboard JSON."""
        try:
            clipboard = QApplication.clipboard()
            if clipboard is None:
                return
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

        # Preflight check: block if errors, warn if warnings
        if not self._preflight_check():
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
        if self._current_file:
            self._engine.set_macro_file(self._current_file)
        self._engine.set_loop(
            count=self._loop_spin.value(),
            delay_ms=self._loop_delay_spin.value(),
            stop_on_error=self._stop_on_error_check.isChecked(),
        )
        self._engine.set_speed_factor(self._speed_spin.value())
        # Set jitter from playback panel
        jitter_pct = getattr(self, '_jitter_spin', None)
        if jitter_pct is not None:
            self._engine.set_jitter(jitter_pct.value() / 100.0)
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
        if 0 <= idx < self._tree_model.rowCount():
            self._select_tree_row(idx)
        self._refresh_variables()

    def _on_action_duration(self, idx: int, duration_ms: int) -> None:
        """H3: Propagate timing data from engine copy back to UI actions."""
        if 0 <= idx < len(self._actions):
            self._actions[idx].last_duration_ms = duration_ms

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
        if clipboard is None:
            return
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
        self._exec_dialog(dialog)

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
        """Update RAM usage and performance stats in status bar."""
        try:
            from core.memory_manager import MemoryManager

            stats = MemoryManager.instance().get_stats()
            # Compact inline display: RAM + perf
            text = f"RAM: {stats['current_mb']}/{stats['threshold_mb']}MB"
            avg_cap = stats.get('avg_capture_ms', 0)
            avg_match = stats.get('avg_match_ms', 0)
            if avg_cap > 0 or avg_match > 0:
                text += f" | ⚡ {avg_cap}ms"
            self._ram_label.setText(text)

            # Detailed tooltip on hover
            tooltip = (
                f"🧠 Bộ nhớ RAM\n"
                f"  Hiện tại: {stats['current_mb']} MB\n"
                f"  Baseline: {stats.get('baseline_mb', '?')} MB\n"
                f"  Đỉnh: {stats['peak_mb']} MB\n"
                f"  Ngưỡng: {stats['threshold_mb']} MB\n"
                f"  Dọn dẹp: {stats['cleanup_count']} lần\n"
                f"\n⚡ Hiệu năng\n"
                f"  Chụp MH: {stats.get('capture_count', 0)} lần (avg {avg_cap}ms)\n"
                f"  So khớp: {stats.get('match_count', 0)} lần (avg {avg_match}ms)\n"
                f"  Cache hit: {stats.get('cache_hits', 0)}\n"
                f"  Template cache: {stats.get('tpl_cache_size', 0)} ảnh"
            )
            self._ram_label.setToolTip(tooltip)
        except Exception:
            logger.debug("Failed to update RAM display", exc_info=True)

    def _on_help(self) -> None:
        """Open the in-app help dialog."""
        dlg = HelpDialog(self)
        dlg.exec()

    def _on_manage_triggers(self) -> None:
        """Open trigger management dialog."""
        from gui.trigger_dialog import TriggerDialog

        dlg = TriggerDialog(self._trigger_mgr, self._macro_dir, self)
        dlg.exec()
        # Auto-save triggers after dialog closes
        triggers_file = Path(self._macro_dir) / ".triggers.json"
        self._trigger_mgr.save_triggers(triggers_file)

    def _on_trigger_fire(self, config) -> None:
        """Handle trigger fire — load and play macro (thread-safe via QTimer)."""
        from PyQt6.QtCore import QTimer as _QTimer

        def _do_fire():
            # Safety: don't overlap with running engine
            if self._engine.isRunning():
                logger.info("Trigger %s skipped — engine already running", config.id)
                return
            if not config.macro_file or not Path(config.macro_file).exists():
                logger.warning("Trigger %s — macro file missing: %s", config.id, config.macro_file)
                return
            # Load macro
            try:
                actions = MacroEngine.load_macro(config.macro_file)
                self._actions = actions
                self._current_file = config.macro_file
                self._refresh_action_table()
                logger.info("Trigger %s — loaded %d actions from %s", config.id, len(actions), config.macro_file)
                # Run preflight
                if not self._preflight_check():
                    logger.warning("Trigger %s — preflight failed, not starting", config.id)
                    return
                self._start_new_engine()
            except Exception:
                logger.exception("Trigger %s — failed to load/start", config.id)

        _QTimer.singleShot(0, _do_fire)

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
        # Stop multi-run engines
        if hasattr(self, '_multi_run'):
            self._multi_run.stop_all_and_wait(3000)
        # Save and stop triggers
        triggers_file = Path(self._macro_dir) / ".triggers.json"
        self._trigger_mgr.save_triggers(triggers_file)
        self._trigger_mgr.stop()
        self._tray.hide()
        QApplication.quit()

    # ------------------------------------------------------------------ #
    # Window events
    # ------------------------------------------------------------------ #
    def _exec_dialog(self, dialog) -> None:
        """Run dialog.exec() while preserving the window's maximized state.

        PyQt6 on Windows can de-maximize the parent window when a modal
        QDialog is shown via exec().  This wrapper saves the state before
        and restores it afterward.
        """
        was_maximized = self.isMaximized()
        dialog.exec()
        if was_maximized and not self.isMaximized():
            self.showMaximized()

    def _show_from_tray(self) -> None:
        self.showNormal()
        self.activateWindow()
        self._exit_low_resource_mode()

    # ── Low Resource Mode (P2-C) ─────────────────────────
    # Reduce timer wake-ups when hidden in system tray to save CPU.
    # Normal: _ram_timer 5s, autosave 60s
    # Low:    _ram_timer 30s, autosave paused

    def _enter_low_resource_mode(self) -> None:
        """Slow down background timers when app is hidden in tray."""
        if getattr(self, '_low_resource_active', False):
            return  # Already in low resource mode
        self._low_resource_active = True

        # Slow RAM display timer: 5s → 30s (no one sees it while hidden)
        if hasattr(self, '_ram_timer') and self._ram_timer.isActive():
            self._ram_timer.setInterval(30_000)

        # Pause autosave — no UI edits possible while hidden
        if hasattr(self, '_autosave'):
            self._autosave.stop()

        logger.debug("Entered low resource mode (tray)")

    def _exit_low_resource_mode(self) -> None:
        """Restore normal timer intervals when app becomes visible."""
        if not getattr(self, '_low_resource_active', False):
            return  # Not in low resource mode
        self._low_resource_active = False

        # Restore RAM timer: 30s → 5s
        if hasattr(self, '_ram_timer') and self._ram_timer.isActive():
            self._ram_timer.setInterval(5_000)
        self._update_ram_display()  # Immediate refresh on restore

        # Resume autosave
        if hasattr(self, '_autosave'):
            self._autosave.start(
                save_callback=self._autosave_callback,
                current_file=getattr(self, '_current_file', None),
            )

        logger.debug("Exited low resource mode")

    def closeEvent(self, event: Optional[QCloseEvent]) -> None:
        # Always save window geometry/splitter sizes before close
        self._save_window_state()

        if self._config.get("ui", {}).get("minimize_to_tray", True):
            if event:
                event.ignore()
            self.hide()
            self._enter_low_resource_mode()
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

