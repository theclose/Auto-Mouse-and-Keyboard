"""
Run Summary Dialog — shows human-friendly playback results after engine stop.

Inspired by Macronyx PlaybackResultsPanel, built for AutoMacro's PyQt6 stack.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from core.engine import PlaybackReport


class RunSummaryDialog(QDialog):
    """Post-playback summary with success/fail/skipped counts."""

    def __init__(self, report: PlaybackReport, parent=None):
        super().__init__(parent)
        self.report = report
        self._result_action = ""  # "rerun" | "goto_error" | ""
        self.setWindowTitle("Kết quả chạy macro")
        self.setMinimumWidth(420)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # -- Status icon + headline --
        r = self.report
        if r.failed == 0:
            icon = "✅"
            headline = "Macro chạy thành công!"
            color = "#4caf50"
        elif r.success > 0:
            icon = "⚠️"
            headline = "Macro hoàn thành với lỗi"
            color = "#ff9800"
        else:
            icon = "❌"
            headline = "Macro thất bại"
            color = "#f44336"

        headline_label = QLabel(f'<h2 style="color:{color}">{icon} {headline}</h2>')
        headline_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(headline_label)

        # -- Stats grid --
        duration_sec = r.duration_ms / 1000
        stats_html = f"""
        <table style="font-size:14px; margin:8px auto;" cellpadding="6">
        <tr><td>📊 Tổng bước:</td><td><b>{r.total}</b></td></tr>
        <tr><td style="color:#4caf50">✅ Thành công:</td><td><b>{r.success}</b></td></tr>
        <tr><td style="color:#f44336">❌ Thất bại:</td><td><b>{r.failed}</b></td></tr>
        <tr><td style="color:#9e9e9e">⏭ Bỏ qua:</td><td><b>{r.skipped}</b></td></tr>
        <tr><td>⏱ Thời gian:</td><td><b>{duration_sec:.1f}s</b></td></tr>
        </table>
        """
        stats_label = QLabel(stats_html)
        stats_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(stats_label)

        # -- First error info --
        if r.first_error:
            error_html = (
                f'<div style="background:#2a1a1a; border:1px solid #f44336; '
                f'border-radius:6px; padding:8px; margin:4px;">'
                f'<b style="color:#f44336">Lỗi đầu tiên (bước {r.first_error_idx + 1}):</b><br>'
                f'<span style="color:#ffcdd2">{r.first_error}</span></div>'
            )
            error_label = QLabel(error_html)
            error_label.setWordWrap(True)
            layout.addWidget(error_label)

        # -- Buttons --
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        close_btn = QPushButton("Đóng")
        close_btn.setDefault(True)
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)

        rerun_btn = QPushButton("🔄 Chạy lại")
        rerun_btn.clicked.connect(self._on_rerun)
        btn_layout.addWidget(rerun_btn)

        if r.first_error_idx >= 0:
            goto_btn = QPushButton("🔍 Mở bước lỗi")
            goto_btn.clicked.connect(self._on_goto_error)
            btn_layout.addWidget(goto_btn)

        layout.addLayout(btn_layout)

    def _on_rerun(self) -> None:
        self._result_action = "rerun"
        self.accept()

    def _on_goto_error(self) -> None:
        self._result_action = "goto_error"
        self.accept()

    @property
    def result_action(self) -> str:
        """After exec(), returns 'rerun', 'goto_error', or '' (closed)."""
        return self._result_action
