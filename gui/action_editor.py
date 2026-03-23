"""
Action Editor – dialog and panel for adding/editing macro actions.
Provides a user-friendly form for each action type with appropriate widgets.
"""

import logging
import os
from typing import Optional, Callable, Any

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QComboBox, QSpinBox, QDoubleSpinBox, QLineEdit, QPushButton,
    QGroupBox, QCheckBox, QFileDialog, QWidget, QLabel,
)
from PyQt6.QtCore import QTimer, Qt, pyqtSignal

from gui.coordinate_picker import CoordinatePickerOverlay
from gui.image_capture import ImageCaptureOverlay

from core.action import Action, get_action_class, get_all_action_types

logger = logging.getLogger(__name__)

# Grouped action categories for the type selector
ACTION_CATEGORIES: list[tuple[str, list[tuple[str, str]]]] = [
    ("🖱 Mouse", [
        ("mouse_click", "Click"),
        ("mouse_double_click", "Double Click"),
        ("mouse_right_click", "Right Click"),
        ("mouse_move", "Move"),
        ("mouse_drag", "Drag"),
        ("mouse_scroll", "Scroll"),
    ]),
    ("⌨ Keyboard", [
        ("key_press", "Key Press"),
        ("key_combo", "Key Combo"),
        ("type_text", "Type Text"),
        ("hotkey", "Hotkey"),
    ]),
    ("🖼 Image", [
        ("wait_for_image", "Wait for Image"),
        ("click_on_image", "Click on Image"),
        ("image_exists", "Image Exists"),
        ("take_screenshot", "Take Screenshot"),
    ]),
    ("🎨 Pixel", [
        ("check_pixel_color", "Check Pixel Color"),
        ("wait_for_color", "Wait for Color"),
    ]),
    ("⏱ Flow Control", [
        ("delay", "Delay"),
        ("loop_block", "Loop Block"),
        ("if_image_found", "If Image Found"),
        ("if_pixel_color", "If Pixel Color"),
        ("if_variable", "If Variable"),
    ]),
    ("📊 Variables", [
        ("set_variable", "Set Variable"),
        ("split_string", "Split String"),
        ("comment", "Comment / Label"),
    ]),
    ("🖥 System", [
        ("activate_window", "Activate Window"),
        ("log_to_file", "Log to File"),
        ("read_clipboard", "Read Clipboard"),
        ("read_file_line", "Read File Line"),
        ("write_to_file", "Write to File"),
        ("secure_type_text", "Secure Type Text"),
        ("run_macro", "Run Sub-Macro"),
        ("capture_text", "Capture Text (OCR)"),
    ]),
]

# Per-type descriptions shown in editor (P2 #8)
_ACTION_DESCRIPTIONS: dict[str, str] = {
    "mouse_click": "Click chuột trái tại tọa độ (X, Y) hoặc vị trí ảnh mẫu",
    "mouse_double_click": "Double-click chuột trái tại tọa độ hoặc ảnh mẫu",
    "mouse_right_click": "Click chuột phải tại tọa độ hoặc ảnh mẫu",
    "mouse_move": "Di chuyển chuột đến vị trí chỉ định",
    "mouse_drag": "Kéo thả chuột từ vị trí hiện tại đến tọa độ đích",
    "mouse_scroll": "Cuộn chuột lên/xuống số dòng chỉ định",
    "key_press": "Nhấn một phím (đơn hoặc đặc biệt như Enter, Tab)",
    "key_combo": "Nhấn tổ hợp phím (ví dụ: Ctrl+C, Alt+F4)",
    "type_text": "Gõ chuỗi ký tự vào ô nhập liệu hiện tại",
    "hotkey": "Nhấn tổ hợp phím nóng (hỗ trợ nhiều phím)",
    "wait_for_image": "Đợi cho đến khi ảnh mẫu xuất hiện trên màn hình",
    "click_on_image": "Tìm ảnh mẫu trên màn hình và click vào vị trí tìm thấy",
    "image_exists": "Kiểm tra ảnh mẫu có tồn tại trên màn hình không",
    "take_screenshot": "Chụp màn hình và lưu thành file ảnh",
    "check_pixel_color": "Kiểm tra màu pixel tại tọa độ chỉ định",
    "wait_for_color": "Đợi cho đến khi pixel tại tọa độ có màu chỉ định",
    "delay": "Dừng chờ một khoảng thời gian (ms)",
    "loop_block": "Lặp lại nhóm action bên trong số lần chỉ định",
    "if_image_found": "Rẽ nhánh: thực hiện action tuỳ theo ảnh có tìm thấy hay không",
    "if_pixel_color": "Rẽ nhánh: thực hiện action tuỳ theo màu pixel",
    "if_variable": "Rẽ nhánh: so sánh giá trị biến và thực hiện action tương ứng",
    "set_variable": "Tạo hoặc cập nhật giá trị biến (số, chuỗi, biểu thức)",
    "split_string": "Tách chuỗi thành mảng theo dấu phân cách",
    "comment": "Nhãn/ghi chú — không thực thi, dùng để đánh dấu",
    "activate_window": "Kích hoạt cửa sổ ứng dụng theo tiêu đề",
    "log_to_file": "Ghi nội dung vào file log",
    "read_clipboard": "Đọc nội dung clipboard vào biến",
    "read_file_line": "Đọc 1 dòng từ file text vào biến",
    "write_to_file": "Ghi nội dung vào file (tạo mới hoặc nối thêm)",
    "secure_type_text": "Gõ text bảo mật (dùng cho mật khẩu)",
    "run_macro": "Chạy một macro khác như sub-routine",
    "capture_text": "Nhận dạng chữ trên màn hình (OCR) và lưu vào biến",
}

# Rich HTML help content shown when user clicks ❓ button
_ACTION_HELP: dict[str, str] = {
    "mouse_click": (
        "<b>🖱 Click — Click chuột trái</b><br><br>"
        "<b>Ý nghĩa:</b> Giả lập click chuột trái tại tọa độ (X, Y) "
        "trên màn hình, hoặc tại vị trí ảnh mẫu nếu có.<br><br>"
        "<b>Khi nào dùng:</b> Nhấn nút, chọn menu, chọn file, mở app.<br>"
        "<hr>"
        "<b>📌 Ví dụ 1:</b> Click nút <i>Đăng nhập</i><br>"
        "→ X=500, Y=300 (tọa độ cố định)<br><br>"
        "<b>📌 Ví dụ 2:</b> Click icon app trên desktop<br>"
        "→ Dùng Image Match: chọn ảnh icon → click vào vị trí tìm thấy<br><br>"
        "<b>📌 Ví dụ 3:</b> Click ô checkbox trong form<br>"
        "→ X=120, Y=450, Duration=0.1s (click nhanh)<br><br>"
        "<b>📌 Ví dụ 4:</b> Click nút trong game (vị trí thay đổi)<br>"
        "→ Kết hợp Image Match thay vì tọa độ cố định"
    ),
    "mouse_double_click": (
        "<b>🖱 Double Click — Nhấp đúp chuột</b><br><br>"
        "<b>Ý nghĩa:</b> Giả lập nhấp đúp chuột trái (2 click liên tiếp) "
        "để mở file, chọn từ, hoặc kích hoạt item.<br><br>"
        "<b>Khi nào dùng:</b> Mở file/folder, chọn từ trong văn bản.<br>"
        "<hr>"
        "<b>📌 Ví dụ 1:</b> Mở file Excel trên desktop<br>"
        "→ X=200, Y=350 (vị trí file icon)<br><br>"
        "<b>📌 Ví dụ 2:</b> Chọn 1 từ trong trình soạn thảo<br>"
        "→ Double-click tại vị trí từ cần chọn<br><br>"
        "<b>📌 Ví dụ 3:</b> Mở folder trong File Explorer<br>"
        "→ Dùng Image Match nếu folder nằm ở vị trí không cố định"
    ),
    "mouse_right_click": (
        "<b>🖱 Right Click — Click chuột phải</b><br><br>"
        "<b>Ý nghĩa:</b> Giả lập click chuột phải để mở context menu.<br><br>"
        "<b>Khi nào dùng:</b> Mở menu ngữ cảnh, copy/paste, xem properties.<br>"
        "<hr>"
        "<b>📌 Ví dụ 1:</b> Click phải file → chọn Delete<br>"
        "→ Right-click file, sau đó Key Press 'D'<br><br>"
        "<b>📌 Ví dụ 2:</b> Copy text đã chọn<br>"
        "→ Right-click → chọn Copy (hoặc dùng Ctrl+C)<br><br>"
        "<b>📌 Ví dụ 3:</b> Mở Properties của 1 shortcut<br>"
        "→ Right-click icon → click 'Properties'"
    ),
    "mouse_move": (
        "<b>🖱 Move — Di chuyển chuột</b><br><br>"
        "<b>Ý nghĩa:</b> Di chuyển con trỏ chuột đến vị trí chỉ định "
        "mà không click.<br><br>"
        "<b>Khi nào dùng:</b> Hover để hiện tooltip, kéo scrollbar, "
        "di chuột để trigger sự kiện hover.<br>"
        "<hr>"
        "<b>📌 Ví dụ 1:</b> Hover menu để hiện submenu<br>"
        "→ Move đến vị trí menu item, sau đó delay 500ms<br><br>"
        "<b>📌 Ví dụ 2:</b> Di chuột ra giữa màn hình<br>"
        "→ X=960, Y=540 (giữa màn 1920×1080)<br><br>"
        "<b>📌 Ví dụ 3:</b> Chuẩn bị trước khi drag<br>"
        "→ Move đến vị trí bắt đầu drag"
    ),
    "mouse_drag": (
        "<b>🖱 Drag — Kéo thả chuột</b><br><br>"
        "<b>Ý nghĩa:</b> Kéo chuột từ vị trí hiện tại đến tọa độ đích "
        "(giữ nút chuột trong khi di chuyển).<br><br>"
        "<b>Khi nào dùng:</b> Kéo file, resize cửa sổ, chọn vùng text, "
        "vẽ trong paint.<br>"
        "<hr>"
        "<b>📌 Ví dụ 1:</b> Kéo file vào thư mục<br>"
        "→ Move đến file → Drag đến folder (X=400, Y=300)<br><br>"
        "<b>📌 Ví dụ 2:</b> Chọn vùng text bằng chuột<br>"
        "→ Drag từ đầu đến cuối đoạn text<br><br>"
        "<b>📌 Ví dụ 3:</b> Resize cửa sổ<br>"
        "→ Drag góc cửa sổ đến kích thước mong muốn"
    ),
    "mouse_scroll": (
        "<b>🖱 Scroll — Cuộn chuột</b><br><br>"
        "<b>Ý nghĩa:</b> Cuộn chuột lên/xuống tại vị trí chỉ định.<br><br>"
        "<b>Khi nào dùng:</b> Cuộn trang web, cuộn danh sách, zoom in/out.<br>"
        "<hr>"
        "<b>📌 Ví dụ 1:</b> Cuộn xuống cuối trang web<br>"
        "→ Clicks=-5 (cuộn xuống 5 dòng), lặp 10 lần<br><br>"
        "<b>📌 Ví dụ 2:</b> Cuộn danh sách lên đầu<br>"
        "→ Clicks=10 (cuộn lên 10 dòng)<br><br>"
        "<b>📌 Ví dụ 3:</b> Cuộn tại vị trí cụ thể<br>"
        "→ X=500, Y=400, Clicks=-3 (cuộn xuống panel bên phải)"
    ),
    "key_press": (
        "<b>⌨ Key Press — Nhấn phím</b><br><br>"
        "<b>Ý nghĩa:</b> Nhấn 1 phím đơn (chữ, số, hoặc phím đặc biệt "
        "như Enter, Tab, Escape).<br><br>"
        "<b>Khi nào dùng:</b> Nhấn Enter để xác nhận, Tab để chuyển ô, "
        "Escape để đóng dialog.<br>"
        "<hr>"
        "<b>📌 Ví dụ 1:</b> Nhấn Enter sau khi nhập xong<br>"
        "→ Key = 'enter'<br><br>"
        "<b>📌 Ví dụ 2:</b> Nhấn Tab để chuyển sang ô tiếp theo<br>"
        "→ Key = 'tab'<br><br>"
        "<b>📌 Ví dụ 3:</b> Nhấn Escape để đóng popup<br>"
        "→ Key = 'esc'<br><br>"
        "<b>📌 Ví dụ 4:</b> Nhấn F5 để refresh trang<br>"
        "→ Key = 'f5'"
    ),
    "key_combo": (
        "<b>⌨ Key Combo — Tổ hợp phím</b><br><br>"
        "<b>Ý nghĩa:</b> Nhấn tổ hợp phím đồng thời (modifier + key).<br><br>"
        "<b>Khi nào dùng:</b> Copy/Paste, Save, Undo, Select All, "
        "chuyển tab...<br>"
        "<hr>"
        "<b>📌 Ví dụ 1:</b> Copy text<br>"
        "→ Keys = 'ctrl+c'<br><br>"
        "<b>📌 Ví dụ 2:</b> Paste text<br>"
        "→ Keys = 'ctrl+v'<br><br>"
        "<b>📌 Ví dụ 3:</b> Select All<br>"
        "→ Keys = 'ctrl+a'<br><br>"
        "<b>📌 Ví dụ 4:</b> Đóng tab trình duyệt<br>"
        "→ Keys = 'ctrl+w'"
    ),
    "type_text": (
        "<b>⌨ Type Text — Gõ văn bản</b><br><br>"
        "<b>Ý nghĩa:</b> Gõ chuỗi ký tự vào ô nhập liệu đang focus, "
        "từng ký tự một (giả lập gõ phím thật).<br><br>"
        "<b>Khi nào dùng:</b> Điền form, nhập username, gõ nội dung email.<br>"
        "<hr>"
        "<b>📌 Ví dụ 1:</b> Nhập username<br>"
        "→ Text = 'admin@company.com'<br><br>"
        "<b>📌 Ví dụ 2:</b> Nhập nội dung tìm kiếm<br>"
        "→ Text = 'báo cáo tháng 3'<br><br>"
        "<b>📌 Ví dụ 3:</b> Nhập giá trị vào Excel<br>"
        "→ Text = '12500', sau đó Key Press 'tab' để chuyển ô"
    ),
    "hotkey": (
        "<b>⌨ Hotkey — Phím nóng</b><br><br>"
        "<b>Ý nghĩa:</b> Tương tự Key Combo, hỗ trợ nhiều phím "
        "modifier cùng lúc.<br><br>"
        "<b>Khi nào dùng:</b> Tổ hợp 3+ phím, phím tắt hệ thống.<br>"
        "<hr>"
        "<b>📌 Ví dụ 1:</b> Mở Task Manager<br>"
        "→ Keys = 'ctrl+shift+esc'<br><br>"
        "<b>📌 Ví dụ 2:</b> Save As trong Office<br>"
        "→ Keys = 'ctrl+shift+s'<br><br>"
        "<b>📌 Ví dụ 3:</b> Chuyển desktop ảo<br>"
        "→ Keys = 'ctrl+win+right'"
    ),
    "wait_for_image": (
        "<b>🖼 Wait for Image — Đợi ảnh xuất hiện</b><br><br>"
        "<b>Ý nghĩa:</b> Tạm dừng macro cho đến khi ảnh mẫu được "
        "tìm thấy trên màn hình (hoặc hết timeout).<br><br>"
        "<b>Khi nào dùng:</b> Đợi trang load xong, đợi dialog xuất hiện, "
        "đợi download hoàn tất.<br>"
        "<hr>"
        "<b>📌 Ví dụ 1:</b> Đợi trang web load xong<br>"
        "→ Ảnh mẫu = logo trang, Timeout = 30s<br><br>"
        "<b>📌 Ví dụ 2:</b> Đợi hộp thoại 'Save' xuất hiện<br>"
        "→ Ảnh mẫu = nút Save, Timeout = 10s<br><br>"
        "<b>📌 Ví dụ 3:</b> Đợi download file xong<br>"
        "→ Ảnh mẫu = thông báo 'completed', Timeout = 60s"
    ),
    "click_on_image": (
        "<b>🖼 Click on Image — Click vào ảnh tìm thấy</b><br><br>"
        "<b>Ý nghĩa:</b> Tìm ảnh mẫu trên màn hình, nếu tìm thấy "
        "→ click vào giữa vị trí ảnh.<br><br>"
        "<b>Khi nào dùng:</b> Click nút có vị trí thay đổi, click icon "
        "trong game, click phần tử UI động.<br>"
        "<hr>"
        "<b>📌 Ví dụ 1:</b> Click nút 'OK' trong dialog<br>"
        "→ Ảnh mẫu = ảnh chụp nút OK<br><br>"
        "<b>📌 Ví dụ 2:</b> Click icon trong system tray<br>"
        "→ Ảnh mẫu = ảnh icon app<br><br>"
        "<b>📌 Ví dụ 3:</b> Click enemy trong game<br>"
        "→ Ảnh mẫu = sprite enemy, Confidence = 0.8"
    ),
    "image_exists": (
        "<b>🖼 Image Exists — Kiểm tra ảnh có tồn tại</b><br><br>"
        "<b>Ý nghĩa:</b> Kiểm tra xem ảnh mẫu có xuất hiện trên màn hình "
        "hay không (trả về True/False, không click).<br><br>"
        "<b>Khi nào dùng:</b> Kiểm tra trạng thái UI trước khi hành động.<br>"
        "<hr>"
        "<b>📌 Ví dụ 1:</b> Kiểm tra đã đăng nhập chưa<br>"
        "→ Ảnh = avatar user, nếu có → đã login<br><br>"
        "<b>📌 Ví dụ 2:</b> Kiểm tra popup error có xuất hiện<br>"
        "→ Kết hợp If Image Found để xử lý<br><br>"
        "<b>📌 Ví dụ 3:</b> Kiểm tra app đã mở chưa<br>"
        "→ Ảnh = title bar của app"
    ),
    "take_screenshot": (
        "<b>🖼 Take Screenshot — Chụp màn hình</b><br><br>"
        "<b>Ý nghĩa:</b> Chụp toàn bộ màn hình và lưu thành file ảnh.<br><br>"
        "<b>Khi nào dùng:</b> Lưu bằng chứng, debug, báo cáo lỗi.<br>"
        "<hr>"
        "<b>📌 Ví dụ 1:</b> Chụp kết quả sau khi chạy xong<br>"
        "→ Lưu vào folder 'screenshots/'<br><br>"
        "<b>📌 Ví dụ 2:</b> Chụp lỗi khi macro gặp sự cố<br>"
        "→ Đặt sau action On Error để ghi lại trạng thái<br><br>"
        "<b>📌 Ví dụ 3:</b> Chụp hàng loạt trang báo cáo<br>"
        "→ Loop: scroll → screenshot → lặp lại"
    ),
    "check_pixel_color": (
        "<b>🎨 Check Pixel Color — Kiểm tra màu pixel</b><br><br>"
        "<b>Ý nghĩa:</b> Lấy màu pixel tại tọa độ (X, Y) và so sánh "
        "với màu chỉ định.<br><br>"
        "<b>Khi nào dùng:</b> Kiểm tra trạng thái UI theo màu sắc.<br>"
        "<hr>"
        "<b>📌 Ví dụ 1:</b> Kiểm tra nút có active không<br>"
        "→ Nút active = xanh (#00FF00), inactive = xám<br><br>"
        "<b>📌 Ví dụ 2:</b> Kiểm tra checkbox đã tick chưa<br>"
        "→ Pixel tại vị trí tick = xanh → đã check<br><br>"
        "<b>📌 Ví dụ 3:</b> Phát hiện thanh loading đã đầy<br>"
        "→ Pixel cuối thanh = xanh → loading xong"
    ),
    "wait_for_color": (
        "<b>🎨 Wait for Color — Đợi pixel đổi màu</b><br><br>"
        "<b>Ý nghĩa:</b> Tạm dừng cho đến khi pixel tại tọa độ "
        "chuyển sang màu chỉ định.<br><br>"
        "<b>Khi nào dùng:</b> Đợi loading bar, đợi nút enable.<br>"
        "<hr>"
        "<b>📌 Ví dụ 1:</b> Đợi loading bar hoàn tất<br>"
        "→ Tọa độ cuối bar, màu = xanh, Timeout = 30s<br><br>"
        "<b>📌 Ví dụ 2:</b> Đợi nút từ xám chuyển sang xanh<br>"
        "→ Màu mục tiêu = #4CAF50, Tolerance = 10<br><br>"
        "<b>📌 Ví dụ 3:</b> Đợi popup biến mất<br>"
        "→ Pixel trên popup → đợi chuyển về màu nền"
    ),
    "delay": (
        "<b>⏱ Delay — Chờ đợi</b><br><br>"
        "<b>Ý nghĩa:</b> Tạm dừng macro trong khoảng thời gian chỉ định "
        "(ms).<br><br>"
        "<b>Khi nào dùng:</b> Đợi animation, đợi network, tránh rate-limit.<br>"
        "<hr>"
        "<b>📌 Ví dụ 1:</b> Đợi trang load sau click<br>"
        "→ Duration = 2000ms (2 giây)<br><br>"
        "<b>📌 Ví dụ 2:</b> Đợi animation hoàn tất<br>"
        "→ Duration = 500ms<br><br>"
        "<b>📌 Ví dụ 3:</b> Tránh rate-limit API<br>"
        "→ Duration = 1000ms giữa các request"
    ),
    "loop_block": (
        "<b>⏱ Loop Block — Vòng lặp</b><br><br>"
        "<b>Ý nghĩa:</b> Lặp lại nhóm action bên trong số lần chỉ định "
        "(hoặc vô hạn).<br><br>"
        "<b>Khi nào dùng:</b> Xử lý hàng loạt, lặp thao tác, auto-farm.<br>"
        "<hr>"
        "<b>📌 Ví dụ 1:</b> Gửi 50 email giống nhau<br>"
        "→ Loop 50: click Compose → type → send<br><br>"
        "<b>📌 Ví dụ 2:</b> Auto-click quảng cáo<br>"
        "→ Loop ∞: click → delay 5s → lặp<br><br>"
        "<b>📌 Ví dụ 3:</b> Đọc 100 dòng từ file<br>"
        "→ Loop 100: read_file_line → type_text → tab"
    ),
    "if_image_found": (
        "<b>⏱ If Image Found — Rẽ nhánh theo ảnh</b><br><br>"
        "<b>Ý nghĩa:</b> Kiểm tra ảnh mẫu có trên màn hình → "
        "thực hiện action khác nhau tùy kết quả.<br><br>"
        "<b>Khi nào dùng:</b> Xử lý popup bất ngờ, kiểm tra trạng thái.<br>"
        "<hr>"
        "<b>📌 Ví dụ 1:</b> Xử lý popup 'Are you sure?'<br>"
        "→ Nếu popup xuất hiện → click Yes, nếu không → bỏ qua<br><br>"
        "<b>📌 Ví dụ 2:</b> Kiểm tra CAPTCHA<br>"
        "→ Nếu thấy CAPTCHA → dừng, nếu không → tiếp tục<br><br>"
        "<b>📌 Ví dụ 3:</b> Auto-retry khi lỗi<br>"
        "→ Nếu thấy 'Error' → click Retry, lặp lại"
    ),
    "if_pixel_color": (
        "<b>⏱ If Pixel Color — Rẽ nhánh theo màu</b><br><br>"
        "<b>Ý nghĩa:</b> Kiểm tra màu pixel tại tọa độ → rẽ nhánh.<br><br>"
        "<b>Khi nào dùng:</b> Tương tự If Image nhưng nhanh hơn.<br>"
        "<hr>"
        "<b>📌 Ví dụ 1:</b> Nút xanh → click, nút xám → đợi<br>"
        "→ Check pixel tại vị trí nút<br><br>"
        "<b>📌 Ví dụ 2:</b> HP bar > 50% → attack, < 50% → heal<br>"
        "→ Check pixel giữa HP bar<br><br>"
        "<b>📌 Ví dụ 3:</b> Phát hiện ngày/đêm trong game<br>"
        "→ Check pixel trời: sáng → farm, tối → nghỉ"
    ),
    "if_variable": (
        "<b>⏱ If Variable — Rẽ nhánh theo biến</b><br><br>"
        "<b>Ý nghĩa:</b> So sánh giá trị biến với giá trị chỉ định "
        "→ thực hiện action tương ứng.<br><br>"
        "<b>Khi nào dùng:</b> Logic phức tạp, đếm lần lặp, kiểm tra input.<br>"
        "<hr>"
        "<b>📌 Ví dụ 1:</b> Nếu counter > 10 → dừng<br>"
        "→ Variable = 'counter', Operator = '>', Value = '10'<br><br>"
        "<b>📌 Ví dụ 2:</b> Nếu username rỗng → bỏ qua<br>"
        "→ Variable = 'username', Operator = '==', Value = ''<br><br>"
        "<b>📌 Ví dụ 3:</b> Kiểm tra OCR result<br>"
        "→ Variable = 'ocr_text', Operator = 'contains', Value = 'success'"
    ),
    "set_variable": (
        "<b>📊 Set Variable — Gán giá trị biến</b><br><br>"
        "<b>Ý nghĩa:</b> Tạo mới hoặc cập nhật giá trị biến. "
        "Hỗ trợ: số, chuỗi, biểu thức toán.<br><br>"
        "<b>Khi nào dùng:</b> Đếm, lưu trạng thái, tính toán.<br>"
        "<hr>"
        "<b>📌 Ví dụ 1:</b> Đếm lần lặp<br>"
        "→ Name = 'counter', Value = '{counter} + 1'<br><br>"
        "<b>📌 Ví dụ 2:</b> Lưu URL cần truy cập<br>"
        "→ Name = 'url', Value = 'https://example.com'<br><br>"
        "<b>📌 Ví dụ 3:</b> Tạo timestamp<br>"
        "→ Name = 'filename', Value = 'report_{counter}.pdf'"
    ),
    "split_string": (
        "<b>📊 Split String — Tách chuỗi</b><br><br>"
        "<b>Ý nghĩa:</b> Tách chuỗi thành mảng theo dấu phân cách, "
        "lấy phần tử theo index.<br><br>"
        "<b>Khi nào dùng:</b> Xử lý CSV, tách dữ liệu OCR, parse text.<br>"
        "<hr>"
        "<b>📌 Ví dụ 1:</b> Tách dòng CSV<br>"
        "→ Input = 'Tên,Email,SĐT', Separator = ','<br><br>"
        "<b>📌 Ví dụ 2:</b> Lấy tên file từ đường dẫn<br>"
        "→ Input = path, Separator = '\\', Index = -1<br><br>"
        "<b>📌 Ví dụ 3:</b> Tách username từ email<br>"
        "→ Input = 'user@company.com', Separator = '@', Index = 0"
    ),
    "comment": (
        "<b>📊 Comment — Ghi chú</b><br><br>"
        "<b>Ý nghĩa:</b> Nhãn/ghi chú không thực thi. "
        "Dùng để đánh dấu các phần trong macro.<br><br>"
        "<b>Khi nào dùng:</b> Luôn luôn! Giúp macro dễ đọc, dễ bảo trì.<br>"
        "<hr>"
        "<b>📌 Ví dụ 1:</b> Đánh dấu phần đầu<br>"
        "→ Text = '=== PHẦN 1: ĐĂNG NHẬP ==='<br><br>"
        "<b>📌 Ví dụ 2:</b> Ghi chú cảnh báo<br>"
        "→ Text = '⚠ Đợi 5s vì server chậm'<br><br>"
        "<b>📌 Ví dụ 3:</b> Note cho bản thân<br>"
        "→ Text = 'TODO: thêm xử lý lỗi ở đây'"
    ),
    "activate_window": (
        "<b>🖥 Activate Window — Kích hoạt cửa sổ</b><br><br>"
        "<b>Ý nghĩa:</b> Tìm và đưa cửa sổ ứng dụng lên foreground "
        "theo tiêu đề (hoặc một phần tiêu đề).<br><br>"
        "<b>Khi nào dùng:</b> Chuyển giữa các app, đảm bảo focus đúng app.<br>"
        "<hr>"
        "<b>📌 Ví dụ 1:</b> Chuyển sang Chrome<br>"
        "→ Title = 'Chrome' (tìm cửa sổ chứa 'Chrome')<br><br>"
        "<b>📌 Ví dụ 2:</b> Chuyển sang Excel file cụ thể<br>"
        "→ Title = 'BaoCao.xlsx'<br><br>"
        "<b>📌 Ví dụ 3:</b> Focus CMD/Terminal<br>"
        "→ Title = 'Command Prompt'"
    ),
    "log_to_file": (
        "<b>🖥 Log to File — Ghi log</b><br><br>"
        "<b>Ý nghĩa:</b> Ghi nội dung vào file log (text). "
        "Hỗ trợ biến trong nội dung.<br><br>"
        "<b>Khi nào dùng:</b> Debug macro, ghi kết quả, audit trail.<br>"
        "<hr>"
        "<b>📌 Ví dụ 1:</b> Ghi kết quả mỗi vòng lặp<br>"
        "→ File = 'log.txt', Text = 'Vòng {counter}: OK'<br><br>"
        "<b>📌 Ví dụ 2:</b> Ghi timestamp<br>"
        "→ Text = '{timestamp}: Đã xử lý xong'<br><br>"
        "<b>📌 Ví dụ 3:</b> Ghi lỗi OCR<br>"
        "→ Text = 'OCR result: {ocr_text}'"
    ),
    "read_clipboard": (
        "<b>🖥 Read Clipboard — Đọc clipboard</b><br><br>"
        "<b>Ý nghĩa:</b> Đọc nội dung clipboard (sau Ctrl+C) vào biến.<br><br>"
        "<b>Khi nào dùng:</b> Lấy text đã copy, lấy URL, lấy dữ liệu.<br>"
        "<hr>"
        "<b>📌 Ví dụ 1:</b> Copy → lấy text → paste elsewhere<br>"
        "→ Ctrl+C → Read Clipboard → biến 'copied_text'<br><br>"
        "<b>📌 Ví dụ 2:</b> Lấy URL từ thanh địa chỉ<br>"
        "→ Click address bar → Ctrl+A → Ctrl+C → Read Clipboard<br><br>"
        "<b>📌 Ví dụ 3:</b> Copy giá trị từ Excel<br>"
        "→ Click cell → Ctrl+C → Read Clipboard → Log to File"
    ),
    "read_file_line": (
        "<b>🖥 Read File Line — Đọc dòng từ file</b><br><br>"
        "<b>Ý nghĩa:</b> Đọc 1 dòng cụ thể từ file text vào biến. "
        "Dùng line_number hoặc tự động tăng.<br><br>"
        "<b>Khi nào dùng:</b> Đọc danh sách URL, email, dữ liệu từ CSV.<br>"
        "<hr>"
        "<b>📌 Ví dụ 1:</b> Đọc danh sách URL<br>"
        "→ File = 'urls.txt', Line = {counter}, Var = 'url'<br><br>"
        "<b>📌 Ví dụ 2:</b> Đọc email từ danh sách<br>"
        "→ File = 'emails.txt', Auto-increment = On<br><br>"
        "<b>📌 Ví dụ 3:</b> Đọc mật khẩu từ file bảo mật<br>"
        "→ File = 'creds.txt', Line = 2 (dòng 2 = password)"
    ),
    "write_to_file": (
        "<b>🖥 Write to File — Ghi vào file</b><br><br>"
        "<b>Ý nghĩa:</b> Ghi nội dung vào file (tạo mới hoặc append). "
        "Hỗ trợ biến trong nội dung.<br><br>"
        "<b>Khi nào dùng:</b> Xuất kết quả, ghi CSV, tạo report.<br>"
        "<hr>"
        "<b>📌 Ví dụ 1:</b> Ghi kết quả ra CSV<br>"
        "→ File = 'result.csv', Text = '{name},{email},{phone}'<br><br>"
        "<b>📌 Ví dụ 2:</b> Tạo file báo cáo<br>"
        "→ File = 'report.txt', Mode = Append<br><br>"
        "<b>📌 Ví dụ 3:</b> Backup dữ liệu<br>"
        "→ File = 'backup_{date}.txt', Text = clipboard content"
    ),
    "secure_type_text": (
        "<b>🖥 Secure Type Text — Gõ bảo mật</b><br><br>"
        "<b>Ý nghĩa:</b> Gõ text mà không hiển thị nội dung trong log/preview. "
        "Dùng cho mật khẩu, token.<br><br>"
        "<b>Khi nào dùng:</b> Nhập password, API key, thông tin nhạy cảm.<br>"
        "<hr>"
        "<b>📌 Ví dụ 1:</b> Nhập mật khẩu đăng nhập<br>"
        "→ Text = 'P@ssw0rd!' (hiển thị ****)<br><br>"
        "<b>📌 Ví dụ 2:</b> Nhập API key<br>"
        "→ Text = 'sk-xxx...' (không lộ trong log)<br><br>"
        "<b>📌 Ví dụ 3:</b> Nhập mã OTP<br>"
        "→ Kết hợp Read Clipboard → Secure Type"
    ),
    "run_macro": (
        "<b>🖥 Run Sub-Macro — Chạy macro con</b><br><br>"
        "<b>Ý nghĩa:</b> Chạy 1 file macro khác như subroutine. "
        "Macro con chạy xong → quay lại macro chính.<br><br>"
        "<b>Khi nào dùng:</b> Tái sử dụng macro, chia nhỏ logic phức tạp.<br>"
        "<hr>"
        "<b>📌 Ví dụ 1:</b> Gọi macro 'login.json'<br>"
        "→ Macro = 'login.json' (đăng nhập → quay lại)<br><br>"
        "<b>📌 Ví dụ 2:</b> Chia macro lớn thành phần<br>"
        "→ Main: run 'step1.json' → run 'step2.json' → ...<br><br>"
        "<b>📌 Ví dụ 3:</b> Error recovery<br>"
        "→ On Error: run 'recovery.json' → retry"
    ),
    "capture_text": (
        "<b>🖥 Capture Text (OCR) — Nhận dạng chữ</b><br><br>"
        "<b>Ý nghĩa:</b> Chụp vùng màn hình và nhận dạng text bằng "
        "Tesseract OCR, lưu kết quả vào biến.<br><br>"
        "<b>Khi nào dùng:</b> Đọc text từ ảnh, lấy giá trị từ UI không copy được.<br>"
        "<hr>"
        "<b>📌 Ví dụ 1:</b> Đọc số dư tài khoản<br>"
        "→ Vùng chụp = khu vực hiển thị số dư<br><br>"
        "<b>📌 Ví dụ 2:</b> Đọc mã CAPTCHA<br>"
        "→ OCR vùng CAPTCHA → nhập kết quả<br><br>"
        "<b>📌 Ví dụ 3:</b> Đọc thông báo lỗi<br>"
        "→ OCR popup → If Variable contains 'error' → xử lý"
    ),
}

class ActionEditorDialog(QDialog):
    """
    Modal dialog for creating or editing a single action.
    Emits action_ready(action) when user confirms.
    """
    action_ready = pyqtSignal(object)  # emits Action before dialog closes

    def __init__(self, parent: Any = None, action: Optional[Action] = None,
                 macro_dir: str = "") -> None:
        super().__init__(parent)
        self._action = action
        self._macro_dir = macro_dir
        self._result_action: Optional[Action] = None
        self._param_widgets: dict[str, Any] = {}

        self.setWindowTitle("Sửa Action" if action else "Thêm Action")
        self.setMinimumWidth(480)
        self.resize(500, 520)
        self.setSizeGripEnabled(True)
        self.setModal(True)
        self._param_cache: dict[str, Any] = {}  # persist x,y across types

        self._setup_ui()

        if action:
            self._load_action(action)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Action type selector — grouped with category headers
        type_group = QGroupBox("Loại Action")
        type_layout = QVBoxLayout(type_group)

        # Combo + Help button in same row
        combo_row = QHBoxLayout()
        self._type_combo = QComboBox()
        self._build_grouped_combo()
        self._type_combo.currentIndexChanged.connect(self._on_type_changed)
        combo_row.addWidget(self._type_combo, stretch=1)

        self._help_btn = QPushButton("❓")
        self._help_btn.setFixedSize(28, 28)
        self._help_btn.setToolTip("Xem hướng dẫn & ví dụ")
        self._help_btn.setAccessibleName("Hướng dẫn action")
        self._help_btn.clicked.connect(self._show_action_help)
        combo_row.addWidget(self._help_btn)
        type_layout.addLayout(combo_row)

        # Action type description (P2 #8)
        self._type_desc_label = QLabel("")
        self._type_desc_label.setObjectName("subtitleLabel")
        self._type_desc_label.setWordWrap(True)
        type_layout.addWidget(self._type_desc_label)
        layout.addWidget(type_group)

        # Parameters area (dynamic)
        self._params_group = QGroupBox("Tham số")
        self._params_layout = QFormLayout(self._params_group)
        layout.addWidget(self._params_group)

        # Common settings
        common_group = QGroupBox("Cài đặt chung")
        common_layout = QFormLayout(common_group)

        self._delay_spin = QSpinBox()
        self._delay_spin.setRange(0, 60000)
        self._delay_spin.setSuffix(" ms")
        self._delay_spin.setValue(0)
        common_layout.addRow("Delay After:", self._delay_spin)

        self._repeat_spin = QSpinBox()
        self._repeat_spin.setRange(1, 10000)
        self._repeat_spin.setValue(1)
        common_layout.addRow("Repeat:", self._repeat_spin)

        self._desc_edit = QLineEdit()
        self._desc_edit.setPlaceholderText("Optional description...")
        common_layout.addRow("Description:", self._desc_edit)

        self._enabled_check = QCheckBox("Enabled")
        self._enabled_check.setChecked(True)
        common_layout.addRow("", self._enabled_check)

        self._error_combo = QComboBox()
        self._error_combo.addItems(["stop", "skip", "retry:3", "retry:5"])
        self._error_combo.setToolTip("What to do when this action fails")
        common_layout.addRow("On Error:", self._error_combo)

        layout.addWidget(common_group)

        # OK / Cancel
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        ok_btn = QPushButton("OK")
        ok_btn.setObjectName("primaryButton")
        ok_btn.clicked.connect(self._on_ok)
        btn_layout.addWidget(ok_btn)
        layout.addLayout(btn_layout)

        # Show first selectable type's params
        # Skip to first non-header item
        for i in range(self._type_combo.count()):
            if self._type_combo.itemData(i, Qt.ItemDataRole.UserRole) is not None:
                self._type_combo.setCurrentIndex(i)
                break
        self._on_type_changed()

    def _build_grouped_combo(self) -> None:
        """Build grouped combo box with category headers."""
        from PyQt6.QtGui import QStandardItemModel, QStandardItem, QFont
        model = QStandardItemModel()
        for cat_label, actions in ACTION_CATEGORIES:
            # Category header (non-selectable, bold)
            header = QStandardItem(cat_label)
            header_font = QFont()
            header_font.setBold(True)
            header.setFont(header_font)
            header.setEnabled(False)                     # non-selectable
            header.setSelectable(False)
            model.appendRow(header)
            # Action items (indented with spaces)
            for atype, label in actions:
                item = QStandardItem(f"    {label}")
                item.setData(atype, Qt.ItemDataRole.UserRole)
                model.appendRow(item)
        self._type_combo.setModel(model)

    def _clear_params(self) -> None:
        """Remove all dynamic parameter widgets, cache reusable values."""
        # Cache x,y before clearing
        for key in ("x", "y"):
            w = self._param_widgets.get(key)
            if w and isinstance(w, QSpinBox):
                self._param_cache[key] = w.value()
        while self._params_layout.count():
            item = self._params_layout.takeAt(0)
            if item is None:
                break
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self._param_widgets.clear()

    def _on_type_changed(self) -> None:
        """Rebuild parameter widgets when action type changes."""
        self._clear_params()
        atype = self._type_combo.currentData(Qt.ItemDataRole.UserRole)
        if not atype:
            self._type_desc_label.setText("")
            return

        # Update description (P2 #8)
        self._type_desc_label.setText(
            f"ℹ️ {_ACTION_DESCRIPTIONS.get(atype, '')}")

        # Dispatch to per-category builder
        builders: dict[str, Callable[[], None]] = {
            "mouse_click": lambda: self._build_mouse_params(atype),
            "mouse_double_click": lambda: self._build_mouse_params(atype),
            "mouse_right_click": lambda: self._build_mouse_params(atype),
            "mouse_move": lambda: self._build_mouse_params(atype),
            "mouse_drag": self._build_drag_params,
            "mouse_scroll": self._build_scroll_params,
            "key_press": self._build_key_press_params,
            "key_combo": self._build_key_combo_params,
            "hotkey": self._build_key_combo_params,
            "type_text": self._build_type_text_params,
            "delay": self._build_delay_params,
            "wait_for_image": lambda: self._build_image_params(atype),
            "click_on_image": lambda: self._build_image_params(atype),
            "image_exists": lambda: self._build_image_params(atype),
            "check_pixel_color": lambda: self._build_pixel_params(atype),
            "wait_for_color": lambda: self._build_pixel_params(atype),
            "take_screenshot": self._build_screenshot_params,
            "if_pixel_color": lambda: self._build_pixel_params(atype),
            "if_image_found": self._build_if_image_found_params,
            "loop_block": self._build_loop_block_params,
            "if_variable": self._build_if_variable_params,
            "set_variable": self._build_set_variable_params,
            "split_string": self._build_split_string_params,
            "comment": self._build_comment_params,
            "activate_window": self._build_activate_window_params,
            "log_to_file": self._build_log_params,
            "read_clipboard": self._build_read_clipboard_params,
            "read_file_line": self._build_read_file_line_params,
            "write_to_file": self._build_write_file_params,
            "secure_type_text": self._build_secure_text_params,
            "run_macro": self._build_run_macro_params,
            "capture_text": self._build_capture_text_params,
        }
        builder = builders.get(atype)
        if builder:
            builder()
        elif atype:
            import logging
            logging.getLogger(__name__).warning(
                "No param builder registered for action type '%s'", atype)

        # Restore cached x,y values if new type also has them
        for key in ("x", "y"):
            if key in self._param_cache and key in self._param_widgets:
                w = self._param_widgets[key]
                if isinstance(w, QSpinBox):
                    w.setValue(self._param_cache[key])

    def _show_action_help(self) -> None:
        """Show rich HTML help tooltip for the selected action type."""
        from PyQt6.QtWidgets import QToolTip
        atype = self._type_combo.currentData(Qt.ItemDataRole.UserRole)
        if not atype:
            return
        html = _ACTION_HELP.get(atype)
        if not html:
            display_name = self._type_combo.currentText()
            desc = _ACTION_DESCRIPTIONS.get(atype, "")
            html = (
                f"<b>{display_name}</b><br><br>"
                f"{desc}<br><br>"
                "<i>Chưa có hướng dẫn chi tiết cho action này.</i>"
            )
        # Show tooltip at button position, with max width
        pos = self._help_btn.mapToGlobal(self._help_btn.rect().bottomLeft())
        QToolTip.showText(pos, f"<div style='max-width:380px'>{html}</div>",
                          self._help_btn)

    def _build_mouse_params(self, atype: str) -> None:
        self._add_xy_params()
        if atype in ("mouse_click", "mouse_move"):
            self._add_duration_param()

    def _build_drag_params(self) -> None:
        self._add_xy_params()
        self._add_duration_param()
        self._add_button_param()

    def _build_scroll_params(self) -> None:
        self._add_xy_params()
        clicks = QSpinBox()
        clicks.setRange(-100, 100)
        clicks.setValue(3)
        self._params_layout.addRow("Clicks (+ up, - down):", clicks)
        self._param_widgets["clicks"] = clicks

    def _build_key_press_params(self) -> None:
        key_edit = QLineEdit("enter")
        self._params_layout.addRow("Key:", key_edit)
        self._param_widgets["key"] = key_edit

    def _build_key_combo_params(self) -> None:
        keys_edit = QLineEdit("ctrl+c")
        keys_edit.setPlaceholderText("e.g. ctrl+shift+s")
        self._params_layout.addRow("Keys (use +):", keys_edit)
        self._param_widgets["keys_str"] = keys_edit

    def _build_type_text_params(self) -> None:
        text_edit = QLineEdit()
        text_edit.setPlaceholderText("Text to type...")
        self._params_layout.addRow("Text:", text_edit)
        self._param_widgets["text"] = text_edit
        interval = QDoubleSpinBox()
        interval.setRange(0.0, 1.0)
        interval.setSingleStep(0.01)
        interval.setValue(0.02)
        interval.setSuffix(" s")
        self._params_layout.addRow("Interval:", interval)
        self._param_widgets["interval"] = interval

    def _build_delay_params(self) -> None:
        dur = QSpinBox()
        dur.setRange(0, 300000)
        dur.setSuffix(" ms")
        dur.setValue(1000)
        self._params_layout.addRow("Duration:", dur)
        self._param_widgets["duration_ms"] = dur

    def _build_image_params(self, atype: str) -> None:
        self._add_image_params()
        if atype in ("wait_for_image", "click_on_image"):
            timeout = QSpinBox()
            timeout.setRange(0, 120000)
            timeout.setSuffix(" ms")
            timeout.setValue(10000)
            self._params_layout.addRow("Timeout:", timeout)
            self._param_widgets["timeout_ms"] = timeout
        if atype == "click_on_image":
            self._add_button_param()

    def _build_screenshot_params(self) -> None:
        # Save directory
        dir_layout = QHBoxLayout()
        dir_edit = QLineEdit("macros/screenshots")
        dir_edit.setPlaceholderText("Thư mục lưu ảnh...")
        dir_browse = QPushButton("Browse")
        dir_browse.clicked.connect(lambda: self._browse_dir(dir_edit))
        dir_layout.addWidget(dir_edit)
        dir_layout.addWidget(dir_browse)
        dir_wrapper = QWidget()
        dir_wrapper.setLayout(dir_layout)
        self._params_layout.addRow("Save Folder:", dir_wrapper)
        self._param_widgets["save_dir"] = dir_edit

        # Filename pattern
        pattern_edit = QLineEdit("screenshot_%Y%m%d_%H%M%S.png")
        pattern_edit.setToolTip(
            "%Y=năm, %m=tháng, %d=ngày, %H=giờ, %M=phút, %S=giây"
        )
        self._params_layout.addRow("Filename:", pattern_edit)
        self._param_widgets["filename_pattern"] = pattern_edit

        # Optional region (0 = full screen)
        for label, key, default in [
            ("Region X:", "region_x", 0), ("Region Y:", "region_y", 0),
            ("Region W:", "region_w", 0), ("Region H:", "region_h", 0),
        ]:
            spin = QSpinBox()
            spin.setRange(0, 9999)
            spin.setValue(default)
            spin.setToolTip("0 = chụp toàn màn hình")
            self._params_layout.addRow(label, spin)
            self._param_widgets[key] = spin

    def _browse_dir(self, line_edit: QLineEdit) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select Folder")
        if path:
            line_edit.setText(path)

    def _build_pixel_params(self, atype: str) -> None:
        self._add_xy_params()
        for color_name, default_val in [("r", 255), ("g", 0), ("b", 0)]:
            spin = QSpinBox()
            spin.setRange(0, 255)
            spin.setValue(default_val)
            self._params_layout.addRow(f"Color {color_name.upper()}:", spin)
            self._param_widgets[color_name] = spin
        tol = QSpinBox()
        tol.setRange(0, 255)
        tol.setValue(10)
        self._params_layout.addRow("Tolerance:", tol)
        self._param_widgets["tolerance"] = tol
        if atype == "wait_for_color":
            timeout = QSpinBox()
            timeout.setRange(0, 120000)
            timeout.setSuffix(" ms")
            timeout.setValue(10000)
            self._params_layout.addRow("Timeout:", timeout)
            self._param_widgets["timeout_ms"] = timeout

    def _add_xy_params(self) -> None:
        x_spin = QSpinBox()
        x_spin.setRange(0, 9999)
        self._params_layout.addRow("X:", x_spin)
        self._param_widgets["x"] = x_spin

        y_spin = QSpinBox()
        y_spin.setRange(0, 9999)
        self._params_layout.addRow("Y:", y_spin)
        self._param_widgets["y"] = y_spin

        # Coordinate Picker button
        pick_btn = QPushButton("📌 Pick from Screen")
        pick_btn.setObjectName("primaryButton")
        pick_btn.setToolTip(
            "Click to pick coordinates from screen.\n"
            "Click on any point → coordinates auto-fill.\n"
            "Press Escape to cancel."
        )
        pick_btn.clicked.connect(
            lambda: self._start_coordinate_picker(x_spin, y_spin)
        )
        self._params_layout.addRow("", pick_btn)

    def _build_if_image_found_params(self) -> None:
        """Builder for IfImageFound — image path, confidence, timeout, ELSE."""
        self._add_image_params()

        timeout = QSpinBox()
        timeout.setRange(0, 120000)
        timeout.setSuffix(" ms")
        timeout.setValue(5000)
        self._params_layout.addRow("Timeout:", timeout)
        self._param_widgets["timeout_ms"] = timeout

        # 3.1: ELSE action (optional)
        else_action = QLineEdit()
        else_action.setPlaceholderText('Optional ELSE: {"type":"log_to_file","params":{"message":"Image not found"}}')
        else_action.setToolTip("Action to execute when image is NOT found (JSON)")
        self._params_layout.addRow("Else Action:", else_action)
        self._param_widgets["else_action_json"] = else_action

    def _build_loop_block_params(self) -> None:
        """Builder for LoopBlock — iterations count."""
        iterations = QSpinBox()
        iterations.setRange(0, 999999)
        iterations.setValue(1)
        iterations.setSpecialValueText("∞ Infinite")
        iterations.setToolTip("0 = infinite loop (until stopped)")
        self._params_layout.addRow("Iterations:", iterations)
        self._param_widgets["iterations"] = iterations

    def _build_if_variable_params(self) -> None:
        var_name = QLineEdit()
        var_name.setPlaceholderText("e.g. counter, row")
        self._params_layout.addRow("Variable:", var_name)
        self._param_widgets["var_name"] = var_name

        operator = QComboBox()
        operator.addItems(["==", "!=", ">", "<", ">=", "<="])
        self._params_layout.addRow("Operator:", operator)
        self._param_widgets["operator"] = operator

        compare_value = QLineEdit()
        compare_value.setPlaceholderText("e.g. 10, hello")
        self._params_layout.addRow("Compare Value:", compare_value)
        self._param_widgets["compare_value"] = compare_value

        # 3.1: ELSE action (optional)
        else_action = QLineEdit()
        else_action.setPlaceholderText('Optional JSON: {"type":"set_variable","params":{"var_name":"x","value":"0","operation":"set"}}')
        else_action.setToolTip("Define an action to execute when condition is FALSE (JSON format)")
        self._params_layout.addRow("Else Action:", else_action)
        self._param_widgets["else_action_json"] = else_action

    def _build_set_variable_params(self) -> None:
        var_name = QLineEdit()
        var_name.setPlaceholderText("e.g. counter, row")
        self._params_layout.addRow("Variable:", var_name)
        self._param_widgets["var_name"] = var_name

        value = QLineEdit()
        value.setPlaceholderText("e.g. 0, 1, hello")
        self._params_layout.addRow("Value:", value)
        self._param_widgets["value"] = value

        operation = QComboBox()
        operation.addItems(["set", "increment", "decrement", "add",
                           "subtract", "multiply", "divide", "modulo", "eval"])
        self._params_layout.addRow("Operation:", operation)
        self._param_widgets["operation"] = operation

    def _build_split_string_params(self) -> None:
        src = QLineEdit()
        src.setPlaceholderText("Source variable name")
        self._params_layout.addRow("Source Var:", src)
        self._param_widgets["source_var"] = src

        delim = QLineEdit()
        delim.setText(",")
        self._params_layout.addRow("Delimiter:", delim)
        self._param_widgets["delimiter"] = delim

        idx = QSpinBox()
        idx.setRange(0, 100)
        self._params_layout.addRow("Field Index:", idx)
        self._param_widgets["field_index"] = idx

        target = QLineEdit()
        target.setPlaceholderText("Target variable name")
        self._params_layout.addRow("Store in:", target)
        self._param_widgets["target_var"] = target

    def _build_comment_params(self) -> None:
        text = QLineEdit()
        text.setPlaceholderText("Section label, e.g. 'Login Phase'")
        self._params_layout.addRow("Comment:", text)
        self._param_widgets["text"] = text

    def _build_activate_window_params(self) -> None:
        title = QLineEdit()
        title.setPlaceholderText("Window title (partial match)")
        self._params_layout.addRow("Window Title:", title)
        self._param_widgets["window_title"] = title

        exact = QCheckBox("Exact Match")
        self._params_layout.addRow("", exact)
        self._param_widgets["exact_match"] = exact

    def _build_log_params(self) -> None:
        msg = QLineEdit()
        msg.setPlaceholderText("Message (supports ${var})")
        self._params_layout.addRow("Message:", msg)
        self._param_widgets["message"] = msg

        path = QLineEdit()
        path.setPlaceholderText("macros/macro_log.txt")
        self._params_layout.addRow("Log File:", path)
        self._param_widgets["file_path"] = path

    def _build_read_clipboard_params(self) -> None:
        var_name = QLineEdit()
        var_name.setPlaceholderText("Variable name to store clipboard")
        var_name.setText("clipboard")
        self._params_layout.addRow("Store in:", var_name)
        self._param_widgets["var_name"] = var_name

    def _build_read_file_line_params(self) -> None:
        path = QLineEdit()
        path.setPlaceholderText("Path to file")
        self._params_layout.addRow("File Path:", path)
        self._param_widgets["file_path"] = path

        line = QLineEdit()
        line.setPlaceholderText("Line number (or ${var})")
        line.setText("1")
        self._params_layout.addRow("Line #:", line)
        self._param_widgets["line_number"] = line

        var_name = QLineEdit()
        var_name.setText("line")
        self._params_layout.addRow("Store in:", var_name)
        self._param_widgets["var_name"] = var_name

    def _build_write_file_params(self) -> None:
        path = QLineEdit()
        path.setPlaceholderText("Output file path")
        self._params_layout.addRow("File Path:", path)
        self._param_widgets["file_path"] = path

        text = QLineEdit()
        text.setPlaceholderText("Text to write (supports ${var})")
        self._params_layout.addRow("Text:", text)
        self._param_widgets["text"] = text

        mode = QComboBox()
        mode.addItems(["append", "overwrite"])
        self._params_layout.addRow("Mode:", mode)
        self._param_widgets["mode"] = mode

    def _build_secure_text_params(self) -> None:
        text_edit = QLineEdit()
        text_edit.setPlaceholderText("Enter sensitive text (will be encrypted)")
        text_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._params_layout.addRow("Text:", text_edit)
        self._param_widgets["encrypted_text"] = text_edit

        encrypt_btn = QPushButton("🔒 Encrypt Now")
        encrypt_btn.setToolTip("Encrypt the text using Windows DPAPI")
        def _do_encrypt():
            from core.secure import encrypt
            raw = text_edit.text()
            if raw and not raw.startswith("DPAPI:"):
                text_edit.setText(encrypt(raw))
        encrypt_btn.clicked.connect(_do_encrypt)
        self._params_layout.addRow("", encrypt_btn)

    def _build_run_macro_params(self) -> None:
        path = QLineEdit()
        path.setPlaceholderText("Path to macro .json file")
        self._params_layout.addRow("Macro File:", path)
        self._param_widgets["macro_path"] = path

        browse_btn = QPushButton("📂 Browse...")
        def _browse():
            from PyQt6.QtWidgets import QFileDialog
            fpath, _ = QFileDialog.getOpenFileName(
                self, "Select Macro", "macros",
                "JSON Macros (*.json)")
            if fpath:
                path.setText(fpath)
        browse_btn.clicked.connect(_browse)
        self._params_layout.addRow("", browse_btn)

    def _build_capture_text_params(self) -> None:
        self._add_xy_params()

        w_spin = QSpinBox()
        w_spin.setRange(10, 9999)
        w_spin.setValue(200)
        self._params_layout.addRow("Width:", w_spin)
        self._param_widgets["width"] = w_spin

        h_spin = QSpinBox()
        h_spin.setRange(10, 9999)
        h_spin.setValue(50)
        self._params_layout.addRow("Height:", h_spin)
        self._param_widgets["height"] = h_spin

        var_name = QLineEdit()
        var_name.setText("ocr_text")
        self._params_layout.addRow("Store in:", var_name)
        self._param_widgets["var_name"] = var_name

        lang = QLineEdit()
        lang.setText("eng")
        lang.setPlaceholderText("OCR language (eng, vie, etc.)")
        self._params_layout.addRow("Language:", lang)
        self._param_widgets["lang"] = lang

    def _start_coordinate_picker(self, x_spin: QSpinBox, y_spin: QSpinBox) -> None:
        """Launch coordinate picker overlay after hiding the dialog."""
        self._picker = CoordinatePickerOverlay()
        self._picker_x_target = x_spin
        self._picker_y_target = y_spin
        self._picker.coordinate_picked.connect(self._on_coordinate_picked)
        self._picker.cancelled.connect(self._on_picker_cancelled)
        # Hide both the dialog AND the main window behind it
        self._parent_window = self.parent()
        if self._parent_window:
            self._parent_window.hide()
        self.hide()
        # Short delay so windows fully hide before screenshot
        QTimer.singleShot(300, self._picker.start)

    def _on_coordinate_picked(self, x: int, y: int) -> None:
        """Handle picked coordinates."""
        self._picker_x_target.setValue(x)
        self._picker_y_target.setValue(y)
        if self._parent_window:
            self._parent_window.show()
            self._parent_window.activateWindow()
        self.show()
        self.activateWindow()

    def _on_picker_cancelled(self) -> None:
        """Handle picker cancellation."""
        if self._parent_window:
            self._parent_window.show()
            self._parent_window.activateWindow()
        self.show()
        self.activateWindow()

    def _add_duration_param(self) -> None:
        dur = QDoubleSpinBox()
        dur.setRange(0.0, 10.0)
        dur.setSingleStep(0.1)
        dur.setValue(0.0)
        dur.setSuffix(" s")
        self._params_layout.addRow("Duration:", dur)
        self._param_widgets["duration"] = dur

    def _add_button_param(self) -> None:
        btn = QComboBox()
        btn.addItems(["left", "right", "middle"])
        self._params_layout.addRow("Button:", btn)
        self._param_widgets["button"] = btn

    def _add_image_params(self) -> None:
        img_layout = QHBoxLayout()
        img_edit = QLineEdit()
        img_edit.setPlaceholderText("Path to template image...")
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(lambda: self._browse_image(img_edit))
        capture_btn = QPushButton("📸 Capture")
        capture_btn.setObjectName("primaryButton")
        capture_btn.setToolTip(
            "Chụp vùng màn hình → tự động điền path\n"
            "Kéo vùng chọn, nhấn Escape để hủy."
        )
        capture_btn.clicked.connect(
            lambda: self._start_image_capture(img_edit)
        )
        img_layout.addWidget(img_edit)
        img_layout.addWidget(browse_btn)
        img_layout.addWidget(capture_btn)

        wrapper = QWidget()
        wrapper.setLayout(img_layout)
        self._params_layout.addRow("Image:", wrapper)
        self._param_widgets["image_path"] = img_edit

        conf = QDoubleSpinBox()
        conf.setRange(0.1, 1.0)
        conf.setSingleStep(0.05)
        conf.setValue(0.8)
        self._params_layout.addRow("Confidence:", conf)
        self._param_widgets["confidence"] = conf

    def _browse_image(self, line_edit: QLineEdit) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Image", self._macro_dir,
            "Images (*.png *.jpg *.bmp)")
        if path:
            line_edit.setText(path)

    def _start_image_capture(self, target_edit: QLineEdit) -> None:
        """Launch capture overlay to snip a screen region as template."""
        import os
        assets_dir = os.path.join(self._macro_dir, "assets")
        self._capture_overlay = ImageCaptureOverlay(save_dir=assets_dir)
        self._capture_target_edit = target_edit
        self._capture_overlay.image_captured.connect(self._on_image_captured)
        self._capture_overlay.cancelled.connect(self._on_capture_cancelled)
        # Hide both dialog and main window
        self._capture_parent = self.parent()
        if self._capture_parent:
            self._capture_parent.hide()
        self.hide()
        QTimer.singleShot(300, self._capture_overlay.start)

    def _on_image_captured(self, path: str) -> None:
        """Handle captured image — fill path into target edit."""
        self._capture_target_edit.setText(path)
        if self._capture_parent:
            self._capture_parent.show()
            self._capture_parent.activateWindow()
        self.show()
        self.activateWindow()
        logger.info("Image captured for template: %s", path)

    def _on_capture_cancelled(self) -> None:
        """Restore windows if capture was cancelled."""
        if self._capture_parent:
            self._capture_parent.show()
            self._capture_parent.activateWindow()
        self.show()
        self.activateWindow()

    def _load_action(self, action: Action) -> None:
        """Pre-fill dialog from an existing action."""
        # Select the correct type
        for i in range(self._type_combo.count()):
            if self._type_combo.itemData(i, Qt.ItemDataRole.UserRole) == action.ACTION_TYPE:
                self._type_combo.setCurrentIndex(i)
                break

        # Common settings
        self._delay_spin.setValue(action.delay_after)
        self._repeat_spin.setValue(action.repeat_count)
        self._desc_edit.setText(action.description)
        self._enabled_check.setChecked(action.enabled)
        idx = self._error_combo.findText(action.on_error)
        if idx >= 0:
            self._error_combo.setCurrentIndex(idx)
        else:
            self._error_combo.setEditText(action.on_error)

        # Type-specific params
        params = action._get_params()
        for key, widget in self._param_widgets.items():
            if key == "keys_str" and "keys" in params:
                widget.setText("+".join(params["keys"]))
            elif key in params:
                val = params[key]
                if isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                    widget.setValue(val)
                elif isinstance(widget, QLineEdit):
                    widget.setText(str(val))
                elif isinstance(widget, QComboBox):
                    idx = widget.findText(str(val))
                    if idx >= 0:
                        widget.setCurrentIndex(idx)

    def _on_ok(self) -> None:
        """Build the action from widget values and accept."""
        atype = self._type_combo.currentData(Qt.ItemDataRole.UserRole)
        params = self._collect_params()

        # Create action
        try:
            cls = get_action_class(atype)
            action = cls(**params)
            action.delay_after = self._delay_spin.value()
            action.repeat_count = self._repeat_spin.value()
            action.description = self._desc_edit.text()
            action.enabled = self._enabled_check.isChecked()
            action.on_error = self._error_combo.currentText()

            if not self._validate_image_path(action):
                return

            self._result_action = action
            self.action_ready.emit(action)  # fire BEFORE accept
            self.accept()
            logger.info("Action created: type=%s params=%s", atype, params)
        except Exception as e:
            logger.warning("Action creation failed: type=%s error=%s", atype, e)
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self, "Thông Số Không Hợp Lệ",
                f"Vui lòng kiểm tra lại các thông số đã nhập.\n\n"
                f"Chi tiết: {e}")

    def _collect_params(self) -> dict[str, Any]:
        """Extract parameter values from widgets."""
        params: dict[str, Any] = {}
        for key, widget in self._param_widgets.items():
            if isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                params[key] = widget.value()
            elif isinstance(widget, QLineEdit):
                params[key] = widget.text()
            elif isinstance(widget, QComboBox):
                params[key] = widget.currentText()

        # Handle keys_str → keys list
        if "keys_str" in params:
            params["keys"] = [k.strip() for k in
                              params.pop("keys_str").split("+") if k.strip()]
        return params

    def _validate_image_path(self, action: Action) -> bool:
        """Warn if image path doesn't exist. Returns False to cancel."""
        if not hasattr(action, 'image_path') or not action.image_path:
            return True
        if os.path.isfile(action.image_path):
            return True
        from PyQt6.QtWidgets import QMessageBox
        r = QMessageBox.warning(
            self, "Warning",
            f"Image file not found:\n{action.image_path}\n\nContinue anyway?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        return r == QMessageBox.StandardButton.Yes

    def get_action(self) -> Optional[Action]:
        return self._result_action
