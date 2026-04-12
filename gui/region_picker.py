"""
Region Picker – full-screen overlay for selecting a rectangular screen region.

Similar to Windows Snipping Tool:
- Click and drag to select a rectangular area
- Shows live rectangle preview with dimensions
- Magnifier lens at cursor for precision
- Click to confirm, Escape to cancel

Emits:
    region_selected(int, int, int, int) – x, y, width, height of selected region
    cancelled()                        – when user presses Escape
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


class RegionPickerOverlay(QWidget):
    """
    Full-screen overlay for drag-selecting a rectangular region.

    Usage:
        picker = RegionPickerOverlay()
        picker.region_selected.connect(lambda x, y, w, h: ...)
        picker.start()
    """

    region_selected = pyqtSignal(int, int, int, int)  # x, y, w, h
    cancelled = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._mouse_pos = QPoint(0, 0)
        self._screenshot: QPixmap = QPixmap()
        self._screenshot_image: Optional[QImage] = None

        # Drag state
        self._dragging = False
        self._drag_start: Optional[QPoint] = None
        self._drag_end: Optional[QPoint] = None

        self._update_timer = QTimer()
        self._update_timer.setInterval(16)  # ~60fps
        self._update_timer.timeout.connect(self._track_mouse)

        # Window setup
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCursor(Qt.CursorShape.CrossCursor)

    def start(self) -> None:
        """Capture the screen and show the picker overlay."""
        screen = QGuiApplication.primaryScreen()
        if screen:
            self._screenshot = screen.grabWindow(0)  # type: ignore[arg-type]
            self._screenshot_image = self._screenshot.toImage()

        pscreen = QApplication.primaryScreen()
        if pscreen:
            self.setGeometry(pscreen.geometry())
        self._mouse_pos = QCursor.pos()
        self.showFullScreen()
        self.setFocus()
        self._update_timer.start()

    def _track_mouse(self) -> None:
        new_pos = QCursor.pos()
        if new_pos != self._mouse_pos:
            self._mouse_pos = new_pos
            self.update()

    def _get_selection_rect(self) -> Optional[QRect]:
        """Return normalized rectangle from drag start/end."""
        if self._drag_start is None or self._drag_end is None:
            return None
        x1 = min(self._drag_start.x(), self._drag_end.x())
        y1 = min(self._drag_start.y(), self._drag_end.y())
        x2 = max(self._drag_start.x(), self._drag_end.x())
        y2 = max(self._drag_start.y(), self._drag_end.y())
        w = x2 - x1
        h = y2 - y1
        if w < 2 or h < 2:
            return None
        return QRect(x1, y1, w, h)

    def paintEvent(self, event: Optional[QPaintEvent]) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        screen_geo = self.geometry()
        mx = self._mouse_pos.x() - screen_geo.x()
        my = self._mouse_pos.y() - screen_geo.y()

        # 1) Draw frozen screenshot
        if not self._screenshot.isNull():
            painter.drawPixmap(0, 0, self._screenshot)

        # 2) Dark overlay over everything
        painter.fillRect(self.rect(), QColor(0, 0, 0, 100))

        # 3) If dragging, show selected region as clear (cut-out) with border
        sel_rect = self._get_selection_rect()
        if sel_rect is not None:
            # Draw the clear region (original screenshot visible)
            if not self._screenshot.isNull():
                local_rect = QRect(
                    sel_rect.x() - screen_geo.x(),
                    sel_rect.y() - screen_geo.y(),
                    sel_rect.width(),
                    sel_rect.height(),
                )
                painter.drawPixmap(local_rect, self._screenshot, local_rect)

            # Selection border
            border_pen = QPen(QColor(108, 99, 255), 2, Qt.PenStyle.SolidLine)
            painter.setPen(border_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            local_rect = QRect(
                sel_rect.x() - screen_geo.x(),
                sel_rect.y() - screen_geo.y(),
                sel_rect.width(),
                sel_rect.height(),
            )
            painter.drawRect(local_rect)

            # Dimension label
            dim_text = f"{sel_rect.width()} × {sel_rect.height()}"
            font = QFont("Segoe UI", 10)
            font.setBold(True)
            painter.setFont(font)
            fm = painter.fontMetrics()
            tw = fm.horizontalAdvance(dim_text) + 12
            th = fm.height() + 8

            label_x = local_rect.x() + (local_rect.width() - tw) // 2
            label_y = local_rect.bottom() + 4
            if label_y + th > self.height():
                label_y = local_rect.top() - th - 4

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(26, 27, 46, 220))
            painter.drawRoundedRect(label_x, label_y, tw, th, 4, 4)
            painter.setPen(QColor(232, 232, 240))
            painter.drawText(label_x + 6, label_y + fm.ascent() + 4, dim_text)

            # Corner handles
            handle_size = 6
            handle_color = QColor(108, 99, 255)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(handle_color)
            for cx, cy in [
                (local_rect.left(), local_rect.top()),
                (local_rect.right(), local_rect.top()),
                (local_rect.left(), local_rect.bottom()),
                (local_rect.right(), local_rect.bottom()),
            ]:
                painter.drawRect(cx - handle_size // 2, cy - handle_size // 2, handle_size, handle_size)

        else:
            # Not dragging yet: show crosshair
            crosshair_pen = QPen(QColor(108, 99, 255, 200), 1, Qt.PenStyle.DashLine)
            painter.setPen(crosshair_pen)
            painter.drawLine(mx, 0, mx, self.height())
            painter.drawLine(0, my, self.width(), my)

        # 4) Coordinate info
        abs_x = self._mouse_pos.x()
        abs_y = self._mouse_pos.y()
        info_text = f"  X: {abs_x}  Y: {abs_y}  "
        font = QFont("Segoe UI", 10)
        font.setBold(True)
        painter.setFont(font)
        fm = painter.fontMetrics()
        tw = fm.horizontalAdvance(info_text) + 16
        th = fm.height() + 12

        box_x = mx + 20
        box_y = my + 25
        if box_x + tw > self.width():
            box_x = mx - tw - 20
        if box_y + th > self.height():
            box_y = my - th - 25

        painter.setPen(QPen(QColor(108, 99, 255), 1))
        painter.setBrush(QColor(26, 27, 46, 230))
        painter.drawRoundedRect(box_x, box_y, tw, th, 6, 6)
        painter.setPen(QColor(232, 232, 240))
        painter.drawText(box_x + 8, box_y + fm.ascent() + 6, info_text.strip())

        # 5) Hint text
        hint_font = QFont("Segoe UI", 9)
        painter.setFont(hint_font)
        painter.setPen(QColor(160, 160, 184))
        hint = "Kéo chuột để chọn vùng  •  Escape để hủy"
        hint_w = painter.fontMetrics().horizontalAdvance(hint)
        painter.drawText((self.width() - hint_w) // 2, self.height() - 30, hint)

        painter.end()

    def mousePressEvent(self, event: Optional[QMouseEvent]) -> None:
        if event and event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._drag_start = QCursor.pos()
            self._drag_end = QCursor.pos()
        elif event and event.button() == Qt.MouseButton.RightButton:
            self._cancel()

    def mouseMoveEvent(self, event: Optional[QMouseEvent]) -> None:
        if self._dragging:
            self._drag_end = QCursor.pos()
            self.update()

    def mouseReleaseEvent(self, event: Optional[QMouseEvent]) -> None:
        if event and event.button() == Qt.MouseButton.LeftButton and self._dragging:
            self._dragging = False
            self._drag_end = QCursor.pos()
            sel = self._get_selection_rect()
            if sel is not None and sel.width() >= 5 and sel.height() >= 5:
                self._update_timer.stop()
                self.close()
                self.region_selected.emit(sel.x(), sel.y(), sel.width(), sel.height())
            else:
                # Too small — reset, let user try again
                self._drag_start = None
                self._drag_end = None
                self.update()

    def keyPressEvent(self, event: Optional[QKeyEvent]) -> None:
        if event and event.key() == Qt.Key.Key_Escape:
            self._cancel()

    def _cancel(self) -> None:
        self._update_timer.stop()
        self.close()
        self.cancelled.emit()

    def closeEvent(self, event: Optional[QCloseEvent]) -> None:
        self._update_timer.stop()
        if event:
            super().closeEvent(event)
