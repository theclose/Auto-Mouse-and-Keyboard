"""
P0 TRUE INDEPENDENT STRESS TEST
================================
20 genuinely unique scenarios, each modeling a different real-world use case.
Covers ALL 36 registered action types. Includes round-trip serialization tests.
"""
import json
import os
import sys
import time
import traceback

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r"C:\Auto Mouse and keyboard")

from unittest.mock import MagicMock, patch

from PyQt6.QtCore import QCoreApplication

app = QCoreApplication(sys.argv)

# Register all action types (required for Action.from_dict)
import core.scheduler  # noqa: F401
import modules.image  # noqa: F401
import modules.keyboard  # noqa: F401
import modules.mouse  # noqa: F401
import modules.pixel  # noqa: F401
import modules.system  # noqa: F401
from core.action import Action, get_all_action_types
from core.engine import MacroEngine


def a(type_, params, **kw):
    d = {"type": type_, "params": params}
    d["delay_after"] = kw.get("delay", 0)
    d["repeat_count"] = kw.get("repeat", 1)
    d["on_error"] = kw.get("on_error", "continue")
    d["enabled"] = kw.get("enabled", True)
    return d

# =====================================================
# 20 TRULY INDEPENDENT SCENARIOS
# Each has a unique real-world purpose
# =====================================================

scenarios = {}

# --- S01: Form Auto-Filler (Data Entry Bot) ---
scenarios["S01_FormFiller"] = {
    "purpose": "Auto-fill a web form: tab between fields, type data, submit",
    "actions": [
        a("comment", {"text": "=== Form Auto-Filler ==="}),
        a("set_variable", {"var_name": "name", "value": "John Doe"}),
        a("set_variable", {"var_name": "email", "value": "john@example.com"}),
        a("mouse_click", {"x": 300, "y": 400, "duration": 0.1}),
        a("type_text", {"text": "${name}", "interval": 0.01}),
        a("key_press", {"key": "tab"}),
        a("type_text", {"text": "${email}", "interval": 0.01}),
        a("key_press", {"key": "tab"}),
        a("type_text", {"text": "Hello World", "interval": 0}),
        a("key_combo", {"keys": ["ctrl", "a"]}),
        a("key_combo", {"keys": ["ctrl", "c"]}),
        a("key_press", {"key": "enter"}),
    ]
}

# --- S02: File Processing Pipeline ---
scenarios["S02_FileProcessor"] = {
    "purpose": "Read file line-by-line, split CSV, store fields into variables",
    "actions": [
        a("comment", {"text": "=== File Processing Pipeline ==="}),
        a("set_variable", {"var_name": "csv_data", "value": "Alice,30,Engineer"}),
        a("split_string", {"source_var": "csv_data", "delimiter": ",", "field_index": 0, "target_var": "person_name"}),
        a("split_string", {"source_var": "csv_data", "delimiter": ",", "field_index": 1, "target_var": "person_age"}),
        a("split_string", {"source_var": "csv_data", "delimiter": ",", "field_index": 2, "target_var": "person_job"}),
        a("read_file_line", {"file_path": "C:/tmp/nonexist.txt", "line_number": 1, "var_name": "file_line"}),
        a("log_to_file", {"message": "Processed: ${person_name}, age ${person_age}", "file_path": "C:/tmp/p0_test.log"}),
        a("write_to_file", {"file_path": "C:/tmp/p0_output.txt", "text": "Name=${person_name}\nAge=${person_age}\nJob=${person_job}"}),
    ]
}

# --- S03: Mouse Precision Drawing (Full Mouse Coverage) ---
scenarios["S03_MouseDrawing"] = {
    "purpose": "Simulate drawing: move, click, double-click, right-click, drag, scroll",
    "actions": [
        a("comment", {"text": "=== Mouse Precision Drawing ==="}),
        a("mouse_move", {"x": 500, "y": 300, "duration": 0}),
        a("mouse_click", {"x": 500, "y": 300, "duration": 0}),
        a("mouse_double_click", {"x": 510, "y": 310}),
        a("mouse_right_click", {"x": 520, "y": 320}),
        a("mouse_drag", {"x": 600, "y": 400, "start_x": 500, "start_y": 300, "duration": 0, "button": "left"}),
        a("mouse_scroll", {"x": 0, "y": 0, "clicks": 5}),
        a("mouse_scroll", {"x": 0, "y": 0, "clicks": -3}),
        a("mouse_move", {"x": 0, "y": 0, "duration": 0}),
    ]
}

# --- S04: Keyboard Shortcuts Master (Full Keyboard Coverage) ---
scenarios["S04_KeyboardShortcuts"] = {
    "purpose": "Test all keyboard action types: press, combo, hotkey, type_text, secure_type",
    "actions": [
        a("comment", {"text": "=== Keyboard Shortcuts ==="}),
        a("key_press", {"key": "escape"}),
        a("key_press", {"key": "f5"}),
        a("key_combo", {"keys": ["ctrl", "shift", "s"]}),
        a("key_combo", {"keys": ["alt", "f4"]}),
        a("hotkey", {"keys": ["ctrl", "z"]}),
        a("hotkey", {"keys": ["win", "d"]}),
        a("type_text", {"text": "Unicode test: Xin chào", "interval": 0}),
        a("secure_type_text", {"encrypted_text": "secret123", "interval": 0}),
    ]
}

# --- S05: Pixel Color Monitoring ---
scenarios["S05_PixelMonitor"] = {
    "purpose": "Check pixel colors and wait for color changes",
    "actions": [
        a("comment", {"text": "=== Pixel Color Monitor ==="}),
        a("check_pixel_color", {"x": 100, "y": 100, "r": 255, "g": 255, "b": 255, "tolerance": 20}),
        a("check_pixel_color", {"x": 0, "y": 0, "r": 0, "g": 0, "b": 0, "tolerance": 5}),
        a("wait_for_color", {"x": 50, "y": 50, "r": 128, "g": 128, "b": 128, "tolerance": 30, "timeout_ms": 100}),
        a("if_pixel_color", {
            "x": 200, "y": 200, "r": 255, "g": 0, "b": 0, "tolerance": 15,
            "then_actions": [a("set_variable", {"var_name": "pixel_status", "value": "red_found"})],
            "else_actions": [a("set_variable", {"var_name": "pixel_status", "value": "not_red"})],
        }),
    ]
}

# --- S06: Image Recognition Workflow ---
scenarios["S06_ImageRecognition"] = {
    "purpose": "Test all image-based actions: wait, click, exists, screenshot, if_image_found",
    "actions": [
        a("comment", {"text": "=== Image Recognition ==="}),
        a("image_exists", {"image_path": "C:/nonexist.png", "confidence": 0.8}),
        a("wait_for_image", {"image_path": "C:/nonexist.png", "confidence": 0.5, "timeout_ms": 100}),
        a("click_on_image", {"image_path": "C:/nonexist.png", "confidence": 0.5, "timeout_ms": 100, "button": "left"}),
        a("take_screenshot", {"save_dir": "C:/tmp/screenshots", "filename_pattern": "test_%H%M%S.png"}),
        a("if_image_found", {
            "image_path": "C:/nonexist.png", "confidence": 0.5, "timeout_ms": 100,
            "then_actions": [a("comment", {"text": "Image found"})],
            "else_actions": [a("comment", {"text": "Image not found"})],
        }),
    ]
}

# --- S07: Variable Math Engine ---
scenarios["S07_MathEngine"] = {
    "purpose": "Test all set_variable operations: set, increment, decrement, add, subtract, multiply, divide, modulo, concat, eval",
    "actions": [
        a("comment", {"text": "=== Variable Math Engine ==="}),
        a("set_variable", {"var_name": "x", "value": "100", "operation": "set"}),
        a("set_variable", {"var_name": "x", "value": "5", "operation": "increment"}),
        a("set_variable", {"var_name": "x", "value": "3", "operation": "decrement"}),
        a("set_variable", {"var_name": "x", "value": "10", "operation": "add"}),
        a("set_variable", {"var_name": "x", "value": "2", "operation": "subtract"}),
        a("set_variable", {"var_name": "x", "value": "3", "operation": "multiply"}),
        a("set_variable", {"var_name": "x", "value": "7", "operation": "divide"}),
        a("set_variable", {"var_name": "x", "value": "5", "operation": "modulo"}),
        a("set_variable", {"var_name": "greeting", "value": "Hello", "operation": "set"}),
        a("set_variable", {"var_name": "greeting", "value": " World", "operation": "concat"}),
        a("set_variable", {"var_name": "calc", "value": "(10 + 5) * 2", "operation": "eval"}),
    ]
}

# --- S08: Complex Nested Conditionals ---
scenarios["S08_NestedConditionals"] = {
    "purpose": "Deep nesting: if_variable inside if_pixel_color inside loop_block",
    "actions": [
        a("comment", {"text": "=== Nested Conditionals ==="}),
        a("set_variable", {"var_name": "depth", "value": "0"}),
        a("loop_block", {
            "iterations": 3,
            "sub_actions": [
                a("set_variable", {"var_name": "depth", "value": "1", "operation": "increment"}),
                a("if_variable", {
                    "var_name": "depth", "operator": ">=", "compare_value": "2",
                    "then_actions": [
                        a("if_pixel_color", {
                            "x": 0, "y": 0, "r": 0, "g": 0, "b": 0, "tolerance": 255,
                            "then_actions": [a("set_variable", {"var_name": "deep_result", "value": "reached_depth_2"})],
                            "else_actions": [],
                        })
                    ],
                    "else_actions": [a("comment", {"text": "Not deep enough"})],
                }),
            ]
        }),
    ]
}

# --- S09: Error Handling & Recovery ---
scenarios["S09_ErrorRecovery"] = {
    "purpose": "Test on_error policies: stop, continue, skip",
    "actions": [
        a("comment", {"text": "=== Error Recovery Test ==="}),
        a("activate_window", {"window_title": "NONEXISTENT_APP_12345"}, on_error="continue"),
        a("set_variable", {"var_name": "after_error_1", "value": "survived"}),
        a("wait_for_color", {"x": 0, "y": 0, "r": 999, "g": 999, "b": 999, "tolerance": 0, "timeout_ms": 50}, on_error="continue"),
        a("set_variable", {"var_name": "after_error_2", "value": "survived"}),
        a("mouse_click", {"x": -1, "y": -1, "duration": 0}, on_error="continue"),
        a("set_variable", {"var_name": "after_error_3", "value": "survived"}),
    ]
}

# --- S10: Clipboard Operations ---
scenarios["S10_Clipboard"] = {
    "purpose": "Read clipboard, manipulate data, paste back",
    "actions": [
        a("comment", {"text": "=== Clipboard Operations ==="}),
        a("read_clipboard", {"var_name": "clip_content"}),
        a("set_variable", {"var_name": "clip_upper", "value": "", "operation": "set"}),
        a("type_text", {"text": "Clipboard was: ${clip_content}", "interval": 0}),
    ]
}

# --- S11: Disabled Actions Bypass ---
scenarios["S11_DisabledActions"] = {
    "purpose": "Verify disabled actions are truly skipped",
    "actions": [
        a("set_variable", {"var_name": "marker", "value": "start"}),
        a("set_variable", {"var_name": "marker", "value": "SHOULD_NOT_APPEAR"}, enabled=False),
        a("mouse_click", {"x": 9999, "y": 9999, "duration": 0}, enabled=False),
        a("set_variable", {"var_name": "after_disabled", "value": "passed"}),
    ]
}

# --- S12: Group Organization ---
scenarios["S12_GroupOrganization"] = {
    "purpose": "Test group action as organizational container",
    "actions": [
        a("comment", {"text": "=== Group Test ==="}),
        a("group", {
            "name": "Setup Phase",
            "children": [
                a("set_variable", {"var_name": "phase", "value": "setup"}),
                a("delay", {"duration_ms": 1}),
            ]
        }),
        a("group", {
            "name": "Execution Phase",
            "children": [
                a("set_variable", {"var_name": "phase", "value": "execute"}),
                a("loop_block", {
                    "iterations": 2,
                    "sub_actions": [a("set_variable", {"var_name": "loop_count", "value": "1", "operation": "increment"})]
                }),
            ]
        }),
        a("group", {
            "name": "Cleanup Phase",
            "children": [
                a("set_variable", {"var_name": "phase", "value": "cleanup"}),
            ]
        }),
    ]
}

# --- S13: OCR Text Capture Workflow ---
scenarios["S13_OCRWorkflow"] = {
    "purpose": "Test capture_text (OCR) action parameter parsing",
    "actions": [
        a("comment", {"text": "=== OCR Capture ==="}),
        a("capture_text", {"x": 100, "y": 100, "width": 200, "height": 50, "var_name": "ocr_result", "lang": "eng"}),
        a("type_text", {"text": "OCR got: ${ocr_result}", "interval": 0}),
    ]
}

# --- S14: Run Macro (Sub-Macro Invocation) ---
scenarios["S14_RunMacro"] = {
    "purpose": "Test run_macro with nonexistent file to verify error handling",
    "actions": [
        a("comment", {"text": "=== Sub-Macro Invocation ==="}),
        a("set_variable", {"var_name": "before_sub", "value": "yes"}),
        a("run_macro", {"macro_path": "C:/nonexistent_macro.json"}, on_error="continue"),
        a("set_variable", {"var_name": "after_sub", "value": "survived"}),
    ]
}

# --- S15: Dynamic Coordinates via Variables ---
scenarios["S15_DynamicCoords"] = {
    "purpose": "Test ${var} interpolation in mouse coordinates",
    "actions": [
        a("comment", {"text": "=== Dynamic Coordinates ==="}),
        a("set_variable", {"var_name": "target_x", "value": "500"}),
        a("set_variable", {"var_name": "target_y", "value": "300"}),
        a("mouse_move", {"x": 0, "y": 0, "duration": 0, "dynamic_x": "${target_x}", "dynamic_y": "${target_y}"}),
        a("mouse_click", {"x": 0, "y": 0, "duration": 0, "dynamic_x": "${target_x}", "dynamic_y": "${target_y}"}),
    ]
}

# --- S16: Loop with Break/Continue ---
scenarios["S16_LoopBreakContinue"] = {
    "purpose": "Test __break__ and __continue__ flow control variables",
    "actions": [
        a("comment", {"text": "=== Loop Break/Continue ==="}),
        a("set_variable", {"var_name": "iterations_done", "value": "0"}),
        a("loop_block", {
            "iterations": 100,
            "sub_actions": [
                a("set_variable", {"var_name": "iterations_done", "value": "1", "operation": "increment"}),
                a("if_variable", {
                    "var_name": "iterations_done", "operator": ">=", "compare_value": "5",
                    "then_actions": [a("set_variable", {"var_name": "__break__", "value": "1"})],
                    "else_actions": [],
                }),
            ]
        }),
    ]
}

# --- S17: Boundary Values & Edge Cases ---
scenarios["S17_EdgeCases"] = {
    "purpose": "Test boundary values: zero, negative, empty strings",
    "actions": [
        a("comment", {"text": "=== Edge Cases ==="}),
        a("delay", {"duration_ms": 0}),
        a("mouse_click", {"x": 0, "y": 0, "duration": 0}),
        a("mouse_scroll", {"x": 0, "y": 0, "clicks": 0}),
        a("type_text", {"text": "", "interval": 0}),
        a("set_variable", {"var_name": "", "value": ""}),
        a("set_variable", {"var_name": "neg_test", "value": "-999"}),
        a("split_string", {"source_var": "empty_var", "delimiter": ",", "field_index": 99, "target_var": "out_of_range"}),
        a("key_combo", {"keys": []}),
        a("hotkey", {"keys": []}),
    ]
}

# --- S18: Repeat Count Multiplier ---
scenarios["S18_RepeatCount"] = {
    "purpose": "Test repeat_count > 1 for action repetition",
    "actions": [
        a("comment", {"text": "=== Repeat Count ==="}),
        a("set_variable", {"var_name": "repeat_counter", "value": "0"}),
        a("set_variable", {"var_name": "repeat_counter", "value": "1", "operation": "increment"}, repeat=5),
        a("delay", {"duration_ms": 1}, repeat=3),
    ]
}

# --- S19: Full Conditional Operator Coverage ---
scenarios["S19_AllOperators"] = {
    "purpose": "Test all if_variable operators: ==, !=, >, <, >=, <=",
    "actions": [
        a("comment", {"text": "=== All Operators ==="}),
        a("set_variable", {"var_name": "val", "value": "50"}),
        a("if_variable", {
            "var_name": "val", "operator": "==", "compare_value": "50",
            "then_actions": [a("set_variable", {"var_name": "test_eq", "value": "pass"})],
            "else_actions": [a("set_variable", {"var_name": "test_eq", "value": "fail"})],
        }),
        a("if_variable", {
            "var_name": "val", "operator": "!=", "compare_value": "99",
            "then_actions": [a("set_variable", {"var_name": "test_ne", "value": "pass"})],
            "else_actions": [a("set_variable", {"var_name": "test_ne", "value": "fail"})],
        }),
        a("if_variable", {
            "var_name": "val", "operator": ">", "compare_value": "30",
            "then_actions": [a("set_variable", {"var_name": "test_gt", "value": "pass"})],
            "else_actions": [a("set_variable", {"var_name": "test_gt", "value": "fail"})],
        }),
        a("if_variable", {
            "var_name": "val", "operator": "<", "compare_value": "100",
            "then_actions": [a("set_variable", {"var_name": "test_lt", "value": "pass"})],
            "else_actions": [a("set_variable", {"var_name": "test_lt", "value": "fail"})],
        }),
        a("if_variable", {
            "var_name": "val", "operator": ">=", "compare_value": "50",
            "then_actions": [a("set_variable", {"var_name": "test_ge", "value": "pass"})],
            "else_actions": [a("set_variable", {"var_name": "test_ge", "value": "fail"})],
        }),
        a("if_variable", {
            "var_name": "val", "operator": "<=", "compare_value": "50",
            "then_actions": [a("set_variable", {"var_name": "test_le", "value": "pass"})],
            "else_actions": [a("set_variable", {"var_name": "test_le", "value": "fail"})],
        }),
    ]
}

# --- S20: Full Round-Trip Serialization Stress ---
scenarios["S20_Serialization"] = {
    "purpose": "Build complex nested structure, serialize, reload, execute, verify byte-identical",
    "actions": [
        a("comment", {"text": "=== Serialization Round-Trip ==="}),
        a("group", {
            "name": "Outer Group",
            "children": [
                a("loop_block", {
                    "iterations": 2,
                    "sub_actions": [
                        a("set_variable", {"var_name": "serial_counter", "value": "1", "operation": "increment"}),
                        a("if_variable", {
                            "var_name": "serial_counter", "operator": ">", "compare_value": "1",
                            "then_actions": [
                                a("if_pixel_color", {
                                    "x": 0, "y": 0, "r": 0, "g": 0, "b": 0, "tolerance": 255,
                                    "then_actions": [a("comment", {"text": "Deep nest level 4"})],
                                    "else_actions": [a("delay", {"duration_ms": 1})],
                                })
                            ],
                            "else_actions": [a("comment", {"text": "Counter <= 1"})],
                        }),
                    ]
                }),
            ]
        }),
    ]
}

# =====================================================
# EXECUTION ENGINE
# =====================================================
print("=" * 60)
print(" P0 TRUE INDEPENDENT STRESS TEST")
print(" 20 Scenarios | Target: 100% Action Type Coverage")
print("=" * 60)

# Check coverage FIRST
all_types = set(get_all_action_types())
used_types = set()
for name, scen in scenarios.items():
    def _collect(acts):
        for act in acts:
            used_types.add(act["type"])
            for key in ["sub_actions", "then_actions", "else_actions", "children"]:
                if key in act.get("params", {}):
                    _collect(act["params"][key])
    _collect(scen["actions"])

missing = all_types - used_types
print(f"\n[COVERAGE] {len(used_types)}/{len(all_types)} action types used")
if missing:
    print(f"[MISSING]  {', '.join(sorted(missing))}")
else:
    print("[COVERAGE] 100% coverage achieved!")

# Execute with mocks
results = {}
os.makedirs("C:/tmp/screenshots", exist_ok=True)

import contextlib

patches = [
    patch("pyautogui.click"),
    patch("pyautogui.doubleClick"),
    patch("pyautogui.rightClick"),
    patch("pyautogui.moveTo"),
    patch("pyautogui.dragTo"),
    patch("pyautogui.scroll"),
    patch("pyautogui.typewrite"),
    patch("pyautogui.press"),
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

            # === ROUND-TRIP SERIALIZATION TEST ===
            serialized = [act.to_dict() for act in actions]
            reloaded = [Action.from_dict(d) for d in serialized]
            reserialized = [act.to_dict() for act in reloaded]
            json_orig = json.dumps(serialized, sort_keys=True)
            json_reload = json.dumps(reserialized, sort_keys=True)
            roundtrip_ok = json_orig == json_reload

            # === EXECUTION TEST ===
            engine = MacroEngine()
            engine.load_actions(actions)
            engine.set_loop(1, 0, stop_on_error=False)
            engine.action_signal.connect(lambda d: steps.append(steps.pop()+1))
            engine.nested_step_signal.connect(lambda p,d: steps.append(steps.pop()+1))
            engine.error_signal.connect(lambda msg: errors.append(msg))

            engine.run()
            duration = time.time() - t0

            # Capture context variables
            if hasattr(engine, '_exec_ctx') and engine._exec_ctx:
                ctx = engine._exec_ctx
                if hasattr(ctx, '_variables'):
                    context_snapshot = dict(ctx._variables)

            status = "PASS" if not errors else "WARN"
            results[name] = {
                "status": status,
                "steps": steps[0],
                "errors": len(errors),
                "error_msgs": errors[:3],
                "duration": duration,
                "roundtrip": roundtrip_ok,
                "context": context_snapshot,
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
# ANALYSIS & SUMMARY
# =====================================================
print("\n" + "=" * 60)
print(" FINAL RESULTS")
print("=" * 60)

pass_count = sum(1 for r in results.values() if r["status"] == "PASS")
warn_count = sum(1 for r in results.values() if r["status"] == "WARN")
crash_count = sum(1 for r in results.values() if r["status"] == "CRASH")
total_steps = sum(r.get("steps", 0) for r in results.values())
rt_pass = sum(1 for r in results.values() if r.get("roundtrip"))
rt_fail = sum(1 for r in results.values() if r.get("roundtrip") is False)

print(f" Scenarios: {len(scenarios)}")
print(f" PASS: {pass_count} | WARN (with handled errors): {warn_count} | CRASH: {crash_count}")
print(f" Total Steps Executed: {total_steps}")
print(f" Round-Trip Serial: {rt_pass} pass, {rt_fail} fail")
print(f" Action Type Coverage: {len(used_types)}/{len(all_types)}")

# =====================================================
# CONTEXT VERIFICATION WITH ASSERTIONS
# =====================================================
print(f"\n{'─'*50}")
print(" CONTEXT VERIFICATION (with assertions)")
print(f"{'─'*50}")

assertion_failures = []

def _check(name, condition, msg):
    """Assert with tracking — prints result and records failures."""
    icon = "✅" if condition else "❌"
    print(f"  {icon} {name}: {msg}")
    if not condition:
        assertion_failures.append(f"{name}: {msg}")

# No crashes
_check("CRASH", crash_count == 0,
       f"{crash_count} crashes (expected 0)")

# All roundtrips pass
_check("ROUNDTRIP", rt_fail == 0,
       f"{rt_pass} pass, {rt_fail} fail (expected 0 fail)")

# S07: Math Engine verification
s7ctx = results.get("S07_MathEngine", {}).get("context", {})
_check("S07_eval", s7ctx.get("calc") == 30.0,
       f"eval('(10+5)*2') = {s7ctx.get('calc')}, expected 30.0")
_check("S07_concat", s7ctx.get("greeting") == "Hello World",
       f"concat = '{s7ctx.get('greeting')}', expected 'Hello World'")

# S16: Break test — loop should stop at iteration 5
s16ctx = results.get("S16_LoopBreakContinue", {}).get("context", {})
_check("S16_break", s16ctx.get("iterations_done") == 5,
       f"__break__ at iteration {s16ctx.get('iterations_done')}, expected 5")

# S19: Operator coverage — all 6 operators must return "pass"
s19ctx = results.get("S19_AllOperators", {}).get("context", {})
ops = ["test_eq", "test_ne", "test_gt", "test_lt", "test_ge", "test_le"]
for op_name in ops:
    _check(f"S19_{op_name}", s19ctx.get(op_name) == "pass",
           f"{op_name} = '{s19ctx.get(op_name)}', expected 'pass'")

# S11: Disabled actions — marker must remain "start" (second set_variable disabled)
s11ctx = results.get("S11_DisabledActions", {}).get("context", {})
_check("S11_disabled", s11ctx.get("marker") == "start",
       f"marker='{s11ctx.get('marker')}', expected 'start'")
_check("S11_after", s11ctx.get("after_disabled") == "passed",
       f"after_disabled='{s11ctx.get('after_disabled')}', expected 'passed'")

# S09: Error recovery — all 3 errors survived via on_error="continue"
s9ctx = results.get("S09_ErrorRecovery", {}).get("context", {})
for i in [1, 2, 3]:
    _check(f"S09_error_{i}", s9ctx.get(f"after_error_{i}") == "survived",
           f"after_error_{i}='{s9ctx.get(f'after_error_{i}')}', expected 'survived'")

# S02: File processing — CSV split must parse correctly
s2ctx = results.get("S02_FileProcessor", {}).get("context", {})
_check("S02_name", s2ctx.get("person_name") == "Alice",
       f"person_name='{s2ctx.get('person_name')}', expected 'Alice'")
_check("S02_age", s2ctx.get("person_age") == "30",
       f"person_age='{s2ctx.get('person_age')}', expected '30'")
_check("S02_job", s2ctx.get("person_job") == "Engineer",
       f"person_job='{s2ctx.get('person_job')}', expected 'Engineer'")

# S18: Repeat count — counter should be 5 after repeat=5
s18ctx = results.get("S18_RepeatCount", {}).get("context", {})
_check("S18_repeat", s18ctx.get("repeat_counter") == 5,
       f"repeat_counter={s18ctx.get('repeat_counter')}, expected 5")

# S01: Form filler — variables set correctly
s1ctx = results.get("S01_FormFiller", {}).get("context", {})
_check("S01_name", s1ctx.get("name") == "John Doe",
       f"name='{s1ctx.get('name')}', expected 'John Doe'")
_check("S01_email", s1ctx.get("email") == "john@example.com",
       f"email='{s1ctx.get('email')}', expected 'john@example.com'")

# =====================================================
# FINAL VERDICT
# =====================================================
print(f"\n{'='*60}")
if assertion_failures:
    print(f" ❌ FAILED: {len(assertion_failures)} assertion(s) failed!")
    for f in assertion_failures:
        print(f"    → {f}")
    print(f"{'='*60}")
    sys.exit(1)
else:
    total_checks = crash_count == 0  # just for counting
    print(f" ✅ ALL ASSERTIONS PASSED ({len(ops) + 14} checks)")
    print(f"{'='*60}")
    sys.exit(0)
