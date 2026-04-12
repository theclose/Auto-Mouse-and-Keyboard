"""
Theme system for the AutoPilot application.
Single template + color palettes = DRY and maintainable.
"""

import os as _os
import tempfile as _tempfile

# Arrow image paths (generated at first theme build)
_arrow_dir: str = ""
_arrow_up: str = ""
_arrow_down: str = ""


def _ensure_arrow_images() -> tuple[str, str]:
    """Generate up/down arrow PNGs for SpinBox buttons (light color, transparent bg).

    Returns (up_path, down_path). Images are cached in a temp dir.
    """
    global _arrow_dir, _arrow_up, _arrow_down

    # Return cached paths if already generated
    if _arrow_up and _os.path.isfile(_arrow_up):
        return _arrow_up, _arrow_down

    _arrow_dir = _tempfile.mkdtemp(prefix="autopilot_arrows_")
    _arrow_up = _os.path.join(_arrow_dir, "up.png")
    _arrow_down = _os.path.join(_arrow_dir, "down.png")

    try:
        from PyQt6.QtCore import QPoint, Qt
        from PyQt6.QtGui import QColor, QImage, QPainter, QPolygon

        for path, points in [
            (_arrow_up, [(5, 1), (9, 7), (1, 7)]),    # ▲
            (_arrow_down, [(5, 7), (9, 1), (1, 1)]),  # ▼
        ]:
            img = QImage(10, 8, QImage.Format.Format_ARGB32)
            img.fill(QColor(0, 0, 0, 0))  # transparent
            p = QPainter(img)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            p.setBrush(QColor(200, 200, 220))  # visible light gray
            p.setPen(Qt.PenStyle.NoPen)
            p.drawPolygon(QPolygon([QPoint(*pt) for pt in points]))
            p.end()
            img.save(path)
    except Exception:
        # Fallback: create 1x1 transparent PNGs so QSS doesn't break
        for path in (_arrow_up, _arrow_down):
            with open(path, "wb") as f:
                # Minimal valid 1x1 transparent PNG
                f.write(
                    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
                    b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4"
                    b"\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05"
                    b"\x00\x01\r\n\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
                )

    return _arrow_up, _arrow_down

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
    "text_secondary": "#c0c0d0",
    "text_muted": "#9595a8",
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
    border-left: 1px solid {border};
    width: 22px;
}}
QSpinBox::up-button:hover, QSpinBox::down-button:hover,
QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover {{
    background-color: {bg_hover};
}}
QSpinBox::up-button:pressed, QSpinBox::down-button:pressed,
QDoubleSpinBox::up-button:pressed, QDoubleSpinBox::down-button:pressed {{
    background-color: {accent_dark};
}}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
    image: url({arrow_up});
    width: 10px;
    height: 8px;
}}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
    image: url({arrow_down});
    width: 10px;
    height: 8px;
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
QWidget#emptyOverlay {{
    padding: 40px;
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
    """Build QSS from template + color dict + arrow images."""
    up_path, down_path = _ensure_arrow_images()
    # Qt QSS requires forward slashes in image URLs, even on Windows
    merged = {
        **colors,
        "arrow_up": up_path.replace("\\", "/"),
        "arrow_down": down_path.replace("\\", "/"),
    }
    return _THEME_TEMPLATE.format(**merged)



ACCENT_PRESETS = {
    "Tím": {"accent": "#6c63ff", "accent_hover": "#8b83ff", "accent_dark": "#4a42d4"},
    "Xanh dương": {"accent": "#3498db", "accent_hover": "#5dade2", "accent_dark": "#2980b9"},
    "Xanh lá": {"accent": "#27ae60", "accent_hover": "#2ecc71", "accent_dark": "#1e8449"},
    "Đỏ": {"accent": "#e74c3c", "accent_hover": "#ec7063", "accent_dark": "#c0392b"},
    "Cam": {"accent": "#e67e22", "accent_hover": "#eb984e", "accent_dark": "#d35400"},
    "Hồng": {"accent": "#e84393", "accent_hover": "#fd79a8", "accent_dark": "#d63031"}
}

# Pre-built themes — lazy-loaded because _build_theme() now uses QPainter
# which requires QApplication to exist.
_DARK_THEME: str | None = None
_LIGHT_THEME: str | None = None


def __getattr__(name: str):
    """Module-level __getattr__ for lazy theme constants."""
    global _DARK_THEME, _LIGHT_THEME
    if name == "DARK_THEME":
        if _DARK_THEME is None:
            _DARK_THEME = _build_theme(DARK_COLORS)
        return _DARK_THEME
    if name == "LIGHT_THEME":
        if _LIGHT_THEME is None:
            _LIGHT_THEME = _build_theme(LIGHT_COLORS)
        return _LIGHT_THEME
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


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


def get_theme(preference: str = "auto", font_size: int = 10, accent: str = "Tím") -> str:
    """Return QSS string based on preference ('auto', 'dark', 'light').

    Args:
        preference: 'auto', 'dark', or 'light'
        font_size: Font size in pt (8-16, default 10)
        accent: Accent color preset name
    """
    font_size = max(8, min(16, font_size))
    
    if preference == "light":
        base_colors = dict(LIGHT_COLORS)
    elif preference == "dark":
        base_colors = dict(DARK_COLORS)
    else:
        base_colors = dict(LIGHT_COLORS) if get_system_theme() == "light" else dict(DARK_COLORS)
        
    if accent in ACCENT_PRESETS:
        base_colors.update(ACCENT_PRESETS[accent])
        
    qss = _build_theme(base_colors)

    # Apply font size (replace default 10pt)
    if font_size != 10:
        qss = qss.replace("font-size: 10pt;", f"font-size: {font_size}pt;")
    return qss
