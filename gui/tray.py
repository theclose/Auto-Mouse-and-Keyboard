"""
System tray integration.
Provides a tray icon with quick controls and minimize-to-tray behavior.
"""

from PyQt6.QtWidgets import QSystemTrayIcon, QMenu
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont
from PyQt6.QtCore import pyqtSignal, QObject
from typing import Optional


def _create_default_icon() -> QIcon:
    """Create a simple colored 'A' icon when no icon file is available."""
    pixmap = QPixmap(64, 64)
    pixmap.fill(QColor(108, 99, 255))
    painter = QPainter(pixmap)
    painter.setPen(QColor(255, 255, 255))
    font = QFont("Segoe UI")
    font.setPixelSize(40)
    font.setWeight(QFont.Weight.Bold)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), 0x0084, "A")  # AlignCenter
    painter.end()
    return QIcon(pixmap)


class TrayManager(QObject):
    """
    Manages the system tray icon and its context menu.
    """

    show_requested = pyqtSignal()
    play_requested = pyqtSignal()
    stop_requested = pyqtSignal()
    pause_requested = pyqtSignal()
    quit_requested = pyqtSignal()

    def __init__(self, parent: QObject | None = None, icon: Optional[QIcon] = None) -> None:
        super().__init__(parent)
        self._icon = icon or _create_default_icon()
        self._tray = QSystemTrayIcon(self._icon, parent)

        # Context menu
        menu = QMenu()
        show_action = menu.addAction("Show Window")
        assert show_action is not None
        self._show_action = show_action
        self._show_action.triggered.connect(self.show_requested.emit)

        menu.addSeparator()

        play_action = menu.addAction("▶ Play")
        assert play_action is not None
        self._play_action = play_action
        self._play_action.triggered.connect(self.play_requested.emit)

        pause_action = menu.addAction("⏸ Pause")
        assert pause_action is not None
        self._pause_action = pause_action
        self._pause_action.triggered.connect(self.pause_requested.emit)

        stop_action = menu.addAction("⏹ Stop")
        assert stop_action is not None
        self._stop_action = stop_action
        self._stop_action.triggered.connect(self.stop_requested.emit)

        menu.addSeparator()

        quit_act = menu.addAction("Quit")
        assert quit_act is not None
        quit_act.triggered.connect(self.quit_requested.emit)

        self._tray.setContextMenu(menu)

        # Double-click to show window
        self._tray.activated.connect(self._on_activated)

    def show(self) -> None:
        self._tray.show()

    def hide(self) -> None:
        self._tray.hide()

    def set_tooltip(self, text: str) -> None:
        self._tray.setToolTip(text)

    def show_message(self, title: str, message: str, duration_ms: int = 3000) -> None:
        self._tray.showMessage(
            title, message,
            QSystemTrayIcon.MessageIcon.Information, duration_ms,
        )

    def update_state(self, is_running: bool, is_paused: bool) -> None:
        """Update menu items based on engine state."""
        self._play_action.setEnabled(not is_running or is_paused)
        self._pause_action.setEnabled(is_running and not is_paused)
        self._stop_action.setEnabled(is_running)

        if is_running and not is_paused:
            self.set_tooltip("AutoMacro – Running")
        elif is_paused:
            self.set_tooltip("AutoMacro – Paused")
        else:
            self.set_tooltip("AutoMacro – Idle")

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show_requested.emit()
