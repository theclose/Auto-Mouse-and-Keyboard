"""
Help dialog for AutoPilot.

Provides:
  - Tab 1: Quick Start Guide
  - Tab 2: Action Reference (auto-generated)
  - Tab 3: Keyboard Shortcuts
  - Tab 4: Troubleshooting FAQ
"""

from PyQt6.QtWidgets import (
    QDialog, QTabWidget, QVBoxLayout, QTextBrowser, QPushButton,
    QHBoxLayout,
)
from PyQt6.QtCore import Qt

from gui.action_editor import ACTION_CATEGORIES


class HelpDialog(QDialog):
    """In-app help with 4 tabs."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("📖 Hướng dẫn sử dụng")
        self.setMinimumSize(700, 520)

        layout = QVBoxLayout(self)
        tabs = QTabWidget()

        tabs.addTab(self._quick_start_tab(), "🚀 Bắt đầu nhanh")
        tabs.addTab(self._action_ref_tab(), "📋 Action Reference")
        tabs.addTab(self._shortcuts_tab(), "⌨ Phím tắt")
        tabs.addTab(self._faq_tab(), "❓ FAQ")

        layout.addWidget(tabs)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton("Đóng")
        close_btn.setObjectName("primaryButton")
        close_btn.clicked.connect(self.close)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    # ── Tab content builders ────────────────────────────────

    def _quick_start_tab(self) -> QTextBrowser:
        tb = QTextBrowser()
        tb.setOpenExternalLinks(True)
        tb.setHtml("""
        <h2>🚀 Bắt Đầu Nhanh — 5 Bước</h2>
        <ol>
            <li><b>Tạo macro:</b> Click <code>📄 Mới</code> hoặc nhấn <code>Ctrl+N</code></li>
            <li><b>Thêm action:</b> Click <code>➕ Thêm</code> → chọn loại action → thiết lập tham số → OK</li>
            <li><b>Chỉnh sửa:</b> Double-click vào action để sửa. Kéo thả để sắp xếp lại thứ tự.</li>
            <li><b>Chạy macro:</b> Nhấn <code>▶ PLAY</code> hoặc phím <code>F6</code></li>
            <li><b>Lưu macro:</b> Click <code>💾 Lưu</code> hoặc <code>Ctrl+S</code></li>
        </ol>

        <h3>💡 Mẹo</h3>
        <ul>
            <li>Dùng <code>📸 Chụp</code> để chụp vùng màn hình làm ảnh mẫu cho Image actions</li>
            <li>Dùng <code>🎯 Tọa độ</code> (Ctrl+G) để lấy tọa độ nhanh từ màn hình</li>
            <li>Bật <code>🐛 Chạy từng bước</code> để debug macro</li>
            <li>Đặt Số lần lặp = 0 để chạy vô hạn (dừng bằng F8)</li>
        </ul>

        <h3>🎯 Ghi macro tự động</h3>
        <p>Sử dụng panel <b>Ghi</b> ở bên phải để ghi lại thao tác chuột/bàn phím tự động.</p>
        """)
        return tb

    def _action_ref_tab(self) -> QTextBrowser:
        tb = QTextBrowser()
        lines = ["<h2>📋 Danh Sách Action</h2>"]
        for cat_name, actions in ACTION_CATEGORIES:
            lines.append(f"<h3>{cat_name}</h3><table border='0' cellpadding='4'>")
            for atype, label in actions:
                lines.append(
                    f"<tr><td><code>{atype}</code></td>"
                    f"<td><b>{label}</b></td></tr>"
                )
            lines.append("</table>")
        lines.append(f"<p><i>Tổng: {sum(len(a) for _, a in ACTION_CATEGORIES)} action types</i></p>")
        tb.setHtml("\n".join(lines))
        return tb

    def _shortcuts_tab(self) -> QTextBrowser:
        tb = QTextBrowser()
        tb.setHtml("""
        <h2>⌨ Phím Tắt</h2>

        <h3>Điều khiển</h3>
        <table border='0' cellpadding='4'>
            <tr><td><code>F6</code></td><td>Chạy / Dừng macro</td></tr>
            <tr><td><code>F7</code></td><td>Tạm dừng</td></tr>
            <tr><td><code>F8</code></td><td>Dừng khẩn cấp</td></tr>
        </table>

        <h3>Tệp</h3>
        <table border='0' cellpadding='4'>
            <tr><td><code>Ctrl+N</code></td><td>Tạo macro mới</td></tr>
            <tr><td><code>Ctrl+O</code></td><td>Mở macro</td></tr>
            <tr><td><code>Ctrl+S</code></td><td>Lưu macro</td></tr>
        </table>

        <h3>Chỉnh sửa</h3>
        <table border='0' cellpadding='4'>
            <tr><td><code>Ctrl+Z</code></td><td>Hoàn tác</td></tr>
            <tr><td><code>Ctrl+Y</code></td><td>Làm lại</td></tr>
            <tr><td><code>Ctrl+C</code></td><td>Sao chép action</td></tr>
            <tr><td><code>Ctrl+V</code></td><td>Dán action</td></tr>
            <tr><td><code>Ctrl+D</code></td><td>Nhân bản action</td></tr>
            <tr><td><code>Ctrl+↑</code></td><td>Di chuyển lên</td></tr>
            <tr><td><code>Ctrl+↓</code></td><td>Di chuyển xuống</td></tr>
            <tr><td><code>Delete</code></td><td>Xóa action</td></tr>
        </table>

        <h3>Công cụ</h3>
        <table border='0' cellpadding='4'>
            <tr><td><code>Ctrl+G</code></td><td>Chọn tọa độ XY</td></tr>
            <tr><td><code>F1</code></td><td>Mở hướng dẫn</td></tr>
        </table>
        """)
        return tb

    def _faq_tab(self) -> QTextBrowser:
        tb = QTextBrowser()
        tb.setHtml("""
        <h2>❓ Câu Hỏi Thường Gặp</h2>

        <h3>1. Macro không tìm thấy ảnh (Image Not Found)?</h3>
        <p>• Giảm <b>Confidence</b> (0.6-0.7) nếu ảnh bị mờ hoặc scale khác<br>
           • Chụp lại ảnh mẫu ở độ phân giải hiện tại<br>
           • Tăng <b>Timeout</b> nếu ảnh xuất hiện chậm</p>

        <h3>2. Click chuột bị lệch tọa độ?</h3>
        <p>• Dùng <code>🎯 Tọa độ</code> (Ctrl+G) để lấy tọa độ chính xác<br>
           • Kiểm tra Windows Display Scaling (100% cho kết quả chính xác nhất)<br>
           • Sử dụng <code>Click on Image</code> thay vì tọa độ cố định</p>

        <h3>3. Macro chạy quá nhanh/chậm?</h3>
        <p>• Điều chỉnh <b>Tốc độ</b> trong panel Cài đặt lặp (0.1× – 5×)<br>
           • Thêm action <code>Delay</code> giữa các bước quan trọng<br>
           • Dùng <code>Wait for Image</code> thay Delay để đợi chính xác</p>

        <h3>4. Làm sao dừng macro khi đang chạy vô hạn?</h3>
        <p>• Nhấn <code>F8</code> (Dừng khẩn cấp) — luôn hoạt động<br>
           • Hoặc click <code>⏹ Dừng</code> trong giao diện</p>

        <h3>5. Biến (Variable) dùng như thế nào?</h3>
        <p>• Tạo biến bằng action <code>Set Variable</code><br>
           • Tham chiếu biến bằng cú pháp <code>${tên_biến}</code><br>
           • Dùng <code>If Variable</code> để rẽ nhánh điều kiện<br>
           • Xem giá trị realtime trong panel <b>🔍 Variables</b></p>
        """)
        return tb
