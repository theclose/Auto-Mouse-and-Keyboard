"""
Theme system for the AutoPilot application.
Single template + color palettes = DRY and maintainable.
"""

# ── Color Palettes ──────────────────────────────────────────

DARK_COLORS = {
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
    "crash_title": "#cc0000",
    "crash_bg": "#fff5f5",
    "crash_text": "#1a1a2e",
    "crash_border": "#e0e0e0",
}

# Back-compat alias used by some imports
COLORS = DARK_COLORS

# ── Single QSS Template ────────────────────────────────────

_THEME_TEMPLATE = """
/* ---- Global ---- */
QWidget {{
    background-color: {bg_primary};
    color: {text_primary};
    font-family: "Segoe UI", "Roboto", sans-serif;
    font-size: 10pt;
}}
QMainWindow {{ background-color: {bg_primary}; }}

/* ---- Menu Bar ---- */
QMenuBar {{
    background-color: {bg_secondary};
    color: {text_primary};
    border-bottom: 1px solid {border};
    padding: 2px;
}}
QMenuBar::item:selected {{ background-color: {bg_hover}; border-radius: 4px; }}
QMenu {{
    background-color: {bg_secondary};
    border: 1px solid {border};
    border-radius: 6px;
    padding: 4px;
}}
QMenu::item {{ padding: 6px 24px; border-radius: 4px; }}
QMenu::item:selected {{ background-color: {accent}; color: white; }}

/* ---- Toolbar ---- */
QToolBar {{
    background-color: {bg_secondary};
    border-bottom: 1px solid {border};
    padding: 4px 8px;
    spacing: 6px;
}}
QToolButton {{
    background-color: {bg_tertiary};
    border: 1px solid {border};
    border-radius: 6px;
    padding: 6px 12px;
    color: {text_primary};
    font-weight: 500;
}}
QToolButton:hover {{ background-color: {bg_hover}; border-color: {accent}; }}
QToolButton:pressed {{ background-color: {accent_dark}; color: white; }}
QToolButton:checked {{ background-color: {accent}; border-color: {accent}; color: white; }}

/* ---- Push Button ---- */
QPushButton {{
    background-color: {bg_tertiary};
    border: 1px solid {border};
    border-radius: 6px;
    padding: 8px 16px;
    color: {text_primary};
    font-weight: 500;
    min-height: 32px;
}}
QPushButton:hover {{ background-color: {bg_hover}; border-color: {accent}; }}
QPushButton:pressed {{ background-color: {accent_dark}; color: white; }}
QPushButton:disabled {{
    background-color: {bg_primary};
    color: {text_muted};
    border-color: {bg_tertiary};
    font-style: italic;
}}
QPushButton#primaryButton {{ background-color: {accent}; border-color: {accent}; color: white; }}
QPushButton#primaryButton:hover {{ background-color: {accent_hover}; }}
QPushButton#dangerButton {{ background-color: {error}; border-color: {error}; color: white; }}
QPushButton#successButton {{ background-color: {success}; border-color: {success}; color: white; }}

/* ---- Table / List ---- */
QTableWidget, QListWidget, QTreeWidget {{
    background-color: {bg_secondary};
    border: 1px solid {border};
    border-radius: 6px;
    gridline-color: {border};
    outline: none;
}}
QTableWidget::item, QListWidget::item {{ padding: 6px 8px; border-bottom: 1px solid {bg_tertiary}; }}
QTableWidget::item:selected, QListWidget::item:selected {{ background-color: {accent}; color: white; }}
QTableWidget::item:hover, QListWidget::item:hover {{ background-color: {bg_hover}; }}
QHeaderView::section {{
    background-color: {bg_tertiary};
    color: {text_secondary};
    border: none;
    border-bottom: 2px solid {accent};
    padding: 8px;
    font-weight: 600;
    text-transform: uppercase;
    font-size: 8pt;
}}

/* ---- Input Fields ---- */
QLineEdit, QTextEdit, QSpinBox, QDoubleSpinBox {{
    background-color: {bg_secondary};
    border: 1px solid {border};
    border-radius: 6px;
    padding: 6px 10px;
    color: {text_primary};
    selection-background-color: {accent};
}}
QLineEdit:focus, QTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
    border-color: {accent};
}}
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
    background-color: {bg_tertiary};
    border: none;
    width: 20px;
}}

/* ---- Combo Box ---- */
QComboBox {{
    background-color: {bg_secondary};
    border: 1px solid {border};
    border-radius: 6px;
    padding: 6px 10px;
    color: {text_primary};
    min-height: 20px;
}}
QComboBox:hover {{ border-color: {accent}; }}
QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox QAbstractItemView {{
    background-color: {bg_secondary};
    border: 1px solid {border};
    border-radius: 6px;
    selection-background-color: {accent};
}}

/* ---- Group Box ---- */
QGroupBox {{
    background-color: {bg_secondary};
    border: 1px solid {border};
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 16px;
    font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 2px 12px;
    color: {accent};
}}

/* ---- Tabs ---- */
QTabWidget::pane {{
    background-color: {bg_secondary};
    border: 1px solid {border};
    border-radius: 6px;
}}
QTabBar::tab {{
    background-color: {bg_tertiary};
    color: {text_secondary};
    border: 1px solid {border};
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    padding: 8px 16px;
    margin-right: 2px;
}}
QTabBar::tab:selected {{
    background-color: {bg_secondary};
    color: {accent};
    border-bottom: 2px solid {accent};
}}

/* ---- Scroll Bars ---- */
QScrollBar:vertical {{ background-color: transparent; width: 10px; border-radius: 5px; }}
QScrollBar::handle:vertical {{ background-color: {scrollbar}; border-radius: 5px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background-color: {scrollbar_hover}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0px; }}
QScrollBar:horizontal {{ background-color: transparent; height: 10px; border-radius: 5px; }}
QScrollBar::handle:horizontal {{ background-color: {scrollbar}; border-radius: 5px; min-width: 30px; }}

/* ---- Status Bar ---- */
QStatusBar {{
    background-color: {bg_secondary};
    border-top: 1px solid {border};
    color: {text_secondary};
    padding: 4px;
}}

/* ---- Progress Bar ---- */
QProgressBar {{
    background-color: {bg_tertiary};
    border: 1px solid {border};
    border-radius: 4px;
    text-align: center;
    color: {text_primary};
    height: 16px;
}}
QProgressBar::chunk {{ background-color: {accent}; border-radius: 4px; }}

/* ---- Splitter ---- */
QSplitter::handle {{ background-color: {border}; width: 2px; height: 2px; }}

/* ---- Labels ---- */
QLabel {{ background-color: transparent; }}
QLabel#headerLabel {{ font-size: 12pt; font-weight: 700; color: {text_primary}; }}
QLabel#subtitleLabel {{ font-size: 9pt; color: {text_secondary}; }}

/* ---- CheckBox ---- */
QCheckBox {{ spacing: 8px; color: {text_primary}; }}
QCheckBox::indicator {{
    width: 18px; height: 18px; border-radius: 4px;
    border: 2px solid {border}; background-color: {bg_secondary};
}}
QCheckBox::indicator:checked {{ background-color: {accent}; border-color: {accent}; }}

/* ---- ToolTip ---- */
QToolTip {{
    background-color: {bg_tertiary};
    color: {text_primary};
    border: 1px solid {border};
    border-radius: 4px;
    padding: 4px 8px;
}}

/* ---- Dialog ---- */
QDialog {{ background-color: {bg_primary}; }}

/* ---- Play Button (Prominent) ---- */
QPushButton#playButton {{
    background-color: {success};
    border: 2px solid {success};
    border-radius: 8px;
    color: white;
    font-size: 14pt;
    font-weight: 700;
    letter-spacing: 2px;
    min-height: 44px;
    padding: 8px 20px;
}}
QPushButton#playButton:hover {{ background-color: {success_hover}; border-color: {success_hover}; }}
QPushButton#playButton:pressed {{ background-color: {success_dark}; }}
QPushButton#playButton:disabled {{
    background-color: {bg_tertiary}; border-color: {border}; color: {text_muted};
}}

/* ---- Control Button (Pause) ---- */
QPushButton#controlButton {{
    background-color: {accent};
    border: 1px solid {accent};
    border-radius: 6px;
    color: white;
    font-weight: 600;
    min-height: 32px;
    padding: 6px 16px;
}}
QPushButton#controlButton:hover {{ background-color: {accent_hover}; }}
QPushButton#controlButton:disabled {{
    background-color: {bg_tertiary}; border-color: {border}; color: {text_muted};
}}

/* ---- Danger Button (Stop) ---- */
QPushButton#dangerButton:hover {{ background-color: {error_hover}; border-color: {error_hover}; }}
QPushButton#dangerButton:disabled {{
    background-color: {bg_tertiary}; border-color: {border}; color: {text_muted};
}}

/* ---- Execution Log ---- */
QListWidget#execLog {{
    font-size: 9pt;
    font-family: "Consolas", "Cascadia Code", monospace;
    background-color: {bg_primary};
    border: 1px solid {border};
    border-radius: 4px;
}}
QListWidget#execLog::item {{ padding: 2px 6px; border-bottom: 1px solid {bg_tertiary}; }}

/* ---- Application Log (Bottom Panel) ---- */
QPlainTextEdit#appLog {{
    font-size: 9pt;
    font-family: "Consolas", "Cascadia Code", monospace;
    background-color: {bg_primary};
    border: 1px solid {border};
    border-radius: 4px;
    color: {text_secondary};
    padding: 4px;
}}

/* ---- Crash Dialog ---- */
QLabel#crashTitle {{ font-size: 14px; font-weight: bold; color: {crash_title}; }}
QTextEdit#crashTraceback {{
    background-color: {crash_bg}; color: {crash_text};
    border: 1px solid {crash_border}; border-radius: 4px;
}}

/* ---- Empty Overlay ---- */
QLabel#emptyOverlay {{
    font-size: 12pt; color: {text_secondary}; padding: 40px;
    background-color: transparent;
}}

/* ---- Focus Ring (Keyboard Accessibility) ---- */
QPushButton:focus, QSpinBox:focus, QDoubleSpinBox:focus,
QComboBox:focus, QLineEdit:focus, QCheckBox:focus,
QListWidget:focus, QTableWidget:focus {{
    outline: 3px solid {accent};
    outline-offset: 1px;
}}
"""


def _build_theme(colors: dict) -> str:
    """Build QSS from template + color dict."""
    return _THEME_TEMPLATE.format(**colors)


# Pre-built themes for backward compatibility
DARK_THEME = _build_theme(DARK_COLORS)
LIGHT_THEME = _build_theme(LIGHT_COLORS)


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
        return "dark"


def get_theme(preference: str = "auto") -> str:
    """Return QSS string based on preference ('auto', 'dark', 'light')."""
    if preference == "light":
        return LIGHT_THEME
    elif preference == "dark":
        return DARK_THEME
    else:
        return LIGHT_THEME if get_system_theme() == "light" else DARK_THEME
