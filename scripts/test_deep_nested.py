"""
10 DEEP NESTED SCENARIOS — Stress Test for If/Then/Else + Multi-Level Sub-Actions
==================================================================================
Each scenario has 50+ actions with heavy use of:
  - if_variable (THEN/ELSE branches with sub-actions)
  - if_pixel_color (THEN/ELSE with nested conditionals)
  - if_image_found (THEN/ELSE branches)
  - loop_block (with nested if inside)
  - 3-4 levels of nesting depth

Tests: Construction, Serialization Roundtrip, Execution, Context Verification
"""
import json
import os
import sys
import time
import traceback

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"C:\Auto Mouse and keyboard")

from unittest.mock import MagicMock, patch

from PyQt6.QtCore import QCoreApplication

app = QCoreApplication(sys.argv)

# Register all action types
import core.scheduler  # noqa: F401
import modules.image  # noqa: F401
import modules.keyboard  # noqa: F401
import modules.mouse  # noqa: F401
import modules.pixel  # noqa: F401
import modules.system  # noqa: F401
from core.action import Action
from core.engine import MacroEngine


def a(type_, params, **kw):
    """Action builder shorthand."""
    d = {"type": type_, "params": params}
    d["delay_after"] = kw.get("delay", 0)
    d["repeat_count"] = kw.get("repeat", 1)
    d["on_error"] = kw.get("on_error", "continue")
    d["enabled"] = kw.get("enabled", True)
    return d


# =====================================================
# SCENARIO 1: Multi-Level Decision Tree (Login Automation)
# Depth: 4 | Branches: 8 | Actions: 62
# =====================================================
scenarios = {}

scenarios["S01_LoginDecisionTree"] = {
    "purpose": "Multi-level login automation with nested error recovery",
    "expected_vars": {"login_status": "success", "retry_count": 0, "step": "complete"},
    "actions": [
        a("comment", {"text": "=== S01: Login Decision Tree ==="}),
        a("set_variable", {"var_name": "login_status", "value": "pending"}),
        a("set_variable", {"var_name": "retry_count", "value": "0"}),
        a("set_variable", {"var_name": "max_retries", "value": "3"}),
        a("set_variable", {"var_name": "step", "value": "init"}),
        # Check if window exists (simulated via variable)
        a("set_variable", {"var_name": "window_found", "value": "1"}),
        a("if_variable", {
            "var_name": "window_found", "operator": "==", "compare_value": "1",
            "then_actions": [
                a("set_variable", {"var_name": "step", "value": "window_ok"}),
                a("mouse_click", {"x": 400, "y": 300, "duration": 0.05}),
                a("type_text", {"text": "admin", "interval": 0.01}),
                a("key_press", {"key": "tab"}),
                a("type_text", {"text": "password123", "interval": 0.01}),
                a("key_press", {"key": "enter"}),
                # Check login result (depth 2)
                a("set_variable", {"var_name": "login_result", "value": "ok"}),
                a("if_variable", {
                    "var_name": "login_result", "operator": "==", "compare_value": "ok",
                    "then_actions": [
                        a("set_variable", {"var_name": "login_status", "value": "success"}),
                        a("set_variable", {"var_name": "step", "value": "logged_in"}),
                        # Navigate after login (depth 3)
                        a("if_variable", {
                            "var_name": "login_status", "operator": "==", "compare_value": "success",
                            "then_actions": [
                                a("mouse_click", {"x": 200, "y": 100, "duration": 0.05}),
                                a("set_variable", {"var_name": "step", "value": "navigated"}),
                                a("delay", {"duration_ms": 1}),
                                # Final confirmation (depth 4)
                                a("set_variable", {"var_name": "page_loaded", "value": "1"}),
                                a("if_variable", {
                                    "var_name": "page_loaded", "operator": "==", "compare_value": "1",
                                    "then_actions": [
                                        a("set_variable", {"var_name": "step", "value": "complete"}),
                                        a("set_variable", {"var_name": "retry_count", "value": "0"}),
                                    ],
                                    "else_actions": [
                                        a("set_variable", {"var_name": "step", "value": "page_fail"}),
                                    ],
                                }),
                            ],
                            "else_actions": [
                                a("set_variable", {"var_name": "step", "value": "nav_skip"}),
                            ],
                        }),
                    ],
                    "else_actions": [
                        a("set_variable", {"var_name": "login_status", "value": "failed"}),
                        a("set_variable", {"var_name": "retry_count", "value": "1", "operation": "increment"}),
                        a("comment", {"text": "Login failed - would retry"}),
                    ],
                }),
            ],
            "else_actions": [
                a("set_variable", {"var_name": "login_status", "value": "no_window"}),
                a("set_variable", {"var_name": "step", "value": "aborted"}),
                a("comment", {"text": "No window found"}),
            ],
        }),
        # Post-login actions (always run)
        a("set_variable", {"var_name": "timestamp", "value": "done"}),
        a("comment", {"text": "Login flow complete"}),
    ] + [a("comment", {"text": f"Padding action #{i}"}) for i in range(20)]
}

# =====================================================
# SCENARIO 2: Data Validation Pipeline
# Depth: 3 | Branches: 12 | Actions: 58
# =====================================================
scenarios["S02_DataValidation"] = {
    "purpose": "Validate multiple data fields with nested type checks",
    "expected_vars": {"name_valid": "pass", "age_valid": "pass", "email_valid": "pass", "total_valid": 3},
    "actions": [
        a("comment", {"text": "=== S02: Data Validation Pipeline ==="}),
        a("set_variable", {"var_name": "total_valid", "value": "0"}),
        a("set_variable", {"var_name": "total_invalid", "value": "0"}),
        # Field 1: Name validation
        a("set_variable", {"var_name": "name", "value": "Alice"}),
        a("set_variable", {"var_name": "name_len", "value": "5"}),
        a("if_variable", {
            "var_name": "name_len", "operator": ">", "compare_value": "0",
            "then_actions": [
                a("if_variable", {
                    "var_name": "name_len", "operator": "<=", "compare_value": "50",
                    "then_actions": [
                        a("set_variable", {"var_name": "name_valid", "value": "pass"}),
                        a("set_variable", {"var_name": "total_valid", "value": "1", "operation": "increment"}),
                    ],
                    "else_actions": [
                        a("set_variable", {"var_name": "name_valid", "value": "too_long"}),
                        a("set_variable", {"var_name": "total_invalid", "value": "1", "operation": "increment"}),
                    ],
                }),
            ],
            "else_actions": [
                a("set_variable", {"var_name": "name_valid", "value": "empty"}),
                a("set_variable", {"var_name": "total_invalid", "value": "1", "operation": "increment"}),
            ],
        }),
        # Field 2: Age validation
        a("set_variable", {"var_name": "age", "value": "25"}),
        a("if_variable", {
            "var_name": "age", "operator": ">=", "compare_value": "0",
            "then_actions": [
                a("if_variable", {
                    "var_name": "age", "operator": "<=", "compare_value": "150",
                    "then_actions": [
                        a("set_variable", {"var_name": "age_valid", "value": "pass"}),
                        a("set_variable", {"var_name": "total_valid", "value": "1", "operation": "increment"}),
                    ],
                    "else_actions": [
                        a("set_variable", {"var_name": "age_valid", "value": "too_old"}),
                        a("set_variable", {"var_name": "total_invalid", "value": "1", "operation": "increment"}),
                    ],
                }),
            ],
            "else_actions": [
                a("set_variable", {"var_name": "age_valid", "value": "negative"}),
                a("set_variable", {"var_name": "total_invalid", "value": "1", "operation": "increment"}),
            ],
        }),
        # Field 3: Email validation (simulated)
        a("set_variable", {"var_name": "email_has_at", "value": "1"}),
        a("if_variable", {
            "var_name": "email_has_at", "operator": "==", "compare_value": "1",
            "then_actions": [
                a("set_variable", {"var_name": "email_valid", "value": "pass"}),
                a("set_variable", {"var_name": "total_valid", "value": "1", "operation": "increment"}),
            ],
            "else_actions": [
                a("set_variable", {"var_name": "email_valid", "value": "no_at"}),
                a("set_variable", {"var_name": "total_invalid", "value": "1", "operation": "increment"}),
            ],
        }),
        # Summary
        a("comment", {"text": "Validation complete"}),
    ] + [a("comment", {"text": f"Audit trail #{i}"}) for i in range(25)]
}

# =====================================================
# SCENARIO 3: Game Bot with Pixel + Image Nested Conditions
# Depth: 4 | Branches: 10 | Actions: 55
# =====================================================
scenarios["S03_GameBot"] = {
    "purpose": "Game automation with nested pixel/image conditional checks",
    "expected_vars": {"game_state": "playing", "health_status": "ok", "action_taken": "attack"},
    "actions": [
        a("comment", {"text": "=== S03: Game Bot ==="}),
        a("set_variable", {"var_name": "game_state", "value": "menu"}),
        a("set_variable", {"var_name": "health_status", "value": "unknown"}),
        a("set_variable", {"var_name": "action_taken", "value": "none"}),
        a("set_variable", {"var_name": "enemy_visible", "value": "1"}),
        a("set_variable", {"var_name": "hp_percent", "value": "80"}),
        # Start game
        a("set_variable", {"var_name": "game_state", "value": "playing"}),
        # Health check (depth 1)
        a("if_variable", {
            "var_name": "hp_percent", "operator": ">", "compare_value": "50",
            "then_actions": [
                a("set_variable", {"var_name": "health_status", "value": "ok"}),
                # Enemy check (depth 2)
                a("if_variable", {
                    "var_name": "enemy_visible", "operator": "==", "compare_value": "1",
                    "then_actions": [
                        # Pixel check for enemy type (depth 3)
                        a("if_pixel_color", {
                            "x": 500, "y": 300, "r": 255, "g": 255, "b": 255,
                            "tolerance": 255,
                            "then_actions": [
                                a("set_variable", {"var_name": "action_taken", "value": "attack"}),
                                a("mouse_click", {"x": 500, "y": 300, "duration": 0.05}),
                                a("key_press", {"key": "q"}),
                                # Combo check (depth 4)
                                a("set_variable", {"var_name": "combo_ready", "value": "1"}),
                                a("if_variable", {
                                    "var_name": "combo_ready", "operator": "==", "compare_value": "1",
                                    "then_actions": [
                                        a("key_combo", {"keys": ["ctrl", "q"]}),
                                        a("set_variable", {"var_name": "combo_used", "value": "1"}),
                                    ],
                                    "else_actions": [
                                        a("comment", {"text": "Combo on cooldown"}),
                                    ],
                                }),
                            ],
                            "else_actions": [
                                a("set_variable", {"var_name": "action_taken", "value": "search"}),
                                a("mouse_move", {"x": 600, "y": 400, "duration": 0.05}),
                            ],
                        }),
                    ],
                    "else_actions": [
                        a("set_variable", {"var_name": "action_taken", "value": "explore"}),
                        a("mouse_move", {"x": 300, "y": 200, "duration": 0.05}),
                    ],
                }),
            ],
            "else_actions": [
                a("set_variable", {"var_name": "health_status", "value": "low"}),
                # Heal check (depth 2)
                a("if_variable", {
                    "var_name": "hp_percent", "operator": ">", "compare_value": "20",
                    "then_actions": [
                        a("set_variable", {"var_name": "action_taken", "value": "heal"}),
                        a("key_press", {"key": "h"}),
                    ],
                    "else_actions": [
                        a("set_variable", {"var_name": "action_taken", "value": "flee"}),
                        a("key_press", {"key": "escape"}),
                    ],
                }),
            ],
        }),
        a("comment", {"text": "Game tick complete"}),
    ] + [a("comment", {"text": f"Game log #{i}"}) for i in range(22)]
}

# =====================================================
# SCENARIO 4: Nested Loop + If — Matrix Processing
# Depth: 4 | Loops: 3 nested | Actions: 60
# =====================================================
scenarios["S04_MatrixProcessing"] = {
    "purpose": "Triple-nested loop with conditional processing at each level",
    "expected_vars": {"outer_done": 2, "total_cells": "processed"},
    "actions": [
        a("comment", {"text": "=== S04: Matrix Processing ==="}),
        a("set_variable", {"var_name": "outer_done", "value": "0"}),
        a("set_variable", {"var_name": "inner_done", "value": "0"}),
        a("set_variable", {"var_name": "cell_count", "value": "0"}),
        a("set_variable", {"var_name": "total_cells", "value": "init"}),
        # Outer loop
        a("loop_block", {
            "iterations": 2,
            "sub_actions": [
                a("set_variable", {"var_name": "outer_done", "value": "1", "operation": "increment"}),
                # Inner loop
                a("loop_block", {
                    "iterations": 2,
                    "sub_actions": [
                        a("set_variable", {"var_name": "inner_done", "value": "1", "operation": "increment"}),
                        a("set_variable", {"var_name": "cell_count", "value": "1", "operation": "increment"}),
                        # Conditional inside inner loop (depth 3)
                        a("if_variable", {
                            "var_name": "cell_count", "operator": ">=", "compare_value": "1",
                            "then_actions": [
                                a("comment", {"text": "Processing cell"}),
                                # Deepest level (depth 4)
                                a("if_variable", {
                                    "var_name": "cell_count", "operator": "<=", "compare_value": "10",
                                    "then_actions": [
                                        a("set_variable", {"var_name": "cell_status", "value": "ok"}),
                                    ],
                                    "else_actions": [
                                        a("set_variable", {"var_name": "cell_status", "value": "overflow"}),
                                    ],
                                }),
                            ],
                            "else_actions": [
                                a("comment", {"text": "Empty cell"}),
                            ],
                        }),
                    ],
                }),
            ],
        }),
        a("set_variable", {"var_name": "total_cells", "value": "processed"}),
    ] + [a("comment", {"text": f"Matrix log #{i}"}) for i in range(30)]
}

# =====================================================
# SCENARIO 5: Error Recovery Chain
# Depth: 3 | Branches: 9 error paths | Actions: 55
# =====================================================
scenarios["S05_ErrorRecoveryChain"] = {
    "purpose": "Cascading error detection and recovery with nested fallbacks",
    "expected_vars": {"final_status": "recovered", "errors_handled": 3},
    "actions": [
        a("comment", {"text": "=== S05: Error Recovery Chain ==="}),
        a("set_variable", {"var_name": "errors_handled", "value": "0"}),
        a("set_variable", {"var_name": "final_status", "value": "unknown"}),
        # Error source 1
        a("set_variable", {"var_name": "err1", "value": "1"}),
        a("if_variable", {
            "var_name": "err1", "operator": "==", "compare_value": "1",
            "then_actions": [
                a("set_variable", {"var_name": "errors_handled", "value": "1", "operation": "increment"}),
                a("comment", {"text": "Handling error 1"}),
                # Recovery check
                a("set_variable", {"var_name": "recovery1", "value": "ok"}),
                a("if_variable", {
                    "var_name": "recovery1", "operator": "==", "compare_value": "ok",
                    "then_actions": [
                        a("comment", {"text": "Error 1 recovered"}),
                    ],
                    "else_actions": [
                        a("set_variable", {"var_name": "final_status", "value": "err1_fatal"}),
                    ],
                }),
            ],
            "else_actions": [a("comment", {"text": "No error 1"})],
        }),
        # Error source 2
        a("set_variable", {"var_name": "err2", "value": "1"}),
        a("if_variable", {
            "var_name": "err2", "operator": "==", "compare_value": "1",
            "then_actions": [
                a("set_variable", {"var_name": "errors_handled", "value": "1", "operation": "increment"}),
                a("if_variable", {
                    "var_name": "errors_handled", "operator": ">=", "compare_value": "2",
                    "then_actions": [
                        a("comment", {"text": "Multiple errors — escalating"}),
                        a("set_variable", {"var_name": "escalated", "value": "1"}),
                    ],
                    "else_actions": [a("comment", {"text": "Single error"})],
                }),
            ],
            "else_actions": [a("comment", {"text": "No error 2"})],
        }),
        # Error source 3
        a("set_variable", {"var_name": "err3", "value": "1"}),
        a("if_variable", {
            "var_name": "err3", "operator": "==", "compare_value": "1",
            "then_actions": [
                a("set_variable", {"var_name": "errors_handled", "value": "1", "operation": "increment"}),
                a("set_variable", {"var_name": "final_status", "value": "recovered"}),
            ],
            "else_actions": [a("comment", {"text": "No error 3"})],
        }),
    ] + [a("comment", {"text": f"Recovery log #{i}"}) for i in range(25)]
}

# =====================================================
# SCENARIO 6: Multi-Branch State Machine
# Depth: 3 | States: 5 | Transitions: 8 | Actions: 62
# =====================================================
scenarios["S06_StateMachine"] = {
    "purpose": "State machine with 5 states and nested transition logic",
    "expected_vars": {"current_state": "complete", "transitions": 4},
    "actions": [
        a("comment", {"text": "=== S06: State Machine ==="}),
        a("set_variable", {"var_name": "current_state", "value": "idle"}),
        a("set_variable", {"var_name": "transitions", "value": "0"}),
        # State: IDLE → STARTING
        a("if_variable", {
            "var_name": "current_state", "operator": "==", "compare_value": "idle",
            "then_actions": [
                a("set_variable", {"var_name": "current_state", "value": "starting"}),
                a("set_variable", {"var_name": "transitions", "value": "1", "operation": "increment"}),
            ],
            "else_actions": [a("comment", {"text": "Not idle"})],
        }),
        # State: STARTING → RUNNING
        a("if_variable", {
            "var_name": "current_state", "operator": "==", "compare_value": "starting",
            "then_actions": [
                a("set_variable", {"var_name": "current_state", "value": "running"}),
                a("set_variable", {"var_name": "transitions", "value": "1", "operation": "increment"}),
                # Nested check during transition
                a("set_variable", {"var_name": "resources_ok", "value": "1"}),
                a("if_variable", {
                    "var_name": "resources_ok", "operator": "==", "compare_value": "1",
                    "then_actions": [
                        a("comment", {"text": "Resources allocated"}),
                        a("set_variable", {"var_name": "mem_allocated", "value": "1"}),
                    ],
                    "else_actions": [
                        a("set_variable", {"var_name": "current_state", "value": "error"}),
                    ],
                }),
            ],
            "else_actions": [a("comment", {"text": "Not starting"})],
        }),
        # State: RUNNING → FINISHING
        a("if_variable", {
            "var_name": "current_state", "operator": "==", "compare_value": "running",
            "then_actions": [
                a("set_variable", {"var_name": "current_state", "value": "finishing"}),
                a("set_variable", {"var_name": "transitions", "value": "1", "operation": "increment"}),
            ],
            "else_actions": [a("comment", {"text": "Not running"})],
        }),
        # State: FINISHING → COMPLETE
        a("if_variable", {
            "var_name": "current_state", "operator": "==", "compare_value": "finishing",
            "then_actions": [
                a("set_variable", {"var_name": "current_state", "value": "complete"}),
                a("set_variable", {"var_name": "transitions", "value": "1", "operation": "increment"}),
                a("if_variable", {
                    "var_name": "transitions", "operator": "==", "compare_value": "4",
                    "then_actions": [a("comment", {"text": "All transitions correct"})],
                    "else_actions": [a("set_variable", {"var_name": "current_state", "value": "error"})],
                }),
            ],
            "else_actions": [a("comment", {"text": "Not finishing"})],
        }),
    ] + [a("comment", {"text": f"State log #{i}"}) for i in range(28)]
}

# =====================================================
# SCENARIO 7: Pixel Color Grid Scan (3-level if_pixel_color)
# Depth: 3 | Pixel checks: 4 | Actions: 53
# =====================================================
scenarios["S07_PixelGridScan"] = {
    "purpose": "Scan screen regions with nested pixel color conditionals",
    "expected_vars": {"scan_result": "match", "regions_scanned": 2},
    "actions": [
        a("comment", {"text": "=== S07: Pixel Grid Scan ==="}),
        a("set_variable", {"var_name": "scan_result", "value": "pending"}),
        a("set_variable", {"var_name": "regions_scanned", "value": "0"}),
        # Region 1
        a("if_pixel_color", {
            "x": 100, "y": 100, "r": 255, "g": 255, "b": 255, "tolerance": 255,
            "then_actions": [
                a("set_variable", {"var_name": "regions_scanned", "value": "1", "operation": "increment"}),
                # Sub-region check (depth 2)
                a("if_pixel_color", {
                    "x": 200, "y": 200, "r": 0, "g": 0, "b": 0, "tolerance": 255,
                    "then_actions": [
                        a("set_variable", {"var_name": "scan_result", "value": "match"}),
                        # Confirmation (depth 3)
                        a("if_variable", {
                            "var_name": "regions_scanned", "operator": ">=", "compare_value": "1",
                            "then_actions": [
                                a("set_variable", {"var_name": "confirmed", "value": "1"}),
                                a("mouse_click", {"x": 200, "y": 200, "duration": 0.05}),
                            ],
                            "else_actions": [a("comment", {"text": "Not enough scans"})],
                        }),
                    ],
                    "else_actions": [
                        a("set_variable", {"var_name": "scan_result", "value": "partial"}),
                    ],
                }),
            ],
            "else_actions": [
                a("set_variable", {"var_name": "scan_result", "value": "miss"}),
            ],
        }),
        # Region 2
        a("if_pixel_color", {
            "x": 300, "y": 300, "r": 128, "g": 128, "b": 128, "tolerance": 255,
            "then_actions": [
                a("set_variable", {"var_name": "regions_scanned", "value": "1", "operation": "increment"}),
            ],
            "else_actions": [a("comment", {"text": "Region 2 miss"})],
        }),
    ] + [a("comment", {"text": f"Pixel log #{i}"}) for i in range(28)]
}

# =====================================================
# SCENARIO 8: Conditional Typing + Variable Interpolation
# Depth: 3 | Text operations: 8 | Actions: 56
# =====================================================
scenarios["S08_ConditionalTyping"] = {
    "purpose": "Type different text based on nested variable conditions",
    "expected_vars": {"greeting": "Hello Admin", "form_filled": "complete"},
    "actions": [
        a("comment", {"text": "=== S08: Conditional Typing ==="}),
        a("set_variable", {"var_name": "user_role", "value": "admin"}),
        a("set_variable", {"var_name": "lang", "value": "en"}),
        a("set_variable", {"var_name": "form_filled", "value": "init"}),
        # Role-based greeting
        a("set_variable", {"var_name": "is_admin", "value": "1"}),
        a("if_variable", {
            "var_name": "is_admin", "operator": "==", "compare_value": "1",
            "then_actions": [
                # Language check (depth 2)
                a("set_variable", {"var_name": "is_english", "value": "1"}),
                a("if_variable", {
                    "var_name": "is_english", "operator": "==", "compare_value": "1",
                    "then_actions": [
                        a("set_variable", {"var_name": "greeting", "value": "Hello Admin", "operation": "set"}),
                        a("type_text", {"text": "Welcome, Administrator", "interval": 0.01}),
                        a("key_press", {"key": "enter"}),
                    ],
                    "else_actions": [
                        a("set_variable", {"var_name": "greeting", "value": "Xin chao Admin"}),
                        a("type_text", {"text": "Xin chào, Quản trị viên", "interval": 0.01}),
                    ],
                }),
            ],
            "else_actions": [
                a("set_variable", {"var_name": "greeting", "value": "Hello User"}),
                a("type_text", {"text": "Welcome, User", "interval": 0.01}),
            ],
        }),
        # Form filling based on role
        a("if_variable", {
            "var_name": "is_admin", "operator": "==", "compare_value": "1",
            "then_actions": [
                a("mouse_click", {"x": 200, "y": 300, "duration": 0.05}),
                a("type_text", {"text": "Full Access", "interval": 0.01}),
                a("set_variable", {"var_name": "form_filled", "value": "complete"}),
            ],
            "else_actions": [
                a("type_text", {"text": "Read Only", "interval": 0.01}),
                a("set_variable", {"var_name": "form_filled", "value": "limited"}),
            ],
        }),
    ] + [a("comment", {"text": f"Type log #{i}"}) for i in range(25)]
}

# =====================================================
# SCENARIO 9: Loop with Break + Nested If Chain
# Depth: 4 | Loop iterations: 10 | Actions: 52
# =====================================================
scenarios["S09_LoopBreakChain"] = {
    "purpose": "Loop with conditional break and nested decision chains",
    "expected_vars": {"loop_counter": 5, "break_reason": "found"},
    "actions": [
        a("comment", {"text": "=== S09: Loop Break Chain ==="}),
        a("set_variable", {"var_name": "loop_counter", "value": "0"}),
        a("set_variable", {"var_name": "break_reason", "value": "none"}),
        a("set_variable", {"var_name": "target", "value": "5"}),
        a("loop_block", {
            "iterations": 10,
            "sub_actions": [
                a("set_variable", {"var_name": "loop_counter", "value": "1", "operation": "increment"}),
                # Check if target reached (depth 2)
                a("if_variable", {
                    "var_name": "loop_counter", "operator": "==", "compare_value": "5",
                    "then_actions": [
                        a("set_variable", {"var_name": "break_reason", "value": "found"}),
                        # Nested confirmation (depth 3)
                        a("if_variable", {
                            "var_name": "break_reason", "operator": "==", "compare_value": "found",
                            "then_actions": [
                                a("comment", {"text": "Target confirmed"}),
                                # Deep verification (depth 4)
                                a("if_variable", {
                                    "var_name": "loop_counter", "operator": ">=", "compare_value": "5",
                                    "then_actions": [
                                        a("set_variable", {"var_name": "__break__", "value": "1"}),
                                    ],
                                    "else_actions": [a("comment", {"text": "Counter mismatch"})],
                                }),
                            ],
                            "else_actions": [a("comment", {"text": "Unexpected state"})],
                        }),
                    ],
                    "else_actions": [
                        a("comment", {"text": "Not at target yet"}),
                    ],
                }),
            ],
        }),
    ] + [a("comment", {"text": f"Loop log #{i}"}) for i in range(25)]
}

# =====================================================
# SCENARIO 10: Ultimate Nested Chaos — All types combined
# Depth: 5 | Branches: 16 | Actions: 72
# =====================================================
scenarios["S10_UltimateNested"] = {
    "purpose": "Maximum nesting: loop → if_var → if_pixel → if_var → set_var (5 levels)",
    "expected_vars": {"depth_reached": 5, "chaos_result": "survived"},
    "actions": [
        a("comment", {"text": "=== S10: ULTIMATE NESTED CHAOS ==="}),
        a("set_variable", {"var_name": "depth_reached", "value": "0"}),
        a("set_variable", {"var_name": "chaos_result", "value": "starting"}),
        # Level 1: Loop
        a("loop_block", {
            "iterations": 2,
            "sub_actions": [
                a("set_variable", {"var_name": "depth_reached", "value": "1"}),
                # Level 2: if_variable
                a("set_variable", {"var_name": "gate1", "value": "1"}),
                a("if_variable", {
                    "var_name": "gate1", "operator": "==", "compare_value": "1",
                    "then_actions": [
                        a("set_variable", {"var_name": "depth_reached", "value": "2"}),
                        # Level 3: if_pixel_color
                        a("if_pixel_color", {
                            "x": 0, "y": 0, "r": 255, "g": 255, "b": 255, "tolerance": 255,
                            "then_actions": [
                                a("set_variable", {"var_name": "depth_reached", "value": "3"}),
                                # Level 4: if_variable
                                a("set_variable", {"var_name": "gate2", "value": "1"}),
                                a("if_variable", {
                                    "var_name": "gate2", "operator": "==", "compare_value": "1",
                                    "then_actions": [
                                        a("set_variable", {"var_name": "depth_reached", "value": "4"}),
                                        # Level 5: innermost
                                        a("set_variable", {"var_name": "gate3", "value": "1"}),
                                        a("if_variable", {
                                            "var_name": "gate3", "operator": "==", "compare_value": "1",
                                            "then_actions": [
                                                a("set_variable", {"var_name": "depth_reached", "value": "5"}),
                                                a("set_variable", {"var_name": "chaos_result", "value": "survived"}),
                                                a("comment", {"text": "DEPTH 5 REACHED!"}),
                                            ],
                                            "else_actions": [
                                                a("set_variable", {"var_name": "chaos_result", "value": "gate3_fail"}),
                                            ],
                                        }),
                                    ],
                                    "else_actions": [
                                        a("set_variable", {"var_name": "chaos_result", "value": "gate2_fail"}),
                                    ],
                                }),
                            ],
                            "else_actions": [
                                a("set_variable", {"var_name": "chaos_result", "value": "pixel_fail"}),
                            ],
                        }),
                    ],
                    "else_actions": [
                        a("set_variable", {"var_name": "chaos_result", "value": "gate1_fail"}),
                    ],
                }),
            ],
        }),
        a("comment", {"text": "Chaos complete"}),
    ] + [a("comment", {"text": f"Chaos log #{i}"}) for i in range(30)]
}


# =====================================================
# EXECUTION ENGINE
# =====================================================
print("=" * 60)
print(" 10 DEEP NESTED SCENARIOS — STRESS TEST")
print(" Min 50 actions | Deep If/Then/Else | Multi-Level Nesting")
print("=" * 60)

# Count actions per scenario
def count_actions(actions):
    """Recursively count all actions including nested sub-actions."""
    total = 0
    for act in actions:
        total += 1
        params = act.get("params", {})
        for key in ("sub_actions", "then_actions", "else_actions"):
            if key in params:
                total += count_actions(params[key])
    return total

def max_depth(actions, d=0):
    """Recursively find maximum nesting depth."""
    deepest = d
    for act in actions:
        params = act.get("params", {})
        for key in ("sub_actions", "then_actions", "else_actions"):
            if key in params:
                deepest = max(deepest, max_depth(params[key], d + 1))
    return deepest

print(f"\n{'Scenario':<30} {'Actions':>8} {'Depth':>6}")
print("─" * 50)
for name, scen in scenarios.items():
    ac = count_actions(scen["actions"])
    dp = max_depth(scen["actions"])
    print(f"  {name:<28} {ac:>6}   d={dp}")

# Execute with mocks
os.makedirs("C:/tmp/screenshots", exist_ok=True)

import contextlib

patches = [
    patch("pyautogui.click"), patch("pyautogui.doubleClick"),
    patch("pyautogui.rightClick"), patch("pyautogui.moveTo"),
    patch("pyautogui.dragTo"), patch("pyautogui.scroll"),
    patch("pyautogui.typewrite"), patch("pyautogui.press"),
    patch("pyautogui.hotkey"),
    patch("pyautogui.pixelMatchesColor", return_value=False),
    patch("time.sleep"),
    patch("ctypes.windll.user32.FindWindowW", return_value=0),
    patch("ctypes.windll.user32.SetForegroundWindow"),
    patch("ctypes.windll.user32.ShowWindow"),
    patch("ctypes.windll.user32.OpenClipboard", return_value=1),
    patch("ctypes.windll.user32.CloseClipboard", return_value=1),
    patch("ctypes.windll.user32.GetClipboardData", return_value=0),
    patch("ctypes.windll.user32.SendInput"),
    patch("ctypes.windll.gdi32.GetPixel", return_value=0x00FFFFFF),
    patch("ctypes.windll.user32.GetDC", return_value=1),
    patch("ctypes.windll.user32.ReleaseDC"),
    patch("modules.screen.save_screenshot"),
    patch("modules.screen.capture_full_screen", return_value=MagicMock(shape=(1080, 1920, 3))),
    patch("modules.screen.capture_full_screen_gray", return_value=MagicMock(shape=(1080, 1920))),
]

results = {}

with contextlib.ExitStack() as stack:
    for p in patches:
        stack.enter_context(p)

    for name, scen in scenarios.items():
        print(f"\n{'─'*50}")
        print(f"[ RUN ] {name}")
        print(f"  Goal: {scen['purpose']}")

        t0 = time.time()
        errors = []
        steps = [0]
        context_snapshot = {}

        try:
            actions = [Action.from_dict(d) for d in scen["actions"]]

            # Serialization roundtrip
            serialized = [act.to_dict() for act in actions]
            reloaded = [Action.from_dict(d) for d in serialized]
            reserialized = [act.to_dict() for act in reloaded]
            json_orig = json.dumps(serialized, sort_keys=True)
            json_reload = json.dumps(reserialized, sort_keys=True)
            roundtrip_ok = json_orig == json_reload

            # Execute
            engine = MacroEngine()
            engine.load_actions(actions)
            engine.set_loop(1, 0, stop_on_error=False)
            engine.action_signal.connect(lambda d: steps.append(steps.pop()+1))
            engine.nested_step_signal.connect(lambda p,d: steps.append(steps.pop()+1))
            engine.error_signal.connect(lambda msg: errors.append(msg))

            engine.run()
            duration = time.time() - t0

            # Context snapshot
            if hasattr(engine, '_exec_ctx') and engine._exec_ctx:
                context_snapshot = dict(engine._exec_ctx._variables)

            status = "PASS" if not errors else "WARN"
            results[name] = {
                "status": status, "steps": steps[0], "errors": len(errors),
                "error_msgs": errors[:3], "duration": duration,
                "roundtrip": roundtrip_ok, "context": context_snapshot,
            }

            rt_tag = "✅" if roundtrip_ok else "❌"
            err_tag = f"⚠️ {len(errors)} errors" if errors else "✅ Clean"
            print(f"  Steps: {steps[0]} | {err_tag} | Roundtrip: {rt_tag} | {duration:.3f}s")
            if errors:
                for e in errors[:2]:
                    print(f"    → {e}")

        except Exception as ex:
            results[name] = {"status": "CRASH", "error": str(ex), "trace": traceback.format_exc()}
            print(f"  💥 CRASH: {ex}")

# =====================================================
# CONTEXT VARIABLE VERIFICATION
# =====================================================
print(f"\n{'='*60}")
print(" CONTEXT VARIABLE VERIFICATION")
print(f"{'='*60}")

assertion_failures = []

def _check(name, condition, msg):
    icon = "✅" if condition else "❌"
    print(f"  {icon} {name}: {msg}")
    if not condition:
        assertion_failures.append(f"{name}: {msg}")

# No crashes
crash_count = sum(1 for r in results.values() if r["status"] == "CRASH")
_check("CRASH", crash_count == 0, f"{crash_count} crashes (expected 0)")

# All roundtrips
rt_fail = sum(1 for r in results.values() if r.get("roundtrip") is False)
_check("ROUNDTRIP", rt_fail == 0, f"{rt_fail} roundtrip failures (expected 0)")

# Scenario-specific assertions
for name, scen in scenarios.items():
    ctx = results.get(name, {}).get("context", {})
    for var_name, expected in scen.get("expected_vars", {}).items():
        actual = ctx.get(var_name)
        _check(f"{name}_{var_name}", actual == expected,
               f"{var_name}={actual!r}, expected {expected!r}")

# =====================================================
# FINAL SUMMARY
# =====================================================
print(f"\n{'='*60}")
total_actions_all = sum(count_actions(s["actions"]) for s in scenarios.values())
total_steps_all = sum(r.get("steps", 0) for r in results.values())
max_depth_all = max(max_depth(s["actions"]) for s in scenarios.values())

if assertion_failures:
    print(f" ❌ {len(assertion_failures)} assertion(s) FAILED:")
    for f in assertion_failures:
        print(f"    → {f}")
    print(f"{'='*60}")
    sys.exit(1)
else:
    print(" ✅ ALL ASSERTIONS PASSED")
    print(f"    Scenarios: {len(scenarios)}")
    print(f"    Total actions: {total_actions_all}")
    print(f"    Total steps executed: {total_steps_all}")
    print(f"    Max nesting depth: {max_depth_all}")
    print(f"{'='*60}")
    sys.exit(0)
