"""
Dark-theme QSS styles for the AutoPilot application.
Modern, professional look with rounded corners and subtle gradients.
"""

# Color palette
COLORS = {
    "bg_primary": "#1a1b2e",
    "bg_secondary": "#232442",
    "bg_tertiary": "#2d2f54",
    "bg_hover": "#363866",
    "accent": "#6c63ff",
    "accent_hover": "#8b83ff",
    "accent_dark": "#4a42d4",
    "success": "#27ae60",
    "success_hover": "#2ecc71",
    "success_dark": "#1e8449",
    "warning": "#f39c12",
    "error": "#e74c3c",
    "error_hover": "#c0392b",
    "text_primary": "#e8e8f0",
    "text_secondary": "#ababc0",
    "text_muted": "#8a8aa8",
    "border": "#3a3c60",
    "border_light": "#4a4c70",
    "scrollbar": "#4a4c70",
    "scrollbar_hover": "#5a5c80",
    "crash_title": "#ff5555",
    "crash_bg": "#2b2b2b",
    "crash_text": "#f8f8f2",
    "crash_border": "#444444",
}

DARK_THEME = f"""
/* ---- Global ---- */
QWidget {{
    background-color: {COLORS["bg_primary"]};
    color: {COLORS["text_primary"]};
    font-family: "Segoe UI", "Roboto", sans-serif;
    font-size: 10pt;
}}

QMainWindow {{
    background-color: {COLORS["bg_primary"]};
}}

/* ---- Menu Bar ---- */
QMenuBar {{
    background-color: {COLORS["bg_secondary"]};
    color: {COLORS["text_primary"]};
    border-bottom: 1px solid {COLORS["border"]};
    padding: 2px;
}}

QMenuBar::item:selected {{
    background-color: {COLORS["bg_hover"]};
    border-radius: 4px;
}}

QMenu {{
    background-color: {COLORS["bg_secondary"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 6px;
    padding: 4px;
}}

QMenu::item {{
    padding: 6px 24px;
    border-radius: 4px;
}}

QMenu::item:selected {{
    background-color: {COLORS["accent"]};
}}

/* ---- Toolbar ---- */
QToolBar {{
    background-color: {COLORS["bg_secondary"]};
    border-bottom: 1px solid {COLORS["border"]};
    padding: 4px 8px;
    spacing: 6px;
}}

QToolButton {{
    background-color: {COLORS["bg_tertiary"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 6px;
    padding: 6px 12px;
    color: {COLORS["text_primary"]};
    font-weight: 500;
}}

QToolButton:hover {{
    background-color: {COLORS["bg_hover"]};
    border-color: {COLORS["accent"]};
}}

QToolButton:pressed {{
    background-color: {COLORS["accent_dark"]};
}}

QToolButton:checked {{
    background-color: {COLORS["accent"]};
    border-color: {COLORS["accent"]};
}}

/* ---- Push Button ---- */
QPushButton {{
    background-color: {COLORS["bg_tertiary"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 6px;
    padding: 8px 16px;
    color: {COLORS["text_primary"]};
    font-weight: 500;
    min-height: 32px;
}}

QPushButton:hover {{
    background-color: {COLORS["bg_hover"]};
    border-color: {COLORS["accent"]};
}}

QPushButton:pressed {{
    background-color: {COLORS["accent_dark"]};
}}

QPushButton:disabled {{
    background-color: {COLORS["bg_primary"]};
    color: {COLORS["text_muted"]};
    border-color: {COLORS["bg_tertiary"]};
    font-style: italic;
}}

QPushButton#primaryButton {{
    background-color: {COLORS["accent"]};
    border-color: {COLORS["accent"]};
    color: white;
}}

QPushButton#primaryButton:hover {{
    background-color: {COLORS["accent_hover"]};
}}

QPushButton#dangerButton {{
    background-color: {COLORS["error"]};
    border-color: {COLORS["error"]};
    color: white;
}}

QPushButton#successButton {{
    background-color: {COLORS["success"]};
    border-color: {COLORS["success"]};
    color: white;
}}

/* ---- Table / List ---- */
QTableWidget, QListWidget, QTreeWidget {{
    background-color: {COLORS["bg_secondary"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 6px;
    gridline-color: {COLORS["border"]};
    outline: none;
}}

QTableWidget::item, QListWidget::item {{
    padding: 6px 8px;
    border-bottom: 1px solid {COLORS["bg_tertiary"]};
}}

QTableWidget::item:selected, QListWidget::item:selected {{
    background-color: {COLORS["accent"]};
    color: white;
}}

QTableWidget::item:hover, QListWidget::item:hover {{
    background-color: {COLORS["bg_hover"]};
}}

QHeaderView::section {{
    background-color: {COLORS["bg_tertiary"]};
    color: {COLORS["text_secondary"]};
    border: none;
    border-bottom: 2px solid {COLORS["accent"]};
    padding: 8px;
    font-weight: 600;
    text-transform: uppercase;
    font-size: 8pt;
}}

/* ---- Input Fields ---- */
QLineEdit, QTextEdit, QSpinBox, QDoubleSpinBox {{
    background-color: {COLORS["bg_secondary"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 6px;
    padding: 6px 10px;
    color: {COLORS["text_primary"]};
    selection-background-color: {COLORS["accent"]};
}}

QLineEdit:focus, QTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
    border-color: {COLORS["accent"]};
}}

QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
    background-color: {COLORS["bg_tertiary"]};
    border: none;
    width: 20px;
}}

/* ---- Combo Box ---- */
QComboBox {{
    background-color: {COLORS["bg_secondary"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 6px;
    padding: 6px 10px;
    color: {COLORS["text_primary"]};
    min-height: 20px;
}}

QComboBox:hover {{
    border-color: {COLORS["accent"]};
}}

QComboBox::drop-down {{
    border: none;
    width: 24px;
}}

QComboBox QAbstractItemView {{
    background-color: {COLORS["bg_secondary"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 6px;
    selection-background-color: {COLORS["accent"]};
}}

/* ---- Group Box ---- */
QGroupBox {{
    background-color: {COLORS["bg_secondary"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 16px;
    font-weight: 600;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 2px 12px;
    color: {COLORS["accent"]};
}}

/* ---- Tabs ---- */
QTabWidget::pane {{
    background-color: {COLORS["bg_secondary"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 6px;
}}

QTabBar::tab {{
    background-color: {COLORS["bg_tertiary"]};
    color: {COLORS["text_secondary"]};
    border: 1px solid {COLORS["border"]};
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    padding: 8px 16px;
    margin-right: 2px;
}}

QTabBar::tab:selected {{
    background-color: {COLORS["bg_secondary"]};
    color: {COLORS["accent"]};
    border-bottom: 2px solid {COLORS["accent"]};
}}

/* ---- Scroll Bars ---- */
QScrollBar:vertical {{
    background-color: transparent;
    width: 10px;
    border-radius: 5px;
}}

QScrollBar::handle:vertical {{
    background-color: {COLORS["scrollbar"]};
    border-radius: 5px;
    min-height: 30px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: {COLORS["scrollbar_hover"]};
}}

QScrollBar::add-line, QScrollBar::sub-line {{
    height: 0px;
}}

QScrollBar:horizontal {{
    background-color: transparent;
    height: 10px;
    border-radius: 5px;
}}

QScrollBar::handle:horizontal {{
    background-color: {COLORS["scrollbar"]};
    border-radius: 5px;
    min-width: 30px;
}}

/* ---- Status Bar ---- */
QStatusBar {{
    background-color: {COLORS["bg_secondary"]};
    border-top: 1px solid {COLORS["border"]};
    color: {COLORS["text_secondary"]};
    padding: 4px;
}}

/* ---- Progress Bar ---- */
QProgressBar {{
    background-color: {COLORS["bg_tertiary"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 4px;
    text-align: center;
    color: {COLORS["text_primary"]};
    height: 16px;
}}

QProgressBar::chunk {{
    background-color: {COLORS["accent"]};
    border-radius: 4px;
}}

/* ---- Splitter ---- */
QSplitter::handle {{
    background-color: {COLORS["border"]};
    width: 2px;
    height: 2px;
}}

/* ---- Labels ---- */
QLabel {{
    background-color: transparent;
}}

QLabel#headerLabel {{
    font-size: 12pt;
    font-weight: 700;
    color: {COLORS["text_primary"]};
}}

QLabel#subtitleLabel {{
    font-size: 9pt;
    color: {COLORS["text_secondary"]};
}}

/* ---- CheckBox ---- */
QCheckBox {{
    spacing: 8px;
    color: {COLORS["text_primary"]};
}}

QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 2px solid {COLORS["border"]};
    background-color: {COLORS["bg_secondary"]};
}}

QCheckBox::indicator:checked {{
    background-color: {COLORS["accent"]};
    border-color: {COLORS["accent"]};
}}

/* ---- ToolTip ---- */
QToolTip {{
    background-color: {COLORS["bg_tertiary"]};
    color: {COLORS["text_primary"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 4px;
    padding: 4px 8px;
}}

/* ---- Dialog ---- */
QDialog {{
    background-color: {COLORS["bg_primary"]};
}}

/* ---- Play Button (Prominent) ---- */
QPushButton#playButton {{
    background-color: {COLORS["success"]};
    border: 2px solid {COLORS["success"]};
    border-radius: 8px;
    color: white;
    font-size: 14pt;
    font-weight: 700;
    letter-spacing: 2px;
    min-height: 44px;
    padding: 8px 20px;
}}

QPushButton#playButton:hover {{
    background-color: {COLORS["success_hover"]};
    border-color: {COLORS["success_hover"]};
}}

QPushButton#playButton:pressed {{
    background-color: {COLORS["success_dark"]};
}}

QPushButton#playButton:disabled {{
    background-color: {COLORS["bg_tertiary"]};
    border-color: {COLORS["border"]};
    color: {COLORS["text_muted"]};
}}

/* ---- Control Button (Pause) ---- */
QPushButton#controlButton {{
    background-color: {COLORS["accent"]};
    border: 1px solid {COLORS["accent"]};
    border-radius: 6px;
    color: white;
    font-weight: 600;
    min-height: 32px;
    padding: 6px 16px;
}}

QPushButton#controlButton:hover {{
    background-color: {COLORS["accent_hover"]};
}}

QPushButton#controlButton:disabled {{
    background-color: {COLORS["bg_tertiary"]};
    border-color: {COLORS["border"]};
    color: {COLORS["text_muted"]};
}}

/* ---- Danger Button (Stop) ---- */
QPushButton#dangerButton:hover {{
    background-color: {COLORS["error_hover"]};
    border-color: {COLORS["error_hover"]};
}}

QPushButton#dangerButton:disabled {{
    background-color: {COLORS["bg_tertiary"]};
    border-color: {COLORS["border"]};
    color: {COLORS["text_muted"]};
}}

/* ---- Execution Log ---- */
QListWidget#execLog {{
    font-size: 9pt;
    font-family: "Consolas", "Cascadia Code", monospace;
    background-color: {COLORS["bg_primary"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 4px;
}}

QListWidget#execLog::item {{
    padding: 2px 6px;
    border-bottom: 1px solid {COLORS["bg_tertiary"]};
}}

/* ---- Application Log (Bottom Panel) ---- */
QPlainTextEdit#appLog {{
    font-size: 9pt;
    font-family: "Consolas", "Cascadia Code", monospace;
    background-color: {COLORS["bg_primary"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 4px;
    color: {COLORS["text_secondary"]};
    padding: 4px;
}}

/* ---- Crash Dialog ---- */
QLabel#crashTitle {{
    font-size: 14px;
    font-weight: bold;
    color: {COLORS["crash_title"]};
}}

QTextEdit#crashTraceback {{
    background-color: {COLORS["crash_bg"]};
    color: {COLORS["crash_text"]};
    border: 1px solid {COLORS["crash_border"]};
    border-radius: 4px;
}}

/* ---- Empty Overlay ---- */
QLabel#emptyOverlay {{
    font-size: 12pt;
    color: {COLORS["text_secondary"]};
    padding: 40px;
    background-color: transparent;
}}

/* ---- Focus Ring (Keyboard Accessibility) ---- */
QPushButton:focus, QSpinBox:focus, QDoubleSpinBox:focus,
QComboBox:focus, QLineEdit:focus, QCheckBox:focus,
QListWidget:focus, QTableWidget:focus {{
    outline: 3px solid {COLORS["accent"]};
    outline-offset: 1px;
}}
"""

# ── Light theme ──────────────────────────────────────────────
LIGHT_COLORS = {
    "bg_primary": "#f5f5f8",
    "bg_secondary": "#ffffff",
    "bg_tertiary": "#e8e8f0",
    "bg_hover": "#dcdce8",
    "accent": "#6c63ff",
    "accent_hover": "#5a52e0",
    "accent_dark": "#4a42d4",
    "success": "#27ae60",
    "success_hover": "#2ecc71",
    "success_dark": "#1e8449",
    "warning": "#f39c12",
    "error": "#e74c3c",
    "error_hover": "#c0392b",
    "text_primary": "#1a1a2e",
    "text_secondary": "#555570",
    "text_muted": "#8888a0",
    "border": "#d0d0e0",
    "border_light": "#e0e0f0",
    "scrollbar": "#c0c0d0",
    "scrollbar_hover": "#a0a0b8",
}

LIGHT_THEME = f"""
/* ---- Global ---- */
QWidget {{
    background-color: {LIGHT_COLORS["bg_primary"]};
    color: {LIGHT_COLORS["text_primary"]};
    font-family: "Segoe UI", "Roboto", sans-serif;
    font-size: 10pt;
}}
QMainWindow {{ background-color: {LIGHT_COLORS["bg_primary"]}; }}

/* ---- Menu Bar ---- */
QMenuBar {{
    background-color: {LIGHT_COLORS["bg_secondary"]};
    color: {LIGHT_COLORS["text_primary"]};
    border-bottom: 1px solid {LIGHT_COLORS["border"]};
    padding: 2px;
}}
QMenuBar::item:selected {{ background-color: {LIGHT_COLORS["bg_hover"]}; border-radius: 4px; }}
QMenu {{
    background-color: {LIGHT_COLORS["bg_secondary"]};
    border: 1px solid {LIGHT_COLORS["border"]};
    border-radius: 6px; padding: 4px;
}}
QMenu::item {{ padding: 6px 24px; border-radius: 4px; }}
QMenu::item:selected {{ background-color: {LIGHT_COLORS["accent"]}; color: white; }}

/* ---- Toolbar ---- */
QToolBar {{
    background-color: {LIGHT_COLORS["bg_secondary"]};
    border-bottom: 1px solid {LIGHT_COLORS["border"]};
    padding: 4px 8px; spacing: 6px;
}}
QToolButton {{
    background-color: {LIGHT_COLORS["bg_tertiary"]};
    border: 1px solid {LIGHT_COLORS["border"]};
    border-radius: 6px; padding: 6px 12px;
    color: {LIGHT_COLORS["text_primary"]}; font-weight: 500;
}}
QToolButton:hover {{ background-color: {LIGHT_COLORS["bg_hover"]}; border-color: {LIGHT_COLORS["accent"]}; }}
QToolButton:pressed {{ background-color: {LIGHT_COLORS["accent_dark"]}; color: white; }}
QToolButton:checked {{ background-color: {LIGHT_COLORS["accent"]}; color: white; }}

/* ---- Push Button ---- */
QPushButton {{
    background-color: {LIGHT_COLORS["bg_tertiary"]};
    border: 1px solid {LIGHT_COLORS["border"]};
    border-radius: 6px; padding: 8px 16px;
    color: {LIGHT_COLORS["text_primary"]}; font-weight: 500;
    min-height: 32px;
}}
QPushButton:hover {{ background-color: {LIGHT_COLORS["bg_hover"]}; border-color: {LIGHT_COLORS["accent"]}; }}
QPushButton:pressed {{ background-color: {LIGHT_COLORS["accent_dark"]}; color: white; }}
QPushButton:disabled {{
    background-color: {LIGHT_COLORS["bg_primary"]};
    color: {LIGHT_COLORS["text_muted"]};
    border-color: {LIGHT_COLORS["bg_tertiary"]};
    font-style: italic;
}}
QPushButton#primaryButton {{ background-color: {LIGHT_COLORS["accent"]}; color: white; border-color: {LIGHT_COLORS["accent"]}; }}
QPushButton#primaryButton:hover {{ background-color: {LIGHT_COLORS["accent_hover"]}; }}
QPushButton#dangerButton {{ background-color: {LIGHT_COLORS["error"]}; color: white; }}
QPushButton#successButton {{ background-color: {LIGHT_COLORS["success"]}; color: white; }}

/* ---- Table / List ---- */
QTableWidget, QListWidget, QTreeWidget {{
    background-color: {LIGHT_COLORS["bg_secondary"]};
    border: 1px solid {LIGHT_COLORS["border"]};
    border-radius: 6px; gridline-color: {LIGHT_COLORS["border"]};
    outline: none;
}}
QTableWidget::item:selected, QListWidget::item:selected {{
    background-color: {LIGHT_COLORS["accent"]}; color: white;
}}
QTableWidget::item:hover, QListWidget::item:hover {{
    background-color: {LIGHT_COLORS["bg_hover"]};
}}
QHeaderView::section {{
    background-color: {LIGHT_COLORS["bg_tertiary"]};
    color: {LIGHT_COLORS["text_secondary"]};
    border: none; border-bottom: 2px solid {LIGHT_COLORS["accent"]};
    padding: 8px; font-weight: 600; font-size: 8pt;
}}

/* ---- Input Fields ---- */
QLineEdit, QTextEdit, QSpinBox, QDoubleSpinBox {{
    background-color: {LIGHT_COLORS["bg_secondary"]};
    border: 1px solid {LIGHT_COLORS["border"]};
    border-radius: 6px; padding: 6px 10px;
    color: {LIGHT_COLORS["text_primary"]};
    selection-background-color: {LIGHT_COLORS["accent"]};
}}
QLineEdit:focus, QTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
    border-color: {LIGHT_COLORS["accent"]};
}}

/* ---- Combo Box ---- */
QComboBox {{
    background-color: {LIGHT_COLORS["bg_secondary"]};
    border: 1px solid {LIGHT_COLORS["border"]};
    border-radius: 6px; padding: 6px 10px;
    color: {LIGHT_COLORS["text_primary"]}; min-height: 20px;
}}
QComboBox:hover {{ border-color: {LIGHT_COLORS["accent"]}; }}
QComboBox QAbstractItemView {{
    background-color: {LIGHT_COLORS["bg_secondary"]};
    border: 1px solid {LIGHT_COLORS["border"]};
    selection-background-color: {LIGHT_COLORS["accent"]};
}}

/* ---- Group Box ---- */
QGroupBox {{
    background-color: {LIGHT_COLORS["bg_secondary"]};
    border: 1px solid {LIGHT_COLORS["border"]};
    border-radius: 8px; margin-top: 12px; padding-top: 16px; font-weight: 600;
}}
QGroupBox::title {{ subcontrol-origin: margin; padding: 2px 12px; color: {LIGHT_COLORS["accent"]}; }}

/* ---- Tabs ---- */
QTabWidget::pane {{ background-color: {LIGHT_COLORS["bg_secondary"]}; border: 1px solid {LIGHT_COLORS["border"]}; border-radius: 6px; }}
QTabBar::tab {{
    background-color: {LIGHT_COLORS["bg_tertiary"]};
    color: {LIGHT_COLORS["text_secondary"]};
    border: 1px solid {LIGHT_COLORS["border"]}; border-bottom: none;
    border-top-left-radius: 6px; border-top-right-radius: 6px;
    padding: 8px 16px; margin-right: 2px;
}}
QTabBar::tab:selected {{ background-color: {LIGHT_COLORS["bg_secondary"]}; color: {LIGHT_COLORS["accent"]}; border-bottom: 2px solid {LIGHT_COLORS["accent"]}; }}

/* ---- Scroll Bars ---- */
QScrollBar:vertical {{ background-color: transparent; width: 10px; border-radius: 5px; }}
QScrollBar::handle:vertical {{ background-color: {LIGHT_COLORS["scrollbar"]}; border-radius: 5px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background-color: {LIGHT_COLORS["scrollbar_hover"]}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0px; }}
QScrollBar:horizontal {{ background-color: transparent; height: 10px; border-radius: 5px; }}
QScrollBar::handle:horizontal {{ background-color: {LIGHT_COLORS["scrollbar"]}; border-radius: 5px; min-width: 30px; }}

/* ---- Status / Progress ---- */
QStatusBar {{ background-color: {LIGHT_COLORS["bg_secondary"]}; border-top: 1px solid {LIGHT_COLORS["border"]}; color: {LIGHT_COLORS["text_secondary"]}; }}
QProgressBar {{
    background-color: {LIGHT_COLORS["bg_tertiary"]};
    border: 1px solid {LIGHT_COLORS["border"]};
    border-radius: 4px; text-align: center; height: 16px;
}}
QProgressBar::chunk {{ background-color: {LIGHT_COLORS["accent"]}; border-radius: 4px; }}

/* ---- Labels ---- */
QLabel {{ background-color: transparent; }}
QLabel#headerLabel {{ font-size: 12pt; font-weight: 700; }}
QLabel#subtitleLabel {{ font-size: 9pt; color: {LIGHT_COLORS["text_secondary"]}; }}
QLabel#emptyOverlay {{ font-size: 12pt; color: {LIGHT_COLORS["text_secondary"]}; padding: 40px; }}

/* ---- CheckBox ---- */
QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{ width: 18px; height: 18px; border-radius: 4px; border: 2px solid {LIGHT_COLORS["border"]}; background-color: {LIGHT_COLORS["bg_secondary"]}; }}
QCheckBox::indicator:checked {{ background-color: {LIGHT_COLORS["accent"]}; border-color: {LIGHT_COLORS["accent"]}; }}

/* ---- ToolTip ---- */
QToolTip {{ background-color: {LIGHT_COLORS["bg_secondary"]}; color: {LIGHT_COLORS["text_primary"]}; border: 1px solid {LIGHT_COLORS["border"]}; border-radius: 4px; padding: 4px 8px; }}
QDialog {{ background-color: {LIGHT_COLORS["bg_primary"]}; }}

/* ---- Play / Control / Danger Buttons ---- */
QPushButton#playButton {{
    background-color: {LIGHT_COLORS["success"]}; border: 2px solid {LIGHT_COLORS["success"]};
    border-radius: 8px; color: white; font-size: 14pt; font-weight: 700;
    letter-spacing: 2px; min-height: 44px; padding: 8px 20px;
}}
QPushButton#playButton:hover {{ background-color: {LIGHT_COLORS["success_hover"]}; }}
QPushButton#playButton:disabled {{ background-color: {LIGHT_COLORS["bg_tertiary"]}; border-color: {LIGHT_COLORS["border"]}; color: {LIGHT_COLORS["text_muted"]}; }}
QPushButton#controlButton {{ background-color: {LIGHT_COLORS["accent"]}; color: white; border-radius: 6px; font-weight: 600; min-height: 32px; }}
QPushButton#controlButton:hover {{ background-color: {LIGHT_COLORS["accent_hover"]}; }}
QPushButton#dangerButton:hover {{ background-color: {LIGHT_COLORS["error_hover"]}; }}

/* ---- Logs ---- */
QListWidget#execLog {{ font-size: 9pt; font-family: "Consolas", monospace; background-color: {LIGHT_COLORS["bg_secondary"]}; border: 1px solid {LIGHT_COLORS["border"]}; }}
QPlainTextEdit#appLog {{ font-size: 9pt; font-family: "Consolas", monospace; background-color: {LIGHT_COLORS["bg_secondary"]}; border: 1px solid {LIGHT_COLORS["border"]}; color: {LIGHT_COLORS["text_secondary"]}; }}

/* ---- Focus Ring ---- */
QPushButton:focus, QSpinBox:focus, QDoubleSpinBox:focus,
QComboBox:focus, QLineEdit:focus, QCheckBox:focus,
QListWidget:focus, QTableWidget:focus {{
    outline: 3px solid {LIGHT_COLORS["accent"]};
    outline-offset: 1px;
}}
"""


# ── Theme helpers ────────────────────────────────────────────

def get_system_theme() -> str:
    """Detect Windows dark/light theme setting. Returns 'dark' or 'light'."""
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        )
        value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        winreg.CloseKey(key)
        return "light" if value == 1 else "dark"
    except Exception:
        return "dark"  # fallback


def get_theme(preference: str = "auto") -> str:
    """Return QSS string based on preference ('auto', 'dark', 'light')."""
    if preference == "light":
        return LIGHT_THEME
    elif preference == "dark":
        return DARK_THEME
    else:  # auto
        return LIGHT_THEME if get_system_theme() == "light" else DARK_THEME
