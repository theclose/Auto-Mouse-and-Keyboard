"""
Automation modules package — atomic action implementations.

Each sub-module registers Action subclasses via @register_action() decorator
in core.action. The registration happens at import time, so modules MUST be
imported before any action type lookup (get_action_class).

Module Index:
    ┌──────────────────┬───────────────────────────────────────────────┐
    │ Module           │ Action Types                                  │
    ├──────────────────┼───────────────────────────────────────────────┤
    │ modules.mouse    │ mouse_click, mouse_double_click,              │
    │                  │ mouse_right_click, mouse_move,                │
    │                  │ mouse_drag, mouse_scroll                      │
    │ modules.keyboard │ key_press, key_combo, type_text, hotkey       │
    │ modules.image    │ wait_for_image, click_on_image,               │
    │                  │ image_exists, take_screenshot                  │
    │ modules.pixel    │ check_pixel_color, wait_for_color             │
    │ modules.system   │ activate_window, log_to_file, read_clipboard, │
    │                  │ read_file_line, write_to_file,                │
    │                  │ secure_type_text, run_macro, capture_text     │
    │ modules.screen   │ (screen utilities, no registered types)       │
    └──────────────────┴───────────────────────────────────────────────┘

Flow control actions (loop_block, if_*, set_variable, split_string,
comment) are registered in core.scheduler (NOT in this package).

Import Order:
    All modules are imported in gui/main_window.py at startup.
    core.scheduler is imported AFTER modules.* to avoid conflicts.

See Also:
    core.scheduler — Flow control & variable actions (7 types)
    core.action    — Action base class and registry
"""
