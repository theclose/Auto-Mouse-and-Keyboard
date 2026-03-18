"""
Crash Handler – Global exception handler with GUI dialog and restart.

Catches unhandled exceptions, shows a user-friendly dialog with:
- Error description and traceback
- Copy Error button
- Restart Application button
- Close button

Prevents silent crashes during 24/7 operation.
"""

import platform
import subprocess
import sys
import traceback
from datetime import datetime
from types import TracebackType
from typing import Any

from PyQt6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTextEdit, QStyle,
)
from PyQt6.QtGui import QFont

import logging

logger = logging.getLogger("CrashHandler")


class CrashDialog(QDialog):
    """Dialog shown on unhandled exceptions."""

    def __init__(self, exctype: type[BaseException], value: BaseException,
                 tb: TracebackType | None, parent: Any = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("AutoMacro – Error")
        self.setMinimumSize(550, 350)
        self.setModal(True)

        self._tb_text = "".join(traceback.format_exception(exctype, value, tb))
        self._restart_cmd = [sys.executable] + sys.argv

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # Header
        header = QHBoxLayout()
        icon_label = QLabel()
        style = self.style()
        assert style is not None
        icon = style.standardIcon(
            QStyle.StandardPixmap.SP_MessageBoxCritical)
        icon_label.setPixmap(icon.pixmap(40, 40))
        header.addWidget(icon_label)

        msg = QVBoxLayout()
        title = QLabel("Oops! AutoMacro encountered a problem.")
        title.setObjectName("crashTitle")
        desc = QLabel(
            f"Error: {exctype.__name__}: {value}\n"
            "You can restart the application or close it.")
        desc.setWordWrap(True)
        msg.addWidget(title)
        msg.addWidget(desc)
        header.addLayout(msg)
        header.addStretch()
        layout.addLayout(header)

        # Traceback
        self._text = QTextEdit()
        self._text.setReadOnly(True)
        self._text.setFont(QFont("Consolas", 9))
        self._text.setPlainText(self._tb_text)
        self._text.setObjectName("crashTraceback")
        layout.addWidget(self._text)

        # Buttons
        btns = QHBoxLayout()
        copy_btn = QPushButton("📄 Copy Error")
        copy_btn.clicked.connect(self._copy)
        btns.addWidget(copy_btn)
        btns.addStretch()

        restart_btn = QPushButton("🔄 Restart")
        restart_btn.setObjectName("successButton")
        restart_btn.clicked.connect(self._restart)
        btns.addWidget(restart_btn)

        close_btn = QPushButton("❌ Close")
        close_btn.clicked.connect(self.close)
        btns.addWidget(close_btn)
        layout.addLayout(btns)

    def _copy(self) -> None:
        report = (
            f"AutoMacro Crash Report\n"
            f"Date: {datetime.now()}\n"
            f"OS: {platform.system()} {platform.release()}\n"
            f"Python: {platform.python_version()}\n\n"
            f"Traceback:\n{self._tb_text}"
        )
        clipboard = QApplication.clipboard()
        assert clipboard is not None
        clipboard.setText(report)

    def _restart(self) -> None:
        logger.info("Restarting application...")
        subprocess.Popen(self._restart_cmd)
        QApplication.quit()


class CrashHandler:
    """Installs global exception hooks."""

    _installed = False
    _handling = False

    @classmethod
    def install(cls) -> None:
        if cls._installed:
            return
        sys.excepthook = cls._handle
        cls._installed = True
        logger.info("CrashHandler installed")

    @classmethod
    def _handle(cls, exctype: type[BaseException], value: BaseException,
                tb: TracebackType | None) -> None:
        if cls._handling:
            sys.__excepthook__(exctype, value, tb)
            return

        cls._handling = True
        try:
            try:
                logger.critical(
                    "Uncaught exception!", exc_info=(exctype, value, tb))
            except Exception:
                pass

            if issubclass(exctype, KeyboardInterrupt):
                sys.__excepthook__(exctype, value, tb)
                return

            app = QApplication.instance()
            if app:
                try:
                    dialog = CrashDialog(exctype, value, tb)
                    dialog.exec()
                except Exception:
                    sys.__excepthook__(exctype, value, tb)
            else:
                sys.__excepthook__(exctype, value, tb)
        finally:
            cls._handling = False
