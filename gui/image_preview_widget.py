"""
ImagePreviewWidget — Live template match preview for Action Editor.

Shows a scaled-down screenshot with the template match highlighted.
Collapsed by default — user clicks the "Preview" header to expand.
Timer only runs while the widget is expanded.
"""

import logging
import os

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import (
    QGroupBox,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)

# Preview dimensions
_PREVIEW_W = 240
_PREVIEW_H = 130


class ImagePreviewWidget(QGroupBox):
    """Live preview showing template match on current screen.

    Collapsed by default. Click the checkbox header to expand/collapse.
    Scan timer only runs while expanded.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("👁 Preview", parent)
        self._template_path: str = ""
        self._confidence: float = 0.8
        self._last_result: str = ""

        # Make the group box checkable (acts as toggle)
        self.setCheckable(True)
        self.setChecked(False)  # Collapsed by default

        self._setup_ui()

        self._scan_timer = QTimer(self)
        self._scan_timer.timeout.connect(self._do_scan)

        # Toggle content visibility when checked/unchecked
        self.toggled.connect(self._on_toggled)
        # Start with content hidden
        self._content_widget.setVisible(False)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 16, 4, 4)

        # Wrap all content in a single widget for easy show/hide
        self._content_widget = QWidget()
        content_layout = QVBoxLayout(self._content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)

        self._preview_label = QLabel()
        self._preview_label.setFixedSize(_PREVIEW_W, _PREVIEW_H)
        self._preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_label.setStyleSheet(
            "background: #1a1a2e; border: 1px solid #333; " "border-radius: 4px; color: #888;"
        )
        self._preview_label.setText("Chọn ảnh mẫu để xem preview")
        content_layout.addWidget(self._preview_label)

        self._match_label = QLabel("⏳ Chờ ảnh mẫu...")
        self._match_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._match_label.setWordWrap(True)
        content_layout.addWidget(self._match_label)

        self._scan_btn = QPushButton("🔄 Quét ngay")
        self._scan_btn.clicked.connect(self._do_scan)
        content_layout.addWidget(self._scan_btn)

        layout.addWidget(self._content_widget)

    def _on_toggled(self, checked: bool) -> None:
        """Show/hide content and start/stop timer based on toggle state."""
        self._content_widget.setVisible(checked)
        if checked:
            # Start scanning if we have a valid template
            if self._template_path and os.path.isfile(self._template_path):
                if not self._scan_timer.isActive():
                    self._scan_timer.start(2500)
                self._do_scan()
        else:
            # Stop scanning when collapsed
            self._scan_timer.stop()

    def set_template(self, path: str) -> None:
        """Update template path. Only starts scanning if preview is expanded."""
        self._template_path = path.strip()
        if not self.isChecked():
            return  # Don't scan if collapsed

        if self._template_path and os.path.isfile(self._template_path):
            self._match_label.setText("🔍 Đang tìm...")
            if not self._scan_timer.isActive():
                self._scan_timer.start(2500)
            self._do_scan()
        else:
            self._scan_timer.stop()
            self._preview_label.setText(
                "Chọn ảnh mẫu để xem preview" if not self._template_path else "❌ File không tồn tại"
            )
            self._match_label.setText("⏳ Chờ ảnh mẫu hợp lệ...")

    def set_confidence(self, value: float) -> None:
        """Update confidence threshold."""
        self._confidence = value

    def stop(self) -> None:
        """Stop the scan timer (call when dialog closes)."""
        self._scan_timer.stop()

    def _do_scan(self) -> None:
        """Capture screen, run template match, update preview.

        Optimized: uses grayscale capture directly and avoids unnecessary copies.
        Memory: ~5MB per scan (down from ~33MB).
        """
        if not self._template_path or not os.path.isfile(self._template_path):
            return

        try:
            import cv2

            from modules.screen import capture_full_screen_gray

            # 1. Grab screen directly as grayscale (~2MB instead of ~8MB BGR)
            screen_gray = capture_full_screen_gray()
            if screen_gray is None:
                self._match_label.setText("❌ Không chụp được màn hình")
                return

            # 2. Load template directly as grayscale (skip color conversion)
            template_gray = cv2.imread(self._template_path, cv2.IMREAD_GRAYSCALE)
            if template_gray is None:
                self._match_label.setText("❌ Không đọc được ảnh mẫu")
                return

            # 3. Match on grayscale (smallest possible arrays)
            result = cv2.matchTemplate(screen_gray, template_gray, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)

            t_h, t_w = template_gray.shape[:2]

            # 4. Scale down for display BEFORE drawing (process tiny image ~240x130)
            h, w = screen_gray.shape[:2]
            scale = min(_PREVIEW_W / w, _PREVIEW_H / h)
            new_w, new_h = int(w * scale), int(h * scale)
            small = cv2.resize(screen_gray, (new_w, new_h))

            # Convert grayscale to RGB for Qt display
            small_rgb = cv2.cvtColor(small, cv2.COLOR_GRAY2RGB)

            # 5. Draw match box on the small image
            if max_val >= self._confidence:
                x, y = max_loc
                sx, sy = int(x * scale), int(y * scale)
                sw, sh = int(t_w * scale), int(t_h * scale)
                cv2.rectangle(small_rgb, (sx, sy), (sx + sw, sy + sh), (0, 255, 0), 2)
                self._match_label.setText(f"✅ Tìm thấy tại ({x}, {y}), conf={max_val:.3f}")
                self._match_label.setStyleSheet("color: #27ae60; font-weight: bold;")
            else:
                self._match_label.setText(f"❌ Không tìm thấy (max conf={max_val:.3f})")
                self._match_label.setStyleSheet("color: #e74c3c;")

            # 6. Display
            qimg = QImage(small_rgb.data, new_w, new_h, new_w * 3, QImage.Format.Format_RGB888)
            pixmap = QPixmap.fromImage(qimg)
            self._preview_label.setPixmap(pixmap)

        except ImportError:
            self._match_label.setText("⚠ cv2 không khả dụng")
            self._scan_timer.stop()
        except Exception as e:
            logger.warning("Preview scan failed: %s", e)
            self._match_label.setText(f"⚠ Lỗi: {str(e)[:50]}")
