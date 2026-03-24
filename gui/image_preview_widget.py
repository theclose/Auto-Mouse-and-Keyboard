"""
ImagePreviewWidget — Live template match preview for Action Editor.

Shows a scaled-down screenshot with the template match highlighted.
Updates periodically via QTimer when a valid template path is set.
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
_PREVIEW_W = 320
_PREVIEW_H = 200


class ImagePreviewWidget(QGroupBox):
    """Live preview showing template match on current screen."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("👁 Preview", parent)
        self._template_path: str = ""
        self._confidence: float = 0.8
        self._last_result: str = ""

        self._setup_ui()

        self._scan_timer = QTimer(self)
        self._scan_timer.timeout.connect(self._do_scan)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 16, 4, 4)

        self._preview_label = QLabel()
        self._preview_label.setFixedSize(_PREVIEW_W, _PREVIEW_H)
        self._preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_label.setStyleSheet(
            "background: #1a1a2e; border: 1px solid #333; " "border-radius: 4px; color: #888;"
        )
        self._preview_label.setText("Chọn ảnh mẫu để xem preview")
        layout.addWidget(self._preview_label)

        self._match_label = QLabel("⏳ Chờ ảnh mẫu...")
        self._match_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._match_label.setWordWrap(True)
        layout.addWidget(self._match_label)

        self._scan_btn = QPushButton("🔄 Quét ngay")
        self._scan_btn.clicked.connect(self._do_scan)
        layout.addWidget(self._scan_btn)

    def set_template(self, path: str) -> None:
        """Update template path and start/stop scanning."""
        self._template_path = path.strip()
        if self._template_path and os.path.isfile(self._template_path):
            self._match_label.setText("🔍 Đang tìm...")
            if not self._scan_timer.isActive():
                self._scan_timer.start(2500)  # scan every 2.5s
            self._do_scan()  # immediate first scan
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
        """Capture screen, run template match, update preview."""
        if not self._template_path or not os.path.isfile(self._template_path):
            return

        try:
            import cv2

            from modules.screen import grab_screen

            # 1. Grab screen
            screen = grab_screen()
            if screen is None:
                self._match_label.setText("❌ Không chụp được màn hình")
                return

            # 2. Load template
            template = cv2.imread(self._template_path)
            if template is None:
                self._match_label.setText("❌ Không đọc được ảnh mẫu")
                return

            # 3. Match
            screen_gray = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY)
            template_gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
            result = cv2.matchTemplate(screen_gray, template_gray, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)

            t_h, t_w = template_gray.shape[:2]

            # 4. Draw on screen copy
            display = screen.copy()
            if max_val >= self._confidence:
                # Green box for match
                x, y = max_loc
                cv2.rectangle(display, (x, y), (x + t_w, y + t_h), (0, 255, 0), 3)
                self._match_label.setText(f"✅ Tìm thấy tại ({x}, {y}), conf={max_val:.3f}")
                self._match_label.setStyleSheet("color: #27ae60; font-weight: bold;")
            else:
                self._match_label.setText(f"❌ Không tìm thấy (max conf={max_val:.3f})")
                self._match_label.setStyleSheet("color: #e74c3c;")

            # 5. Scale down and display
            h, w = display.shape[:2]
            scale = min(_PREVIEW_W / w, _PREVIEW_H / h)
            new_w, new_h = int(w * scale), int(h * scale)
            small = cv2.resize(display, (new_w, new_h))
            # BGR → RGB for Qt
            rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
            qimg = QImage(rgb.data, new_w, new_h, new_w * 3, QImage.Format.Format_RGB888)
            pixmap = QPixmap.fromImage(qimg)
            self._preview_label.setPixmap(pixmap)

        except ImportError:
            self._match_label.setText("⚠ cv2 không khả dụng")
            self._scan_timer.stop()
        except Exception as e:
            logger.warning("Preview scan failed: %s", e)
            self._match_label.setText(f"⚠ Lỗi: {str(e)[:50]}")
