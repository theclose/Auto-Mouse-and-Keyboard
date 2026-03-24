"""
Smart Hints engine — analyzes macro structure and provides
contextual tips, warnings, and suggestions.
"""

import logging

from core.action import Action

logger = logging.getLogger(__name__)


def analyze_hints(actions: list[Action]) -> list[dict[str, str | int]]:
    """Analyze a list of actions and return contextual hints.

    Returns list of dicts with keys:
        - level: 'tip' | 'warning' | 'error'
        - icon: emoji
        - message: hint text
        - action_idx: optional index of related action
    """
    hints: list[dict[str, str | int]] = []
    if not actions:
        return hints

    for i, action in enumerate(actions):
        atype = getattr(action, "ACTION_TYPE", "")
        prev = actions[i - 1] if i > 0 else None
        prev_type = getattr(prev, "ACTION_TYPE", "") if prev else ""

        # Rule 1: Click/mouse right after ActivateWindow without delay
        if prev_type == "activate_window" and atype.startswith("mouse_") and action.delay_after < 300:
            hints.append(
                {
                    "level": "tip",
                    "icon": "💡",
                    "message": f"Action #{i+1}: Nên thêm Delay ≥500ms sau "
                    f"ActivateWindow (hiện tại: {action.delay_after}ms)",
                    "action_idx": i,
                }
            )

        # Rule 2: TypeText right after ActivateWindow without delay
        if prev_type == "activate_window" and atype in ("type_text", "secure_type_text") and action.delay_after < 200:
            hints.append(
                {
                    "level": "tip",
                    "icon": "💡",
                    "message": f"Action #{i+1}: Nên thêm Delay trước TypeText " f"sau ActivateWindow",
                    "action_idx": i,
                }
            )

        # Rule 3: WaitForImage with very low timeout
        if atype == "wait_for_image":
            timeout = getattr(action, "timeout_ms", 5000)
            if timeout < 2000:
                hints.append(
                    {
                        "level": "warning",
                        "icon": "⚠️",
                        "message": f"Action #{i+1}: WaitForImage timeout quá thấp "
                        f"({timeout}ms) — có thể fail trên máy chậm",
                        "action_idx": i,
                    }
                )

        # Rule 4: LoopBlock with count=0 (infinite) without break condition
        if atype == "loop_block":
            loop_count = getattr(action, "loop_count", 1)
            if loop_count == 0:
                # Check if sub-actions have any IfVariable that could break
                children = getattr(action, "children", [])
                has_break = any(getattr(c, "ACTION_TYPE", "") == "if_variable" for c in children)
                if not has_break:
                    hints.append(
                        {
                            "level": "warning",
                            "icon": "🔄",
                            "message": f"Action #{i+1}: LoopBlock vô hạn không có "
                            f"điều kiện thoát — có thể chạy mãi",
                            "action_idx": i,
                        }
                    )

        # Rule 8: Empty composite (no sub-actions)
        if action.is_composite:
            children = getattr(action, "children", [])
            if not children:
                hints.append(
                    {
                        "level": "warning",
                        "icon": "📭",
                        "message": f"Action #{i+1}: {atype} không có " f"sub-action nào — sẽ không làm gì",
                        "action_idx": i,
                    }
                )

        # Rule 5: Duplicate consecutive delays
        if atype == "delay" and prev_type == "delay":
            hints.append(
                {
                    "level": "tip",
                    "icon": "💡",
                    "message": f"Action #{i+1}: Hai Delay liên tiếp — " f"có thể gộp thành một",
                    "action_idx": i,
                }
            )

        # Rule 6: Image action without template path
        if atype in ("wait_for_image", "click_on_image", "image_exists"):
            template = getattr(action, "template_path", "")
            if not template:
                hints.append(
                    {
                        "level": "error",
                        "icon": "❌",
                        "message": f"Action #{i+1}: {atype} chưa có ảnh mẫu",
                        "action_idx": i,
                    }
                )

        # Rule 7: Variable used but never set
        if atype == "if_variable":
            var_name = getattr(action, "var_name", "")
            if var_name and not var_name.startswith("${"):
                # Check if any prior SetVariable sets this var
                prior_sets = [
                    a
                    for a in actions[:i]
                    if getattr(a, "ACTION_TYPE", "") == "set_variable" and getattr(a, "var_name", "") == var_name
                ]
                if not prior_sets:
                    hints.append(
                        {
                            "level": "warning",
                            "icon": "⚠️",
                            "message": f'Action #{i+1}: Biến "${{{var_name}}}" ' f"chưa được set trước đó",
                            "action_idx": i,
                        }
                    )

    # Global hints
    total_delay = sum(a.delay_after for a in actions)
    if total_delay > 30000:
        hints.append(
            {
                "level": "tip",
                "icon": "⏱",
                "message": f"Tổng delay: {total_delay/1000:.1f}s — " f"xem xét giảm để macro chạy nhanh hơn",
            }
        )

    if len(actions) > 50:
        hints.append(
            {
                "level": "tip",
                "icon": "📦",
                "message": f"Macro có {len(actions)} actions — " f"xem xét chia thành sub-macro (RunMacro)",
            }
        )

    # ─── Recursive analysis: check rules inside composites ───
    for nested_action, label in _collect_nested_actions(actions):
        atype = getattr(nested_action, "ACTION_TYPE", "")

        # Rule 3 (nested): WaitForImage with very low timeout
        if atype == "wait_for_image":
            timeout = getattr(nested_action, "timeout_ms", 5000)
            if timeout < 2000:
                hints.append(
                    {
                        "level": "warning",
                        "icon": "⚠️",
                        "message": f"{label}: WaitForImage timeout quá thấp " f"({timeout}ms)",
                    }
                )

        # Rule 6 (nested): Image action without template path
        if atype in ("wait_for_image", "click_on_image", "image_exists"):
            template = getattr(nested_action, "template_path", "")
            if not template:
                hints.append(
                    {
                        "level": "error",
                        "icon": "❌",
                        "message": f"{label}: {atype} chưa có ảnh mẫu",
                    }
                )

        # Rule 5 (nested): Check for empty composite children
        if atype in ("loop_block", "if_image_found", "if_pixel_color", "if_variable"):
            children = getattr(nested_action, "children", [])
            if not children:
                hints.append(
                    {
                        "level": "warning",
                        "icon": "📭",
                        "message": f"{label}: {atype} không có sub-action nào",
                    }
                )

    return hints


def _collect_nested_actions(actions: list[Action], parent_label: str = "") -> list[tuple[Action, str]]:
    """Recursively collect all nested actions with context labels.

    Returns list of (action, label) tuples for sub-actions only
    (root-level actions are already handled by the main loop).
    """
    result: list[tuple[Action, str]] = []
    for i, action in enumerate(actions):
        prefix = f"#{i+1}" if not parent_label else f"{parent_label}"
        if action.is_composite:
            if action.has_branches:
                for j, child in enumerate(action.then_children):
                    label = f"[{prefix} → THEN #{j+1}]"
                    result.append((child, label))
                    # Recurse deeper
                    result.extend(_collect_nested_actions([child], label))
                for j, child in enumerate(action.else_children):
                    label = f"[{prefix} → ELSE #{j+1}]"
                    result.append((child, label))
                    result.extend(_collect_nested_actions([child], label))
            else:
                for j, child in enumerate(action.children):
                    label = f"[{prefix} → sub #{j+1}]"
                    result.append((child, label))
                    result.extend(_collect_nested_actions([child], label))
    return result
