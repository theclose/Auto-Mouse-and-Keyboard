"""
Macro Templates — pre-built macro snippets for common automation tasks.
"""

import json
import logging
from typing import Any

from core.action import Action, get_action_class

logger = logging.getLogger(__name__)

# Built-in templates
BUILTIN_TEMPLATES: list[dict[str, Any]] = [
    {
        "name": "📋 Form Filling — Điền form",
        "description": "Click vào ô → gõ text → Tab → lặp lại",
        "actions": [
            {
                "type": "mouse_click",
                "x": 300,
                "y": 200,
                "delay_after": 200,
                "description": "Click vào ô input đầu tiên",
            },
            {"type": "type_text", "text": "Giá trị 1", "delay_after": 100, "description": "Gõ giá trị"},
            {"type": "key_press", "key": "tab", "delay_after": 100, "description": "Tab sang ô tiếp theo"},
            {"type": "type_text", "text": "Giá trị 2", "delay_after": 100, "description": "Gõ giá trị tiếp"},
            {"type": "key_press", "key": "enter", "delay_after": 300, "description": "Submit form"},
        ],
    },
    {
        "name": "🔍 Image Search Loop — Tìm ảnh",
        "description": "Lặp chờ ảnh xuất hiện rồi click vào",
        "actions": [
            {
                "type": "set_variable",
                "var_name": "found",
                "value": "0",
                "operation": "set",
                "delay_after": 0,
                "description": "Khởi tạo biến",
            },
            {
                "type": "wait_for_image",
                "template_path": "",
                "timeout_ms": 10000,
                "delay_after": 500,
                "description": "Đợi ảnh mẫu xuất hiện",
            },
            {
                "type": "click_on_image",
                "template_path": "",
                "delay_after": 300,
                "description": "Click vào ảnh tìm thấy",
            },
        ],
    },
    {
        "name": "🔐 Login Flow — Đăng nhập",
        "description": "Mở app → click username → gõ → click pass → gõ → login",
        "actions": [
            {"type": "activate_window", "title": "Login", "delay_after": 500, "description": "Kích hoạt cửa sổ Login"},
            {"type": "mouse_click", "x": 400, "y": 300, "delay_after": 200, "description": "Click vào ô Username"},
            {"type": "type_text", "text": "admin", "delay_after": 100, "description": "Gõ username"},
            {"type": "key_press", "key": "tab", "delay_after": 100, "description": "Tab sang Password"},
            {"type": "type_text", "text": "password", "delay_after": 100, "description": "Gõ password"},
            {"type": "key_press", "key": "enter", "delay_after": 500, "description": "Nhấn Enter để đăng nhập"},
        ],
    },
    {
        "name": "📸 Screenshot Timer — Chụp định kỳ",
        "description": "Chụp ảnh màn hình mỗi N giây",
        "actions": [
            {
                "type": "set_variable",
                "var_name": "count",
                "value": "0",
                "operation": "set",
                "delay_after": 0,
                "description": "Bộ đếm",
            },
            {
                "type": "take_screenshot",
                "save_path": "screenshots/shot_${count}.png",
                "delay_after": 100,
                "description": "Chụp màn hình",
            },
            {
                "type": "set_variable",
                "var_name": "count",
                "value": "1",
                "operation": "increment",
                "delay_after": 0,
                "description": "Tăng bộ đếm",
            },
            {"type": "delay", "duration_ms": 5000, "delay_after": 0, "description": "Đợi 5 giây"},
        ],
    },
    {
        "name": "📊 CSV Processing — Xử lý CSV",
        "description": "Đọc file → tách chuỗi → xử lý → ghi kết quả",
        "actions": [
            {
                "type": "set_variable",
                "var_name": "line_num",
                "value": "0",
                "operation": "set",
                "delay_after": 0,
                "description": "Bắt đầu từ dòng 0",
            },
            {
                "type": "read_file_line",
                "file_path": "data.csv",
                "line_index_var": "line_num",
                "target_var": "line",
                "delay_after": 0,
                "description": "Đọc 1 dòng CSV",
            },
            {
                "type": "split_string",
                "source_var": "line",
                "delimiter": ",",
                "field_index": 0,
                "target_var": "col1",
                "delay_after": 0,
                "description": "Lấy cột đầu tiên",
            },
            {
                "type": "log_to_file",
                "file_path": "output.txt",
                "text": "${col1}",
                "delay_after": 0,
                "description": "Ghi kết quả",
            },
            {
                "type": "set_variable",
                "var_name": "line_num",
                "value": "1",
                "operation": "increment",
                "delay_after": 0,
                "description": "Chuyển sang dòng tiếp",
            },
        ],
    },
    {
        "name": "🔁 Retry Pattern — Thử lại khi fail",
        "description": "Thử thao tác N lần, thoát khi thành công",
        "actions": [
            {
                "type": "set_variable",
                "var_name": "max_retries",
                "value": "3",
                "operation": "set",
                "delay_after": 0,
                "description": "Số lần thử tối đa",
            },
            {
                "type": "set_variable",
                "var_name": "attempt",
                "value": "0",
                "operation": "set",
                "delay_after": 0,
                "description": "Bộ đếm lần thử",
            },
            {
                "type": "set_variable",
                "var_name": "attempt",
                "value": "1",
                "operation": "increment",
                "delay_after": 0,
                "description": "Tăng lần thử",
            },
            {"type": "comment", "text": "Thêm action cần retry ở đây", "delay_after": 0, "description": "Placeholder"},
            {"type": "delay", "duration_ms": 1000, "delay_after": 0, "description": "Đợi trước khi thử lại"},
        ],
    },
    {
        "name": "🖱 Auto Clicker — Click tự động",
        "description": "Click vị trí cố định N lần với delay giữa mỗi click",
        "actions": [
            {"type": "mouse_click", "x": 500, "y": 400, "delay_after": 500, "description": "Click vị trí mục tiêu"},
            {"type": "delay", "duration_ms": 200, "delay_after": 0, "description": "Đợi giữa các click"},
        ],
    },
    {
        "name": "📋 Clipboard Copy-Paste — Sao chép & Dán",
        "description": "Chọn vùng nguồn → copy → chuyển cửa sổ → paste → lặp lại",
        "actions": [
            {"type": "activate_window", "title": "Source", "delay_after": 300, "description": "Mở cửa sổ nguồn"},
            {"type": "hotkey", "keys": "ctrl+a", "delay_after": 100, "description": "Chọn tất cả"},
            {"type": "hotkey", "keys": "ctrl+c", "delay_after": 200, "description": "Copy"},
            {"type": "activate_window", "title": "Destination", "delay_after": 300, "description": "Mở cửa sổ đích"},
            {"type": "mouse_click", "x": 400, "y": 300, "delay_after": 100, "description": "Click vào vị trí dán"},
            {"type": "hotkey", "keys": "ctrl+v", "delay_after": 200, "description": "Paste"},
        ],
    },
    {
        "name": "🔄 App Restart Monitor — Giám sát & khởi động lại",
        "description": "Kiểm tra cửa sổ app → nếu không thấy → mở lại app",
        "actions": [
            {"type": "set_variable", "var_name": "target_app", "value": "Notepad", "operation": "set", "delay_after": 0, "description": "Tên app cần giám sát"},
            {"type": "activate_window", "title": "${target_app}", "delay_after": 500, "description": "Thử kích hoạt app"},
            {"type": "delay", "duration_ms": 2000, "delay_after": 0, "description": "Đợi kiểm tra"},
            {"type": "comment", "text": "Thêm If-check và RunCommand để mở lại app nếu cần", "delay_after": 0, "description": "Hướng dẫn"},
        ],
    },
    {
        "name": "📧 Batch Input — Nhập hàng loạt từ file",
        "description": "Đọc từng dòng từ file → click vào ô → nhập → Enter → lặp lại",
        "actions": [
            {"type": "set_variable", "var_name": "line_num", "value": "0", "operation": "set", "delay_after": 0, "description": "Bắt đầu từ dòng 0"},
            {"type": "read_file_line", "file_path": "input_data.txt", "line_index_var": "line_num", "target_var": "current_line", "delay_after": 0, "description": "Đọc 1 dòng dữ liệu"},
            {"type": "mouse_click", "x": 400, "y": 300, "delay_after": 200, "description": "Click vào ô nhập"},
            {"type": "type_text", "text": "${current_line}", "delay_after": 100, "description": "Nhập dữ liệu từ file"},
            {"type": "key_press", "key": "enter", "delay_after": 300, "description": "Submit"},
            {"type": "set_variable", "var_name": "line_num", "value": "1", "operation": "increment", "delay_after": 0, "description": "Chuyển dòng tiếp"},
        ],
    },
]


def get_templates() -> list[dict[str, Any]]:
    """Return all available templates (built-in + user custom)."""
    templates = list(BUILTIN_TEMPLATES)

    # Load user templates from templates/ directory
    from core.app_paths import TEMPLATES_DIR

    templates_dir = TEMPLATES_DIR
    if templates_dir.exists():
        for f in sorted(templates_dir.glob("*.json")):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                templates.append(data)
            except Exception as e:
                logger.warning("Failed to load template %s: %s", f.name, e)

    return templates


def create_actions_from_template(template: dict[str, Any]) -> list[Action]:
    """Create Action objects from a template definition."""
    actions = []
    for spec in template.get("actions", []):
        action_type = spec.get("type", "")
        try:
            cls = get_action_class(action_type)
        except (ValueError, KeyError):
            logger.warning("Unknown action type in template: %s", action_type)
            continue
        if not cls:
            logger.warning("Unknown action type in template: %s", action_type)
            continue

        action = cls()
        # Set delay_after
        action.delay_after = spec.get("delay_after", 100)
        # Set description
        action.description = spec.get("description", "")

        # Set type-specific params
        params = {k: v for k, v in spec.items() if k not in ("type", "delay_after", "description")}
        if params:
            try:
                action._set_params(params)
            except Exception as e:
                logger.warning("Failed to set params for %s: %s", action_type, e)

        actions.append(action)

    return actions
