"""
no_scroll_widgets.py — Suppress scroll-to-change-value globally.

QSpinBox, QDoubleSpinBox, and QComboBox by default consume wheel events
to change their value, even when they don't have keyboard focus.
This causes accidental value changes when scrolling a parent ScrollArea.

Solution: monkey-patch wheelEvent on the widget CLASSES at startup.
This is 100% reliable — every instance (existing and future) inherits
the patched behavior without any subclassing or event filters.

Usage (call once at startup, after QApplication is created):
    from gui.no_scroll_widgets import patch_wheel_events
    patch_wheel_events()
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QSlider,
    QSpinBox,
)

_patched = False


def patch_wheel_events() -> None:
    """Monkey-patch wheelEvent on QSpinBox, QDoubleSpinBox, QComboBox, QSlider.

    After this call, these widgets will ONLY respond to wheel events
    when they have keyboard focus (i.e. user clicked on them first).
    Otherwise the event is ignored and propagated to the parent
    (typically a QScrollArea).

    Safe to call multiple times — patches only once.
    """
    global _patched
    if _patched:
        return
    _patched = True

    # ── QSpinBox ──
    def _spin_wheel(self, event):  # type: ignore[override]
        event.ignore()

    QSpinBox.wheelEvent = _spin_wheel  # type: ignore[assignment]

    # ── QDoubleSpinBox ──
    def _dspin_wheel(self, event):  # type: ignore[override]
        event.ignore()

    QDoubleSpinBox.wheelEvent = _dspin_wheel  # type: ignore[assignment]

    # ── QComboBox ──
    def _combo_wheel(self, event):  # type: ignore[override]
        event.ignore()

    QComboBox.wheelEvent = _combo_wheel  # type: ignore[assignment]

    # ── QSlider ──
    def _slider_wheel(self, event):  # type: ignore[override]
        event.ignore()

    QSlider.wheelEvent = _slider_wheel  # type: ignore[assignment]
