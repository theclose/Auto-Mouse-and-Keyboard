"""
Coordinate Picker – full-screen overlay for picking screen coordinates.

Features:
- Crosshair cursor following the mouse
- Live X, Y coordinate display next to cursor
- Magnifier lens showing zoomed view around cursor
- Color of pixel under cursor
- Click to confirm, Escape to cancel
- Works on multi-monitor setups
"""

from typing import Optional

from PyQt6.QtCore import QPoint, QRect, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QCloseEvent,
    QColor,
    QCursor,
    QFont,
    QGuiApplication,
    QImage,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPen,
    QPixmap,
)
from PyQt6.QtWidgets import QApplication, QWidget


class CoordinatePickerOverlay(QWidget):
    """
    Full-screen transparent overlay for picking coordinates.

    Usage:
        picker = CoordinatePickerOverlay()
        picker.coordinate_picked.connect(lambda x, y: print(f"Picked: {x}, {y}"))
        picker.start()

    Emits:
        coordinate_picked(int, int) – the screen X, Y when user clicks
        cancelled()                – when user presses Escape
    """

    coordinate_picked = pyqtSignal(int, int)
    cancelled = pyqtSignal()

    # Magnifier settings
    MAG_SIZE = 120  # magnifier diameter
    MAG_ZOOM = 4  # zoom factor
    MAG_OFFSET = 30  # distance from cursor
    CAPTURE_RADIUS = 15  # pixels around cursor to capture (MAG_SIZE / MAG_ZOOM / 2)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._mouse_pos = QPoint(0, 0)
        self._screenshot: QPixmap = QPixmap()
        self._screenshot_image: Optional[QImage] = None  # Cached QImage
        self._update_timer = QTimer()
        self._update_timer.setInterval(16)  # ~60fps
        self._update_timer.timeout.connect(self._track_mouse)

        # Window setup: frameless, always on top, transparent
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCursor(Qt.CursorShape.BlankCursor)

    def start(self) -> None:
        """Capture the screen and show the picker overlay."""
        screen = QGuiApplication.primaryScreen()
        if screen:
            self._screenshot = screen.grabWindow(0)  # type: ignore[arg-type]
            self._screenshot_image = self._screenshot.toImage()  # Cache once

        pscreen = QApplication.primaryScreen()
        if pscreen:
            self.setGeometry(pscreen.geometry())
        self._mouse_pos = QCursor.pos()
        self.showFullScreen()
        self.setFocus()
        self._update_timer.start()

    def _track_mouse(self) -> None:
        """Update mouse position and repaint."""
        new_pos = QCursor.pos()
        if new_pos != self._mouse_pos:
            self._mouse_pos = new_pos
            self.update()

    def paintEvent(self, event: Optional[QPaintEvent]) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        screen_geo = self.geometry()
        mx = self._mouse_pos.x() - screen_geo.x()
        my = self._mouse_pos.y() - screen_geo.y()

        # 1) Draw the frozen screenshot as background
        if not self._screenshot.isNull():
            painter.drawPixmap(0, 0, self._screenshot)

        # 2) Semi-transparent dark overlay
        painter.fillRect(self.rect(), QColor(0, 0, 0, 60))

        # 3) Crosshair lines (full screen width/height)
        crosshair_pen = QPen(QColor(108, 99, 255, 200), 1, Qt.PenStyle.DashLine)
        painter.setPen(crosshair_pen)
        painter.drawLine(mx, 0, mx, self.height())  # vertical
        painter.drawLine(0, my, self.width(), my)  # horizontal

        # 4) Center target circle
        target_pen = QPen(QColor(108, 99, 255), 2, Qt.PenStyle.SolidLine)
        painter.setPen(target_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QPoint(mx, my), 12, 12)
        painter.drawEllipse(QPoint(mx, my), 3, 3)

        # 5) Magnifier lens
        self._draw_magnifier(painter, mx, my)

        # 6) Coordinate info box
        self._draw_info_box(painter, mx, my)

        painter.end()

    def _draw_magnifier(self, painter: QPainter, mx: int, my: int) -> None:
        """Draw a circular magnified view of the area around the cursor."""
        if self._screenshot.isNull():
            return

        r = self.CAPTURE_RADIUS
        mag = self.MAG_SIZE

        # Determine magnifier position (avoid going off-screen)
        mag_x = mx + self.MAG_OFFSET
        mag_y = my - mag - self.MAG_OFFSET

        if mag_x + mag > self.width():
            mag_x = mx - mag - self.MAG_OFFSET
        if mag_y < 0:
            mag_y = my + self.MAG_OFFSET

        # Capture region around cursor from frozen screenshot
        screen_geo = self.geometry()
        capture_rect = QRect(
            self._mouse_pos.x() - screen_geo.x() - r, self._mouse_pos.y() - screen_geo.y() - r, r * 2, r * 2
        )
        captured = self._screenshot.copy(capture_rect)

        # Scale up
        zoomed = captured.scaled(
            mag,
            mag,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.FastTransformation,
        )

        # Draw magnifier background (dark circle)
        painter.setPen(QPen(QColor(108, 99, 255), 2))
        painter.setBrush(QColor(30, 30, 50, 230))
        painter.drawEllipse(mag_x, mag_y, mag, mag)

        # Clip to circle and draw zoomed image
        painter.save()
        from PyQt6.QtGui import QPainterPath

        clip_path = QPainterPath()
        clip_path.addEllipse(float(mag_x), float(mag_y), float(mag), float(mag))
        painter.setClipPath(clip_path)
        painter.drawPixmap(mag_x, mag_y, zoomed)

        # Draw crosshair inside magnifier
        center_x = mag_x + mag // 2
        center_y = mag_y + mag // 2
        cross_pen = QPen(QColor(255, 80, 80, 180), 1)
        painter.setPen(cross_pen)
        painter.drawLine(center_x - 8, center_y, center_x + 8, center_y)
        painter.drawLine(center_x, center_y - 8, center_x, center_y + 8)
        painter.restore()

    def _draw_info_box(self, painter: QPainter, mx: int, my: int) -> None:
        """Draw coordinate info box near cursor."""
        screen_geo = self.geometry()
        abs_x = self._mouse_pos.x()
        abs_y = self._mouse_pos.y()
        text = f"  X: {abs_x}  Y: {abs_y}  "

        # Get pixel color from cached QImage (avoids per-frame conversion)
        color_hex = ""
        if self._screenshot_image is not None:
            sx = abs_x - screen_geo.x()
            sy = abs_y - screen_geo.y()
            if 0 <= sx < self._screenshot_image.width() and 0 <= sy < self._screenshot_image.height():
                pixel = self._screenshot_image.pixelColor(sx, sy)
                color_hex = pixel.name()

        if color_hex:
            text += f" {color_hex}  "

        # Calculate box position
        font = QFont("Segoe UI", 11)
        font.setBold(True)
        painter.setFont(font)
        fm = painter.fontMetrics()
        tw = fm.horizontalAdvance(text)
        th = fm.height()

        box_w = tw + 16
        box_h = th + 16
        box_x = mx + 20
        box_y = my + 25

        # Keep box on screen
        if box_x + box_w > self.width():
            box_x = mx - box_w - 20
        if box_y + box_h > self.height():
            box_y = my - box_h - 25

        # Draw box background
        painter.setPen(QPen(QColor(108, 99, 255), 1))
        painter.setBrush(QColor(26, 27, 46, 230))
        painter.drawRoundedRect(box_x, box_y, box_w, box_h, 6, 6)

        # Draw color swatch
        if color_hex:
            swatch_size = 12
            swatch_x = box_x + box_w - swatch_size - 10
            swatch_y = box_y + (box_h - swatch_size) // 2
            painter.setBrush(QColor(color_hex))
            painter.setPen(QPen(QColor(255, 255, 255, 100), 1))
            painter.drawRoundedRect(swatch_x, swatch_y, swatch_size, swatch_size, 2, 2)

        # Draw text
        painter.setPen(QColor(232, 232, 240))
        painter.drawText(box_x + 8, box_y + th + 4, text.strip())

        # Hint text at bottom
        hint_font = QFont("Segoe UI", 9)
        painter.setFont(hint_font)
        painter.setPen(QColor(160, 160, 184))
        hint = "Click to pick  •  Escape to cancel"
        hint_w = painter.fontMetrics().horizontalAdvance(hint)
        painter.drawText((self.width() - hint_w) // 2, self.height() - 30, hint)

    def mousePressEvent(self, event: Optional[QMouseEvent]) -> None:
        if event and event.button() == Qt.MouseButton.LeftButton:
            self._update_timer.stop()
            abs_x = self._mouse_pos.x()
            abs_y = self._mouse_pos.y()
            self.close()
            self.coordinate_picked.emit(abs_x, abs_y)
        elif event and event.button() == Qt.MouseButton.RightButton:
            # Treat right-click as cancel to prevent stuck overlay
            self._update_timer.stop()
            self.close()
            self.cancelled.emit()

    def keyPressEvent(self, event: Optional[QKeyEvent]) -> None:
        if event and event.key() == Qt.Key.Key_Escape:
            self._update_timer.stop()
            self.close()
            self.cancelled.emit()

    def closeEvent(self, event: Optional[QCloseEvent]) -> None:
        self._update_timer.stop()
        if event:
            super().closeEvent(event)
