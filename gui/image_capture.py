"""
Image capture tool – a semi-transparent overlay for snipping screen regions.
The user draws a rectangle and the captured region is saved as a template image.
"""

import os
import time
from typing import Optional

from PyQt6.QtCore import QPoint, QRect, Qt, pyqtSignal
from PyQt6.QtGui import (
    QColor,
    QGuiApplication,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPen,
    QPixmap,
)
from PyQt6.QtWidgets import QApplication, QWidget


class ImageCaptureOverlay(QWidget):
    """
    Full-screen semi-transparent overlay.
    User draws a rectangle → captured region is saved to disk.
    Emits `image_captured(str)` with the file path.
    """

    image_captured = pyqtSignal(str)
    cancelled = pyqtSignal()

    def __init__(self, save_dir: str = ".", parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._save_dir = save_dir
        self._origin = QPoint()
        self._current = QPoint()
        self._drawing = False
        self._screenshot: QPixmap = QPixmap()

        # Full-screen window flags
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setCursor(Qt.CursorShape.CrossCursor)

    def start(self) -> None:
        """Take a screenshot and show the overlay."""
        # Capture entire screen
        screen = QGuiApplication.primaryScreen()
        if screen:
            self._screenshot = screen.grabWindow(0)  # type: ignore[arg-type]

        pscreen = QApplication.primaryScreen()
        if pscreen:
            self.setGeometry(pscreen.geometry())
        self.showFullScreen()

    def paintEvent(self, event: Optional[QPaintEvent]) -> None:
        painter = QPainter(self)

        # Draw the frozen screenshot
        if not self._screenshot.isNull():
            painter.drawPixmap(0, 0, self._screenshot)

        # Semi-transparent overlay
        painter.fillRect(self.rect(), QColor(0, 0, 0, 100))

        # Draw selection rectangle
        if self._drawing:
            rect = QRect(self._origin, self._current).normalized()

            # Clear the overlay inside the selection (show original)
            # Zero-copy: draw directly from source rect, no QPixmap.copy()
            if not self._screenshot.isNull():
                painter.drawPixmap(rect, self._screenshot, rect)

            # Draw border
            pen = QPen(QColor(108, 99, 255), 2, Qt.PenStyle.SolidLine)
            painter.setPen(pen)
            painter.drawRect(rect)

            # Size label
            painter.setPen(QColor(255, 255, 255))
            label = f"{rect.width()} × {rect.height()}"
            painter.drawText(rect.x(), rect.y() - 5, label)

        painter.end()

    def mousePressEvent(self, event: Optional[QMouseEvent]) -> None:
        if event and event.button() == Qt.MouseButton.LeftButton:
            self._origin = event.pos()
            self._current = event.pos()
            self._drawing = True
            self.update()

    def mouseMoveEvent(self, event: Optional[QMouseEvent]) -> None:
        if self._drawing and event:
            self._current = event.pos()
            self.update()

    def mouseReleaseEvent(self, event: Optional[QMouseEvent]) -> None:
        if event and event.button() == Qt.MouseButton.LeftButton and self._drawing:
            self._drawing = False
            rect = QRect(self._origin, self._current).normalized()

            if rect.width() > 5 and rect.height() > 5:
                self._save_region(rect)

            self._cleanup_and_close()

    def keyPressEvent(self, event: Optional[QKeyEvent]) -> None:
        if event and event.key() == Qt.Key.Key_Escape:
            self._drawing = False
            self.cancelled.emit()
            self._cleanup_and_close()

    def _cleanup_and_close(self) -> None:
        """Release screenshot memory and schedule widget destruction."""
        self._screenshot = QPixmap()  # Release ~8MB immediately
        self.close()
        self.deleteLater()  # Schedule Qt cleanup

    def _save_region(self, rect: QRect) -> None:
        """Crop the screenshot and save to file."""
        if self._screenshot.isNull():
            return

        cropped = self._screenshot.copy(rect)
        os.makedirs(self._save_dir, exist_ok=True)

        # Generate unique filename using ms-precision timestamp (avoids collision)
        ts = f"{time.strftime('%Y%m%d_%H%M%S')}_{int(time.time() * 1000) % 1000:03d}"
        filename = f"template_{ts}.png"
        filepath = os.path.join(self._save_dir, filename)

        # Handle rare case of same-second captures
        counter = 1
        while os.path.exists(filepath):
            filename = f"template_{ts}_{counter}.png"
            filepath = os.path.join(self._save_dir, filename)
            counter += 1

        cropped.save(filepath, "PNG")
        self.image_captured.emit(filepath)
