"""
Log panel widget — extracted from main_window.py.
Displays application log with level filter.
"""

import logging

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Thread-safe logging handler for GUI
# ---------------------------------------------------------------------------
class _LogSignalBridge(QObject):
    """Bridge: logging.Handler cannot have pyqtSignal, QObject can."""

    log_record = pyqtSignal(str)


class QLogHandler(logging.Handler):
    """Emits formatted log records as Qt signals (thread-safe)."""

    def __init__(self) -> None:
        super().__init__()
        self._bridge = _LogSignalBridge()
        self.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                datefmt="%H:%M:%S",
            )
        )

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            self._bridge.log_record.emit(msg)
        except Exception:
            self.handleError(record)


class LogPanel(QWidget):
    """Collapsible log panel with level filter."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._setup_ui()
        self._attach_handler()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(2)

        # Header with filter + clear button
        header_row = QHBoxLayout()
        header_label = QLabel("📝 Nhật ký")
        header_label.setObjectName("subtitleLabel")
        header_row.addWidget(header_label)
        header_row.addStretch()

        self._log_filter = QComboBox()
        self._log_filter.addItems(["Tất cả", "INFO", "WARNING", "ERROR"])
        self._log_filter.setFixedWidth(90)
        self._log_filter.setFixedHeight(22)
        self._log_filter.setToolTip("Lọc mức nhật ký")
        self._log_filter.currentTextChanged.connect(self._on_filter_changed)
        header_row.addWidget(self._log_filter)

        clear_btn = QPushButton("🗑 Xóa")
        clear_btn.setFixedHeight(22)
        clear_btn.setFixedWidth(70)
        clear_btn.clicked.connect(self.clear)
        header_row.addWidget(clear_btn)
        layout.addLayout(header_row)

        # Log text area
        self._app_log = QPlainTextEdit()
        self._app_log.setObjectName("appLog")
        self._app_log.setReadOnly(True)
        self._app_log.setMaximumBlockCount(1000)
        layout.addWidget(self._app_log)

    def _attach_handler(self) -> None:
        """Attach logging handler to root logger."""
        self._log_handler = QLogHandler()
        self._log_handler._bridge.log_record.connect(self._append_log)
        logging.getLogger().addHandler(self._log_handler)
        logger.info("Log panel attached — showing live logs")

    def _append_log(self, text: str) -> None:
        """Slot: append a log line (called via signal, thread-safe)."""
        level_filter = self._log_filter.currentText()
        if level_filter != "Tất cả":
            if f"[{level_filter}]" not in text:
                return
        self._app_log.appendPlainText(text)

    def _on_filter_changed(self, level: str) -> None:
        logger.info("Log filter set to: %s", level)

    def clear(self) -> None:
        """Clear log contents."""
        self._app_log.clear()

    def cleanup(self) -> None:
        """Remove handler on destroy."""
        logging.getLogger().removeHandler(self._log_handler)
