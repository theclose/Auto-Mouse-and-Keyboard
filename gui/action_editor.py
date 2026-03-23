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
    QTextBrowser, QFrame, QSizePolicy,
)
from PyQt6.QtCore import QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QKeySequence, QShortcut

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
# Each entry: meaning + when to use + 3-4 scenario-based examples with explanations
_ACTION_HELP: dict[str, str] = {
    "mouse_click": (
        "<b>🖱 Click — Click chuột trái</b><br><br>"
        "<b>Ý nghĩa:</b> Giả lập 1 lần nhấn chuột trái tại tọa độ (X, Y) cố định, "
        "hoặc tại vị trí ảnh mẫu nếu sử dụng Image Match. Dùng cho mọi thao tác "
        "nhấn nút, chọn item, mở link.<br>"
        "<hr>"
        "<b>📌 Kịch bản 1: Tự động đăng nhập website</b><br>"
        "Bạn muốn click vào ô 'Username' trên trang login.<br>"
        "→ <b>X=500, Y=300</b> (tọa độ ô input trên màn hình)<br>"
        "→ <b>Duration=0.1s</b> (click nhanh, không cần giữ)<br>"
        "<i>Giải thích:</i> Dùng tọa độ cố định khi vị trí ô input không thay đổi "
        "(cửa sổ trình duyệt luôn maximize).<br><br>"
        "<b>📌 Kịch bản 2: Click nút 'Gửi' trong phần mềm kế toán</b><br>"
        "Nút 'Gửi' có thể ở vị trí khác tùy kích thước cửa sổ.<br>"
        "→ Chọn <b>Image Match</b>: chụp ảnh nút 'Gửi' làm mẫu<br>"
        "→ AutoMacro tự tìm nút trên màn hình → click vào giữa<br>"
        "<i>Giải thích:</i> Image Match an toàn hơn tọa độ khi cửa sổ hay thay đổi kích thước.<br><br>"
        "<b>📌 Kịch bản 3: Click hàng loạt checkbox trong danh sách</b><br>"
        "Bạn cần tick 20 checkbox liên tiếp, mỗi cái cách nhau 30px.<br>"
        "→ <b>X=120, Y=200</b> (checkbox đầu tiên)<br>"
        "→ Kết hợp <b>Loop Block</b>: lặp 20 lần, mỗi lần <b>Y += 30</b><br>"
        "<i>Giải thích:</i> Dùng biến Set Variable để tăng Y mỗi vòng lặp."
    ),
    "mouse_double_click": (
        "<b>🖱 Double Click — Nhấp đúp chuột</b><br><br>"
        "<b>Ý nghĩa:</b> Nhấp đúp chuột trái (2 click nhanh liên tiếp). "
        "Hệ điều hành xử lý double-click khác single-click — dùng để mở file, "
        "chọn từ trong văn bản, kích hoạt item.<br>"
        "<hr>"
        "<b>📌 Kịch bản 1: Tự động mở file báo cáo Excel hàng ngày</b><br>"
        "Mỗi sáng cần mở file 'BaoCao.xlsx' trên Desktop.<br>"
        "→ <b>X=200, Y=350</b> (vị trí file icon trên Desktop)<br>"
        "<i>Giải thích:</i> Một click chỉ chọn file, double-click mới mở. "
        "Nếu dùng single click → file chỉ được highlight, không mở.<br><br>"
        "<b>📌 Kịch bản 2: Chọn 1 từ trong email để copy</b><br>"
        "Cần chọn từ 'Approved' trong email để kiểm tra trạng thái.<br>"
        "→ Double-click tại vị trí từ → từ được bôi đen<br>"
        "→ Sau đó: Key Combo 'ctrl+c' → Read Clipboard<br>"
        "<i>Giải thích:</i> Double-click trong text editor/browser sẽ tự động chọn cả từ.<br><br>"
        "<b>📌 Kịch bản 3: Kích hoạt ô nhập liệu trong bảng</b><br>"
        "Trong Excel/Google Sheets, single-click chọn cell, double-click mới vào chế độ edit.<br>"
        "→ Double-click cell đích → sau đó Type Text để nhập giá trị"
    ),
    "mouse_right_click": (
        "<b>🖱 Right Click — Click chuột phải</b><br><br>"
        "<b>Ý nghĩa:</b> Mở context menu (menu chuột phải) tại vị trí chỉ định. "
        "Menu sẽ hiện các tùy chọn tùy thuộc vào ứng dụng đang focus.<br>"
        "<hr>"
        "<b>📌 Kịch bản 1: Xóa file tự động</b><br>"
        "Cần xóa file rác trong thư mục Downloads mỗi tuần.<br>"
        "→ Right-click file → chờ menu hiện (Delay 300ms)<br>"
        "→ Key Press 'D' (phím tắt Delete trong context menu)<br>"
        "<i>Giải thích:</i> Sau right-click cần delay nhỏ để menu hiện ra trước khi nhấn phím.<br><br>"
        "<b>📌 Kịch bản 2: Copy đường dẫn ảnh trên web</b><br>"
        "→ Right-click ảnh → click 'Copy image address'<br>"
        "→ Read Clipboard → Write to File (lưu URL)<br>"
        "<i>Giải thích:</i> Context menu trình duyệt có option copy URL mà Ctrl+C không làm được."
    ),
    "mouse_move": (
        "<b>🖱 Move — Di chuyển chuột</b><br><br>"
        "<b>Ý nghĩa:</b> Di chuyển con trỏ chuột đến vị trí (X, Y) mà không click. "
        "Dùng khi cần hover để kích hoạt tooltip, submenu, hoặc chuẩn bị cho thao tác tiếp.<br>"
        "<hr>"
        "<b>📌 Kịch bản 1: Mở submenu của thanh menu</b><br>"
        "Trong Excel, hover vào 'Format' → submenu hiện ra.<br>"
        "→ Move đến 'Format' (X=200, Y=30) → Delay 500ms → Click submenu item<br>"
        "<i>Giải thích:</i> Nếu click thẳng vào submenu item mà chưa hover parent → menu chưa hiện."
    ),
    "mouse_drag": (
        "<b>🖱 Drag — Kéo thả chuột</b><br><br>"
        "<b>Ý nghĩa:</b> Nhấn giữ chuột trái tại vị trí hiện tại, "
        "kéo đến tọa độ đích (X, Y), rồi thả. Mô phỏng thao tác drag-and-drop.<br>"
        "<hr>"
        "<b>📌 Kịch bản 1: Kéo file vào ứng dụng</b><br>"
        "Kéo file ảnh từ Desktop vào cửa sổ Photoshop.<br>"
        "→ Mouse Move đến file icon → Drag đến vùng canvas (X=800, Y=400)<br>"
        "→ Duration=0.5s (kéo chậm để app kịp phản hồi)<br>"
        "<i>Giải thích:</i> Duration quá nhanh (<0.1s) có thể khiến app không nhận drag.<br><br>"
        "<b>📌 Kịch bản 2: Chọn vùng text bằng kéo chuột</b><br>"
        "→ Move đến đầu dòng 1 → Drag đến cuối dòng 3 → Ctrl+C<br>"
        "<i>Giải thích:</i> Khác Ctrl+A (chọn tất cả), drag cho phép chọn chính xác vùng muốn."
    ),
    "mouse_scroll": (
        "<b>🖱 Scroll — Cuộn chuột</b><br><br>"
        "<b>Ý nghĩa:</b> Cuộn chuột lên/xuống. Clicks dương = cuộn lên, âm = cuộn xuống.<br>"
        "<hr>"
        "<b>📌 Kịch bản 1: Cuộn xuống cuối trang web để chụp ảnh</b><br>"
        "→ Loop: Scroll Clicks=-5 → Delay 1s → Take Screenshot → lặp lại<br>"
        "<i>Giải thích:</i> Clicks=-5 cuộn xuống khoảng 5 dòng. Delay cho trang load lazy content."
    ),
    "key_press": (
        "<b>⌨ Key Press — Nhấn 1 phím</b><br><br>"
        "<b>Ý nghĩa:</b> Nhấn và thả 1 phím đơn: chữ cái, số, hoặc phím đặc biệt "
        "(Enter, Tab, Escape, F1-F12, Home, End, Delete...).<br>"
        "<hr>"
        "<b>📌 Kịch bản 1: Xác nhận form sau khi điền xong</b><br>"
        "→ Key = <b>'enter'</b><br>"
        "<i>Giải thích:</i> Nhiều form web chấp nhận Enter để submit, nhanh hơn click nút Submit.<br><br>"
        "<b>📌 Kịch bản 2: Di chuyển giữa các ô trong bảng tính</b><br>"
        "Điền 10 ô liên tiếp: nhập giá trị → Tab → nhập → Tab...<br>"
        "→ Loop: Type Text '{giá_trị}' → Key Press <b>'tab'</b> → lặp<br>"
        "<i>Giải thích:</i> Tab = sang phải, Enter = xuống dưới.<br><br>"
        "<b>📌 Kịch bản 3: Đóng popup phiền toái tự động</b><br>"
        "→ Wait for Image (ảnh popup) → Key Press <b>'esc'</b><br>"
        "<i>Giải thích:</i> Hầu hết dialog/popup đều đóng khi nhấn Escape."
    ),
    "key_combo": (
        "<b>⌨ Key Combo — Tổ hợp phím</b><br><br>"
        "<b>Ý nghĩa:</b> Nhấn đồng thời modifier (Ctrl/Alt/Shift/Win) + phím khác. "
        "Đây là cách gọi shortcut ứng dụng — nhanh hơn click menu.<br>"
        "<hr>"
        "<b>📌 Kịch bản 1: Copy dữ liệu từ app A sang app B</b><br>"
        "→ Ctrl+A (chọn tất cả) → Ctrl+C → Activate Window 'App B' → Ctrl+V<br>"
        "<i>Giải thích:</i> Key Combo đảm bảo 2 phím nhấn đồng thời. Nếu dùng 2 Key Press riêng → sẽ nhấn tuần tự, không phải combo.<br><br>"
        "<b>📌 Kịch bản 2: Auto-save mỗi 5 phút</b><br>"
        "→ Loop: Delay 300000ms → Key Combo <b>'ctrl+s'</b><br>"
        "<i>Giải thích:</i> Ctrl+S hoạt động trong hầu hết mọi app.<br><br>"
        "<b>📌 Kịch bản 3: Undo 5 bước</b><br>"
        "→ Loop 5: Key Combo <b>'ctrl+z'</b> → Delay 200ms<br>"
        "<i>Giải thích:</i> Delay giữa các Undo để app kịp xử lý mỗi bước."
    ),
    "type_text": (
        "<b>⌨ Type Text — Gõ văn bản</b><br><br>"
        "<b>Ý nghĩa:</b> Gõ chuỗi ký tự vào ô đang focus, từng ký tự một. "
        "Hỗ trợ chữ có dấu tiếng Việt.<br>"
        "<hr>"
        "<b>📌 Kịch bản 1: Tự động điền 50 email từ file</b><br>"
        "File 'emails.txt', mỗi dòng 1 email.<br>"
        "→ Loop 50: Read File Line → Type Text '{email}' → Tab → lặp<br>"
        "<i>Giải thích:</i> Biến {email} sẽ được thay bằng giá trị đọc từ file.<br><br>"
        "<b>📌 Kịch bản 2: Nhập công thức Excel</b><br>"
        "→ Click cell A1 → Type Text '=SUM(B1:B10)' → Enter<br>"
        "<i>Giải thích:</i> Type Text gõ chính xác từng ký tự, kể cả '=' để Excel nhận diện công thức.<br><br>"
        "<b>📌 Kịch bản 3: Điền form đăng ký</b><br>"
        "→ Click ô Họ tên → Type Text 'Nguyễn Văn A' → Tab → Type Text '0912345678' → Tab → Type Text 'email@gmail.com' → Enter"
    ),
    "hotkey": (
        "<b>⌨ Hotkey — Tổ hợp 3+ phím</b><br><br>"
        "<b>Ý nghĩa:</b> Tương tự Key Combo nhưng hỗ trợ 3 phím trở lên (ví dụ: Ctrl+Shift+S).<br>"
        "<hr>"
        "<b>📌 Kịch bản 1: Mở Task Manager khi app bị đơ</b><br>"
        "→ Hotkey <b>'ctrl+shift+esc'</b><br>"
        "<i>Giải thích:</i> Phím tắt mở trực tiếp Task Manager, không cần qua Ctrl+Alt+Del.<br><br>"
        "<b>📌 Kịch bản 2: Save As file với tên mới</b><br>"
        "→ Hotkey <b>'ctrl+shift+s'</b> → Type Text tên mới → Enter<br>"
        "<i>Giải thích:</i> Ctrl+S lưu đè, Ctrl+Shift+S mở 'Save As' để lưu file mới."
    ),
    "wait_for_image": (
        "<b>🖼 Wait for Image — Đợi ảnh xuất hiện</b><br><br>"
        "<b>Ý nghĩa:</b> Tạm dừng macro và liên tục quét màn hình cho đến khi tìm thấy ảnh mẫu "
        "hoặc hết timeout. Đây là cách <b>đồng bộ hóa</b> macro với ứng dụng.<br>"
        "<hr>"
        "<b>📌 Kịch bản 1: Đợi trang web load xong sau khi đăng nhập</b><br>"
        "Sau khi nhấn 'Login', trang cần 2-10s load tùy mạng.<br>"
        "→ Ảnh mẫu = <b>logo trang dashboard</b>, Timeout = <b>30s</b><br>"
        "<i>Giải thích:</i> Nếu dùng Delay cố định (5s), mạng chậm → macro click trang chưa load. "
        "Wait for Image tự adjust: mạng nhanh → chuyển ngay, mạng chậm → đợi thêm.<br><br>"
        "<b>📌 Kịch bản 2: Đợi file download xong</b><br>"
        "→ Ảnh mẫu = <b>'Download complete'</b>, Timeout = <b>120s</b><br>"
        "<i>Giải thích:</i> Dùng Timeout lớn cho file lớn. Nếu quá timeout → on_error xử lý."
    ),
    "click_on_image": (
        "<b>🖼 Click on Image — Tìm ảnh rồi click</b><br><br>"
        "<b>Ý nghĩa:</b> Quét toàn bộ màn hình tìm ảnh mẫu, rồi click vào giữa vùng tìm thấy. "
        "Giải quyết vấn đề nút ở vị trí thay đổi.<br>"
        "<hr>"
        "<b>📌 Kịch bản 1: Auto-click nút 'OK' trong mọi popup</b><br>"
        "Nút OK nằm ở vị trí khác nhau mỗi lần popup hiện.<br>"
        "→ Ảnh mẫu = <b>ảnh nút OK</b>, Confidence = <b>0.8</b><br>"
        "<i>Giải thích:</i> Confidence 0.8 = chấp nhận khớp 80%. "
        "Thấp quá (0.5) → click nhầm. Cao quá (0.99) → không tìm thấy khi font hơi khác.<br><br>"
        "<b>📌 Kịch bản 2: Click icon trong System Tray</b><br>"
        "Icon system tray rất nhỏ (16×16px), tọa độ thay đổi tùy số app chạy.<br>"
        "→ Ảnh mẫu = ảnh icon app (chụp từ tray)<br>"
        "<i>Giải thích:</i> Tọa độ cố định sẽ sai khi có app khác mở/đóng."
    ),
    "image_exists": (
        "<b>🖼 Image Exists — Kiểm tra ảnh tồn tại</b><br><br>"
        "<b>Ý nghĩa:</b> Check 1 lần duy nhất xem ảnh mẫu có trên màn hình không (True/False). "
        "Khác Wait for Image: không đợi, chỉ check ngay lúc đó.<br>"
        "<hr>"
        "<b>📌 Kịch bản: Kiểm tra đã login chưa trước khi làm việc</b><br>"
        "→ Image Exists: ảnh = <b>avatar user</b><br>"
        "→ Nếu có → tiếp tục. Nếu không → run macro 'login.json'<br>"
        "<i>Giải thích:</i> Kết hợp với If Image Found để rẽ nhánh tự động."
    ),
    "take_screenshot": (
        "<b>🖼 Take Screenshot — Chụp màn hình</b><br><br>"
        "<b>Ý nghĩa:</b> Chụp toàn bộ màn hình lưu thành file .png. File đặt tên theo timestamp.<br>"
        "<hr>"
        "<b>📌 Kịch bản: Chụp xác nhận sau mỗi đơn hàng</b><br>"
        "Macro xử lý 50 đơn hàng, mỗi đơn cần chụp ảnh xác nhận.<br>"
        "→ Loop 50: xử lý đơn → <b>Take Screenshot</b> → lặp<br>"
        "<i>Giải thích:</i> File ảnh tự đặt tên theo timestamp → không bao giờ ghi đè."
    ),
    "check_pixel_color": (
        "<b>🎨 Check Pixel Color — Kiểm tra màu pixel</b><br><br>"
        "<b>Ý nghĩa:</b> Lấy màu RGB tại tọa độ (X, Y) và so sánh. "
        "<b>Nhanh gấp 100x</b> so với Image Match — chỉ kiểm tra 1 điểm.<br>"
        "<hr>"
        "<b>📌 Kịch bản: Kiểm tra nút Submit có active không</b><br>"
        "Nút active = xanh #4CAF50, disabled = xám #999.<br>"
        "→ Check pixel giữa nút (X=400, Y=500)<br>"
        "→ Xanh → click. Xám → đợi thêm<br>"
        "<i>Giải thích:</i> Nhanh hơn nhiều so với Image Match vì chỉ 1 pixel."
    ),
    "wait_for_color": (
        "<b>🎨 Wait for Color — Đợi pixel đổi màu</b><br><br>"
        "<b>Ý nghĩa:</b> Liên tục check pixel tại (X, Y) cho đến khi đúng màu hoặc hết timeout.<br>"
        "<hr>"
        "<b>📌 Kịch bản: Đợi progress bar đầy rồi tiếp tục</b><br>"
        "Thanh loading khi full = xanh #00FF00.<br>"
        "→ Tọa độ = cuối thanh (X=700, Y=580), Màu = #00FF00, Timeout = 60s<br>"
        "<i>Giải thích:</i> Check pixel cuối thanh: khi chuyển xanh → thanh đã full."
    ),
    "delay": (
        "<b>⏱ Delay — Tạm dừng</b><br><br>"
        "<b>Ý nghĩa:</b> Dừng macro trong thời gian chỉ định (millisecond). 1000ms = 1 giây.<br>"
        "<hr>"
        "<b>📌 Kịch bản 1: Đợi animation menu rồi mới click</b><br>"
        "Menu dropdown có animation 300ms.<br>"
        "→ Click menu → <b>Delay 500ms</b> → Click item<br>"
        "<i>Giải thích:</i> 500ms > 300ms animation → menu chắc chắn đã hiện hết.<br><br>"
        "<b>📌 Kịch bản 2: Chống rate-limit khi gửi email hàng loạt</b><br>"
        "→ Loop: soạn email → gửi → <b>Delay 3000ms</b> → lặp<br>"
        "<i>Giải thích:</i> 3s giữa các email ≈ 20 email/phút, an toàn cho hầu hết hệ thống.<br><br>"
        "<b>💡 Tip:</b> Nếu không biết trước thời gian cần chờ, dùng <b>Wait for Image</b> thay vì Delay cố định — linh hoạt hơn."
    ),
    "loop_block": (
        "<b>🔁 Loop Block — Vòng lặp</b><br><br>"
        "<b>Ý nghĩa:</b> Lặp lại nhóm action N lần hoặc vô hạn. "
        "Nền tảng cho mọi xử lý hàng loạt (batch).<br>"
        "<hr>"
        "<b>📌 Kịch bản 1: Gửi 100 email từ danh sách</b><br>"
        "→ Loop 100: Read File Line → Click 'To:' → Type Text '{email}' → soạn → Gửi → Delay 3s<br>"
        "<i>Giải thích:</i> Mỗi vòng Read File Line tự động đọc dòng tiếp theo."
    ),
    "if_image_found": (
        "<b>🔀 If Image Found — Rẽ nhánh theo ảnh</b><br><br>"
        "<b>Ý nghĩa:</b> Kiểm tra ảnh có trên màn hình → thực hiện hành động khác nhau. "
        "Đây là <b>logic điều kiện</b> quan trọng nhất.<br>"
        "<hr>"
        "<b>📌 Kịch bản 1: Tự động xử lý popup bất ngờ</b><br>"
        "Macro chạy, popup 'Are you sure?' bất ngờ hiện.<br>"
        "→ If Image Found: ảnh nút 'Yes'<br>"
        "→ Có → Click on Image 'Yes'. Không → bỏ qua, tiếp tục<br>"
        "<i>Giải thích:</i> Đặt trong loop → tự xử lý popup bất cứ lúc nào hiện ra.<br><br>"
        "<b>📌 Kịch bản 2: Kiểm tra login thành công</b><br>"
        "→ If Image Found: ảnh 'Dashboard'<br>"
        "→ Có → tiếp. Không → Take Screenshot lỗi → dừng"
    ),
    "if_pixel_color": (
        "<b>🔀 If Pixel Color — Rẽ nhánh theo màu</b><br><br>"
        "<b>Ý nghĩa:</b> Kiểm tra màu pixel → rẽ nhánh. Nhanh gấp 100x so với If Image.<br>"
        "<hr>"
        "<b>📌 Kịch bản: Kiểm tra HP trong game</b><br>"
        "HP bar: đỏ = full, đen = hết.<br>"
        "→ Check pixel giữa HP bar<br>"
        "→ Đỏ → tiếp tục attack. Đen → dùng potion heal<br>"
        "<i>Giải thích:</i> Check pixel mỗi 100ms — rất nhanh, phù hợp game loop."
    ),
    "if_variable": (
        "<b>🔀 If Variable — Rẽ nhánh theo biến</b><br><br>"
        "<b>Ý nghĩa:</b> So sánh giá trị biến (==, !=, >, <, contains).<br>"
        "<hr>"
        "<b>📌 Kịch bản 1: Dừng sau N lần lặp</b><br>"
        "→ Set Variable 'count' = '{count} + 1'<br>"
        "→ If Variable: count > 50 → Dừng macro<br>"
        "<i>Giải thích:</i> Kiểm soát chính xác hơn Loop Block thông thường.<br><br>"
        "<b>📌 Kịch bản 2: Kiểm tra kết quả OCR</b><br>"
        "→ Capture Text → biến 'result'<br>"
        "→ If Variable: result contains 'thành công' → tiếp. Không → Log lỗi<br>"
        "<i>Giải thích:</i> Dùng 'contains' thay '==' vì OCR có thể trả thêm khoảng trắng thừa."
    ),
    "set_variable": (
        "<b>📊 Set Variable — Gán giá trị biến</b><br><br>"
        "<b>Ý nghĩa:</b> Tạo hoặc cập nhật biến. Hỗ trợ số, chuỗi, và tham chiếu {tên_biến}.<br>"
        "<hr>"
        "<b>📌 Kịch bản 1: Tạo bộ đếm</b><br>"
        "→ Set Variable: Name = 'counter', Value = '0' (trước loop)<br>"
        "→ Trong loop: Value = '{counter} + 1'<br>"
        "<i>Giải thích:</i> {counter} thay bằng giá trị hiện tại, +1 → tự tăng mỗi vòng.<br><br>"
        "<b>📌 Kịch bản 2: Tên file động</b><br>"
        "→ Value = 'report_{counter}.pdf'<br>"
        "<i>Giải thích:</i> Mỗi vòng tạo tên file khác: report_1.pdf, report_2.pdf..."
    ),
    "split_string": (
        "<b>📊 Split String — Tách chuỗi</b><br><br>"
        "<b>Ý nghĩa:</b> Tách chuỗi theo ký tự phân cách, lấy phần tử theo index (0 = đầu, -1 = cuối).<br>"
        "<hr>"
        "<b>📌 Kịch bản: Xử lý file CSV</b><br>"
        "Dòng CSV: 'Nguyễn Văn A,email@gmail.com,0912345678'<br>"
        "→ Split: Separator = ',' → Index 0 = tên, Index 1 = email, Index 2 = SĐT<br>"
        "<i>Giải thích:</i> Sau Split, mỗi phần tử lưu vào biến riêng → Type Text từng ô."
    ),
    "comment": (
        "<b>📝 Comment — Ghi chú</b><br><br>"
        "<b>Ý nghĩa:</b> Nhãn ghi chú không thực thi. Engine bỏ qua hoàn toàn khi chạy.<br>"
        "<hr>"
        "<b>📌 Kịch bản: Đánh dấu phần trong macro dài</b><br>"
        "Macro 50 action khó theo dõi → thêm Comment phân section:<br>"
        "→ <b>'=== PHẦN 1: ĐĂNG NHẬP ==='</b><br>"
        "→ <b>'⚠ LƯU Ý: Server chậm, cần đợi 5s'</b><br>"
        "<i>Giải thích:</i> Giúp macro 'self-documenting' — đọc lại sau 1 tháng vẫn hiểu."
    ),
    "activate_window": (
        "<b>🖥 Activate Window — Chuyển cửa sổ</b><br><br>"
        "<b>Ý nghĩa:</b> Tìm cửa sổ theo tiêu đề (hoặc 1 phần) và đưa lên foreground.<br>"
        "<hr>"
        "<b>📌 Kịch bản: Macro thao tác giữa Chrome và Excel</b><br>"
        "→ Activate Window <b>'Chrome'</b> → copy dữ liệu<br>"
        "→ Activate Window <b>'BaoCao.xlsx'</b> → paste vào Excel<br>"
        "<i>Giải thích:</i> Chỉ cần 1 phần tiêu đề: 'Chrome' sẽ match 'Báo cáo - Google Chrome'."
    ),
    "log_to_file": (
        "<b>📝 Log to File — Ghi log</b><br><br>"
        "<b>Ý nghĩa:</b> Nối (append) 1 dòng text vào file log. Hỗ trợ biến {counter}, {timestamp}.<br>"
        "<hr>"
        "<b>📌 Kịch bản: Ghi nhật ký chạy macro</b><br>"
        "→ Mỗi vòng: Log to File <b>'Vòng {counter}: xử lý {email} — OK'</b><br>"
        "<i>Giải thích:</i> Sau khi chạy xong, mở file log → biết rõ đã xử lý bao nhiêu item."
    ),
    "read_clipboard": (
        "<b>📋 Read Clipboard — Đọc clipboard</b><br><br>"
        "<b>Ý nghĩa:</b> Lấy text trong clipboard (sau Ctrl+C) vào biến để xử lý tiếp.<br>"
        "<hr>"
        "<b>📌 Kịch bản: Lấy URL từ thanh địa chỉ trình duyệt</b><br>"
        "→ Click thanh địa chỉ → Ctrl+A → Ctrl+C<br>"
        "→ <b>Read Clipboard</b> → biến 'url' → Write to File<br>"
        "<i>Giải thích:</i> Ctrl+C copy vào clipboard, Read Clipboard lấy ra để macro sử dụng."
    ),
    "read_file_line": (
        "<b>📄 Read File Line — Đọc dòng từ file</b><br><br>"
        "<b>Ý nghĩa:</b> Đọc dòng thứ N từ file text vào biến. "
        "Trong loop, tự động đọc dòng tiếp theo mỗi vòng.<br>"
        "<hr>"
        "<b>📌 Kịch bản: Nhập 100 tài khoản từ file</b><br>"
        "File 'accounts.txt' mỗi dòng: username,password<br>"
        "→ Loop 100: Read File Line → Split ',' → Type Text user → Tab → Secure Type pass → Enter<br>"
        "<i>Giải thích:</i> Kết hợp Read File Line + Split String = đọc CSV cơ bản."
    ),
    "write_to_file": (
        "<b>📄 Write to File — Ghi vào file</b><br><br>"
        "<b>Ý nghĩa:</b> Ghi text vào file (tạo mới hoặc nối thêm). Hỗ trợ biến.<br>"
        "<hr>"
        "<b>📌 Kịch bản: Xuất kết quả ra CSV</b><br>"
        "→ File = 'result.csv', Text = '{name},{email},{phone}'<br>"
        "→ Mode = Append (nối thêm, không ghi đè)<br>"
        "<i>Giải thích:</i> Chế độ Append thêm dòng mới mỗi lần → tạo file CSV nhiều dòng."
    ),
    "secure_type_text": (
        "<b>🔒 Secure Type Text — Gõ bảo mật</b><br><br>"
        "<b>Ý nghĩa:</b> Gõ text nhưng <b>không hiển thị</b> trong log/preview. Chỉ hiện '****'.<br>"
        "<hr>"
        "<b>📌 Kịch bản: Tự động đăng nhập hệ thống</b><br>"
        "→ Click ô Password → <b>Secure Type Text</b> 'P@ssw0rd!'<br>"
        "→ Trong log chỉ hiện: 'type_text: ****'<br>"
        "<i>Giải thích:</i> Type Text thường → password hiện rõ trong log → rủi ro bảo mật."
    ),
    "run_macro": (
        "<b>📦 Run Sub-Macro — Chạy macro con</b><br><br>"
        "<b>Ý nghĩa:</b> Chạy file macro khác (.json) như subroutine. Xong → quay lại macro chính.<br>"
        "<hr>"
        "<b>📌 Kịch bản: Tái sử dụng flow đăng nhập</b><br>"
        "Nhiều macro đều cần login → tạo 'login.json' riêng.<br>"
        "→ Macro A: <b>Run 'login.json'</b> → xử lý A<br>"
        "→ Macro B: <b>Run 'login.json'</b> → xử lý B<br>"
        "<i>Giải thích:</i> Thay đổi flow login → chỉ sửa 1 file thay vì sửa tất cả macro."
    ),
    "capture_text": (
        "<b>🔎 Capture Text (OCR) — Nhận dạng chữ</b><br><br>"
        "<b>Ý nghĩa:</b> Chụp vùng màn hình, nhận dạng text bằng Tesseract OCR, lưu vào biến. "
        "Cho phép macro 'đọc' text trên UI.<br>"
        "<hr>"
        "<b>📌 Kịch bản 1: Đọc số dư tài khoản ngân hàng</b><br>"
        "→ Vùng chụp = khu vực hiển thị số dư (X1=300, Y1=200, X2=500, Y2=230)<br>"
        "→ Biến = 'balance' → Log to File 'Số dư: {balance}'<br>"
        "<i>Giải thích:</i> OCR chuyển ảnh text thành chuỗi ký tự macro có thể xử lý.<br><br>"
        "<b>📌 Kịch bản 2: Đọc mã đơn hàng từ popup</b><br>"
        "→ Capture Text vùng mã đơn → biến 'order_id' → Write to File<br>"
        "<i>Giải thích:</i> Dùng khi UI không cho Ctrl+C (text trong ảnh, canvas, PDF viewer)."
    ),
}

class _HelpPopup(QFrame):
    """Persistent help popup with close button and Escape key support."""

    def __init__(self, html: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(
            "_HelpPopup { background: #1e1e2e; border: 1px solid #6c6cff; "
            "border-radius: 8px; }"
        )
        self.setFixedWidth(420)
        self.setMinimumHeight(200)
        self.setMaximumHeight(450)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 8)
        layout.setSpacing(4)

        # Header row: title + close button
        header = QHBoxLayout()
        title = QLabel("📖 Hướng dẫn")
        title.setStyleSheet("font-weight: bold; font-size: 13px; color: #e0e0ff;")
        header.addWidget(title)
        header.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(24, 24)
        close_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #aaa; "
            "border: none; font-size: 16px; font-weight: bold; } "
            "QPushButton:hover { color: #ff6b6b; }"
        )
        close_btn.setToolTip("Đóng (Esc)")
        close_btn.clicked.connect(self.close)
        header.addWidget(close_btn)
        layout.addLayout(header)

        # Content browser
        browser = QTextBrowser()
        browser.setHtml(f"<div style='color:#ccc; font-size:12px; "
                        f"line-height:1.5'>{html}</div>")
        browser.setOpenExternalLinks(False)
        browser.setStyleSheet(
            "QTextBrowser { background: transparent; border: none; "
            "color: #ccc; }"
        )
        browser.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(browser)

        # Escape key shortcut
        esc = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        esc.activated.connect(self.close)

    def keyPressEvent(self, event: Any) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)


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
        """Show persistent help popup for the selected action type."""
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
        # Close previous popup if open
        if hasattr(self, '_help_popup') and self._help_popup is not None:
            self._help_popup.close()
        self._help_popup = _HelpPopup(html, parent=self)
        # Position below the help button (global coords since popup is a window)
        btn_pos = self._help_btn.mapToGlobal(
            self._help_btn.rect().bottomRight())
        self._help_popup.move(btn_pos.x() - 420, btn_pos.y() + 4)
        self._help_popup.show()
        self._help_popup.setFocus()

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
