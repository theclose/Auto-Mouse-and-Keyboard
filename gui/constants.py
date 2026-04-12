"""
Shared GUI constants — Single source of truth for action type icons and colors.
Import from here instead of duplicating in multiple files.

TYPE_ICONS: Auto-generated from Action subclass TYPE_ICON attributes,
with fallback to hardcoded defaults for backward compatibility.
"""

__all__ = ['TYPE_ICONS', 'COLOR_PRESETS']


def _build_type_icons() -> dict[str, str]:
    """Build TYPE_ICONS from the Action registry.

    Strategy:
      1. Start with hardcoded fallback dict (covers all 34 existing types)
      2. Overlay with registry-discovered TYPE_ICON attributes
      3. Any new action class that defines TYPE_ICON will auto-appear

    This ensures zero-risk for existing code while enabling future
    single-source-of-truth for new action types.
    """
    # Hardcoded fallback (backward-compatible, covers existing 34 types)
    icons: dict[str, str] = {
        "mouse_click": "\U0001f5b1",
        "mouse_double_click": "\U0001f5b1",
        "mouse_right_click": "\U0001f5b1",
        "mouse_move": "\U0001f5b1",
        "mouse_drag": "\U0001f5b1",
        "mouse_scroll": "\U0001f5b1",
        "key_press": "\u2328",
        "key_combo": "\u2328",
        "type_text": "\u2328",
        "hotkey": "\u2328",
        "delay": "\u23f1",
        "wait_for_image": "\U0001f5bc",
        "click_on_image": "\U0001f5bc",
        "image_exists": "\U0001f5bc",
        "take_screenshot": "\U0001f4f8",
        "check_pixel_color": "\U0001f3a8",
        "wait_for_color": "\U0001f3a8",
        "loop_block": "\U0001f501",
        "if_image_found": "\u2753",
        "if_pixel_color": "\U0001f3af",
        "if_variable": "\U0001f4cf",
        "set_variable": "\U0001f4ca",
        "split_string": "\u2702\ufe0f",
        "comment": "\U0001f4ac",
        "activate_window": "\U0001f5a5",
        "log_to_file": "\U0001f4dd",
        "read_clipboard": "\U0001f4cb",
        "read_file_line": "\U0001f4c2",
        "write_to_file": "\U0001f4be",
        "secure_type_text": "\U0001f512",
        "run_macro": "\u25b6\ufe0f",
        "capture_text": "\U0001f50d",
        "group": "\U0001f4e6",
        "run_command": "\u26a1",
        "stealth_click": "\U0001f47b",
        "stealth_type": "\U0001f47b",
    }

    # Auto-discover from registry (overlay — new types auto-register)
    try:
        from core.action import _ACTION_REGISTRY
        for type_name, cls in _ACTION_REGISTRY.items():
            icon = getattr(cls, 'TYPE_ICON', '')
            if icon:  # Only override if subclass defines a non-empty icon
                icons[type_name] = icon
    except ImportError:
        pass  # Fallback to hardcoded if registry not available

    return icons


# Build on import
TYPE_ICONS: dict[str, str] = _build_type_icons()

# Per-action color presets (used via action.color field)
COLOR_PRESETS: dict[str, tuple[int, int, int, int]] = {
    "red":    (220, 53, 69, 45),
    "orange": (255, 152, 0, 45),
    "yellow": (255, 193, 7, 45),
    "green":  (76, 175, 80, 45),
    "teal":   (0, 150, 136, 45),
    "blue":   (33, 150, 243, 45),
    "indigo": (63, 81, 181, 45),
    "purple": (156, 39, 176, 45),
    "pink":   (233, 30, 99, 45),
}
