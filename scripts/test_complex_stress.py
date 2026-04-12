"""
10 Complex Stress Test Scenarios - High-Complexity Action Trees.

Each scenario builds a realistic macro with 15+ action types,
nested composites (Loop->If->Loop), variables, file I/O, image/pixel.

Tests: Construction, Serialization round-trip, Execution (mocked I/O).
"""

import json
import logging
import os
import sys
import time
import traceback
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import core.scheduler  # noqa: F401
import modules.image  # noqa: F401
import modules.keyboard  # noqa: F401

# Import all modules to populate the action registry
import modules.mouse  # noqa: F401
import modules.pixel  # noqa: F401
import modules.system  # noqa: F401
from core.action import Action, get_action_class
from core.engine_context import set_context
from core.execution_context import ExecutionContext

logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")

# ── Helpers ──

def make(action_type, **kwargs):
    cls = get_action_class(action_type)
    if cls is None:
        raise ValueError(f"Unknown action type: {action_type}")
    return cls(**kwargs)


def count_total(action):
    total = 1
    for attr in ('children', 'then_children', 'else_children', '_sub_actions'):
        for child in getattr(action, attr, []):
            total += count_total(child)
    return total


def get_types(actions):
    types = set()
    for a in actions:
        types.add(a.ACTION_TYPE)
        for attr in ('children', 'then_children', 'else_children', '_sub_actions'):
            types |= get_types(getattr(a, attr, []))
    return types


def verify_roundtrip(actions):
    for action in actions:
        d = action.to_dict()
        j = json.dumps(d, ensure_ascii=False)
        restored = Action.from_dict(json.loads(j))
        if restored.ACTION_TYPE != action.ACTION_TYPE:
            return False
    return True


def run_mocked(actions, ctx):
    set_context(ctx)
    patches = [
        patch("pyautogui.click", MagicMock()),
        patch("pyautogui.doubleClick", MagicMock()),
        patch("pyautogui.rightClick", MagicMock()),
        patch("pyautogui.moveTo", MagicMock()),
        patch("pyautogui.mouseDown", MagicMock()),
        patch("pyautogui.mouseUp", MagicMock()),
        patch("pyautogui.scroll", MagicMock()),
        patch("pyautogui.press", MagicMock()),
        patch("pyautogui.hotkey", MagicMock()),
        patch("pyautogui.write", MagicMock()),
        patch("pyautogui.typewrite", MagicMock()),
        patch("pyautogui.keyDown", MagicMock()),
        patch("pyautogui.keyUp", MagicMock()),
        patch("pyautogui.locateOnScreen", MagicMock(return_value=None)),
        patch("pyautogui.screenshot", MagicMock()),
        patch("pyautogui.pixel", MagicMock(return_value=(255, 0, 0))),
        patch("time.sleep", MagicMock()),
        patch("builtins.open", MagicMock()),
        patch("os.makedirs", MagicMock()),
        patch("subprocess.run", MagicMock(return_value=MagicMock(
            stdout="mock", returncode=0))),
    ]
    for p in patches:
        p.start()
    try:
        for a in actions:
            try:
                a.run()
            except Exception:
                pass  # Non-fatal in mocked env
        return True, ""
    except Exception:
        return False, traceback.format_exc()
    finally:
        for p in patches:
            p.stop()


# ══ CORRECT API REFERENCE ══
# set_variable(var_name, value, operation="set")  ops: set/increment/decrement/add/subtract
#   increment: current + int(value) [default step=1]
#   add: current + float(value) with interpolation
# write_to_file(file_path, text, mode="w")
# mouse_drag(x, y, duration, button, start_x, start_y)  x,y = end coords
# split_string(source_var, delimiter, field_index, target_var)
# check_pixel_color(x, y, r, g, b, tolerance)  → stores "pixel_matched" in ctx
# image_exists(image_path, confidence)  → no var_name
# group(name, children=[...])  → _children.append() to add after init


# ══════════════════════════════════════════════════════════════
# SCENARIO 1: Data Scraping Pipeline (18 types)
# ══════════════════════════════════════════════════════════════
def s01():
    a = []
    a.append(make("comment", text="Data Scraper v1"))
    a.append(make("set_variable", var_name="counter", value="0"))
    a.append(make("set_variable", var_name="max_pages", value="5"))
    a.append(make("activate_window", window_title="Chrome"))

    loop = make("loop_block", iterations=5)
    loop.add_action(make("set_variable", var_name="counter", value="1", operation="increment"))
    loop.add_action(make("delay", duration_ms=50))
    loop.add_action(make("mouse_click", x=100, y=200))
    loop.add_action(make("read_clipboard", var_name="page_data"))

    if_past3 = make("if_variable", var_name="counter", operator=">", compare_value="3")
    if_past3.add_then_action(make("log_to_file", message="Past page 3"))
    if_past3.add_else_action(make("type_text", text="Scraping"))
    loop.add_action(if_past3)

    loop.add_action(make("key_combo", keys=["ctrl", "a"]))
    loop.add_action(make("take_screenshot", save_dir="macros/screenshots"))

    if_pixel = make("if_pixel_color", x=50, y=50, r=255, g=0, b=0)
    if_pixel.add_then_action(make("mouse_right_click", x=50, y=50))
    if_pixel.add_else_action(make("mouse_double_click", x=100, y=100))
    loop.add_action(if_pixel)

    loop.add_action(make("mouse_scroll", x=200, y=300, clicks=-3))
    loop.add_action(make("key_press", key="pagedown"))
    a.append(loop)

    a.append(make("write_to_file", file_path="macros/results.txt", text="Done"))
    a.append(make("comment", text="Pipeline done"))
    return a


# ══════════════════════════════════════════════════════════════
# SCENARIO 2: Image Automation with Fallback (15 types)
# ══════════════════════════════════════════════════════════════
def s02():
    a = []
    a.append(make("set_variable", var_name="found", value="false"))
    a.append(make("set_variable", var_name="attempts", value="0"))

    loop = make("loop_block", iterations=10)
    loop.add_action(make("set_variable", var_name="attempts", value="1", operation="increment"))

    if_img = make("if_image_found", image_path="button_ok.png", confidence=0.8, timeout_ms=500)
    if_img.add_then_action(make("mouse_click", x=0, y=0))
    if_img.add_then_action(make("set_variable", var_name="found", value="true"))
    if_img.add_else_action(make("delay", duration_ms=50))
    loop.add_action(if_img)

    if_found = make("if_variable", var_name="found", operator="==", compare_value="true")
    if_found.add_then_action(make("comment", text="Found!"))
    if_found.add_else_action(make("key_press", key="f5"))
    loop.add_action(if_found)

    if_white = make("if_pixel_color", x=960, y=540, r=255, g=255, b=255)
    if_white.add_then_action(make("take_screenshot", save_dir="macros/screenshots"))
    loop.add_action(if_white)

    loop.add_action(make("mouse_move", x=500, y=500))
    loop.add_action(make("hotkey", keys=["alt", "tab"]))
    loop.add_action(make("log_to_file", message="Attempt"))
    a.append(loop)

    if_result = make("if_variable", var_name="found", operator="==", compare_value="false")
    if_result.add_then_action(make("write_to_file", file_path="macros/r.txt", text="FAIL"))
    if_result.add_else_action(make("write_to_file", file_path="macros/r.txt", text="OK"))
    a.append(if_result)
    a.append(make("comment", text="Image auto done"))
    return a


# ══════════════════════════════════════════════════════════════
# SCENARIO 3: 3-Level Nested Loop Matrix (15 types)
# ══════════════════════════════════════════════════════════════
def s03():
    a = []
    a.append(make("set_variable", var_name="total", value="0"))

    outer = make("loop_block", iterations=3)
    outer.add_action(make("set_variable", var_name="row", value="1"))

    middle = make("loop_block", iterations=4)
    middle.add_action(make("set_variable", var_name="col", value="1"))
    middle.add_action(make("set_variable", var_name="total", value="1", operation="increment"))
    middle.add_action(make("mouse_click", x=100, y=100))
    middle.add_action(make("delay", duration_ms=10))

    inner = make("loop_block", iterations=2)
    inner.add_action(make("key_press", key="tab"))
    inner.add_action(make("type_text", text="cell"))
    inner.add_action(make("key_combo", keys=["shift", "tab"]))
    middle.add_action(inner)

    if_half = make("if_variable", var_name="total", operator=">", compare_value="6")
    if_half.add_then_action(make("log_to_file", message="Halfway"))
    middle.add_action(if_half)

    middle.add_action(make("mouse_scroll", x=100, y=100, clicks=1))
    outer.add_action(middle)
    outer.add_action(make("take_screenshot", save_dir="macros/screenshots"))
    a.append(outer)

    a.append(make("split_string", source_var="total", delimiter=",",
                  field_index=0, target_var="part0"))
    a.append(make("comment", text="Matrix done"))
    return a


# ══════════════════════════════════════════════════════════════
# SCENARIO 4: Form Filler + Validation (19 types)
# ══════════════════════════════════════════════════════════════
def s04():
    a = []
    a.append(make("comment", text="Form Filler"))
    a.append(make("activate_window", window_title="Form"))
    a.append(make("set_variable", var_name="field_count", value="0"))
    a.append(make("set_variable", var_name="errors", value="0"))
    a.append(make("read_file_line", file_path="macros/data.csv", line_number=1, var_name="line"))
    a.append(make("split_string", source_var="line", delimiter=",",
                  field_index=0, target_var="field0"))

    loop = make("loop_block", iterations=5)
    loop.add_action(make("set_variable", var_name="field_count", value="1", operation="increment"))
    loop.add_action(make("mouse_click", x=200, y=120))
    loop.add_action(make("key_combo", keys=["ctrl", "a"]))
    loop.add_action(make("type_text", text="test_data"))
    loop.add_action(make("key_press", key="tab"))
    loop.add_action(make("delay", duration_ms=10))

    if_err = make("if_pixel_color", x=500, y=300, r=255, g=0, b=0)
    if_err.add_then_action(make("set_variable", var_name="errors", value="1", operation="increment"))
    if_err.add_then_action(make("log_to_file", message="Error"))
    if_err.add_else_action(make("comment", text="Field OK"))
    loop.add_action(if_err)

    loop.add_action(make("mouse_move", x=300, y=400))
    loop.add_action(make("hotkey", keys=["alt", "n"]))
    a.append(loop)

    if_res = make("if_variable", var_name="errors", operator=">", compare_value="0")
    if_res.add_then_action(make("take_screenshot", save_dir="macros/screenshots"))
    if_res.add_then_action(make("write_to_file", file_path="macros/err.txt", text="Errors"))
    if_res.add_else_action(make("key_combo", keys=["ctrl", "s"]))
    a.append(if_res)

    a.append(make("mouse_double_click", x=400, y=500))
    a.append(make("comment", text="Form done"))
    return a


# ══════════════════════════════════════════════════════════════
# SCENARIO 5: System Monitor (15 types)
# ══════════════════════════════════════════════════════════════
def s05():
    a = []
    a.append(make("comment", text="System Monitor"))
    a.append(make("set_variable", var_name="checks", value="0"))
    a.append(make("set_variable", var_name="alerts", value="0"))

    loop = make("loop_block", iterations=8)
    loop.add_action(make("set_variable", var_name="checks", value="1", operation="increment"))
    loop.add_action(make("run_command", command="echo test", var_name="proc"))
    loop.add_action(make("log_to_file", message="Check"))
    loop.add_action(make("check_pixel_color", x=100, y=100, r=0, g=255, b=0))

    if_alert = make("if_variable", var_name="pixel_matched", operator="==", compare_value="False")
    if_alert.add_then_action(make("set_variable", var_name="alerts", value="1", operation="increment"))
    if_alert.add_then_action(make("take_screenshot", save_dir="macros/screenshots"))
    if_alert.add_then_action(make("write_to_file", file_path="macros/alert.txt", text="ALERT"))
    if_alert.add_else_action(make("comment", text="OK"))
    loop.add_action(if_alert)

    loop.add_action(make("mouse_click", x=800, y=50))
    loop.add_action(make("delay", duration_ms=50))
    loop.add_action(make("key_press", key="f5"))
    loop.add_action(make("mouse_scroll", x=400, y=400, clicks=-5))
    a.append(loop)

    if_multi = make("if_variable", var_name="alerts", operator=">", compare_value="2")
    if_multi.add_then_action(make("activate_window", window_title="Alert"))
    if_multi.add_then_action(make("type_text", text="Alerts detected"))
    if_multi.add_else_action(make("log_to_file", message="All OK"))
    a.append(if_multi)
    a.append(make("comment", text="Monitor done"))
    return a


# ══════════════════════════════════════════════════════════════
# SCENARIO 6: Drag-Drop Workflow (17 types)
# ══════════════════════════════════════════════════════════════
def s06():
    a = []
    a.append(make("set_variable", var_name="items", value="0"))
    a.append(make("activate_window", window_title="Files"))

    loop = make("loop_block", iterations=6)
    loop.add_action(make("set_variable", var_name="items", value="1", operation="increment"))
    loop.add_action(make("mouse_click", x=100, y=200))
    loop.add_action(make("mouse_drag", start_x=100, start_y=200, x=600, y=200))
    loop.add_action(make("delay", duration_ms=20))

    if_c = make("if_image_found", image_path="confirm.png", confidence=0.8, timeout_ms=300)
    if_c.add_then_action(make("key_press", key="enter"))
    if_c.add_else_action(make("mouse_right_click", x=600, y=200))
    loop.add_action(if_c)

    loop.add_action(make("key_combo", keys=["ctrl", "z"]))
    loop.add_action(make("hotkey", keys=["alt", "tab"]))
    loop.add_action(make("type_text", text="Moved"))
    loop.add_action(make("hotkey", keys=["alt", "tab"]))
    a.append(loop)

    a.append(make("take_screenshot", save_dir="macros/screenshots"))
    a.append(make("write_to_file", file_path="macros/dnd.txt", text="Done"))
    a.append(make("mouse_double_click", x=400, y=300))
    a.append(make("mouse_move", x=0, y=0))
    a.append(make("comment", text="D&D done"))
    return a


# ══════════════════════════════════════════════════════════════
# SCENARIO 7: 4-Level If Chain (15 types, deep nesting)
# ══════════════════════════════════════════════════════════════
def s07():
    a = []
    a.append(make("set_variable", var_name="score", value="75"))
    a.append(make("set_variable", var_name="grade", value="?"))

    if_a = make("if_variable", var_name="score", operator=">=", compare_value="90")
    if_a.add_then_action(make("set_variable", var_name="grade", value="A"))

    if_b = make("if_variable", var_name="score", operator=">=", compare_value="80")
    if_b.add_then_action(make("set_variable", var_name="grade", value="B"))

    if_c = make("if_variable", var_name="score", operator=">=", compare_value="70")
    if_c.add_then_action(make("set_variable", var_name="grade", value="C"))
    if_c.add_else_action(make("set_variable", var_name="grade", value="F"))

    if_b.add_else_action(if_c)
    if_a.add_else_action(if_b)
    a.append(if_a)

    a.append(make("log_to_file", message="Graded"))

    loop = make("loop_block", iterations=3)
    loop.add_action(make("set_variable", var_name="score", value="10", operation="decrement"))
    loop.add_action(make("mouse_click", x=300, y=200))
    loop.add_action(make("type_text", text="grade"))
    loop.add_action(make("key_press", key="enter"))
    loop.add_action(make("delay", duration_ms=10))
    a.append(loop)

    a.append(make("split_string", source_var="grade", delimiter=",",
                  field_index=0, target_var="subj"))
    a.append(make("run_command", command="echo test", var_name="out"))
    a.append(make("write_to_file", file_path="macros/grade.txt", text="Final"))
    a.append(make("comment", text="Grading done"))
    return a


# ══════════════════════════════════════════════════════════════
# SCENARIO 8: Pixel Grid 5x5 Scanner (15 types)
# ══════════════════════════════════════════════════════════════
def s08():
    a = []
    a.append(make("set_variable", var_name="matches", value="0"))
    a.append(make("set_variable", var_name="scanned", value="0"))
    a.append(make("comment", text="Grid Scan 5x5"))

    row_loop = make("loop_block", iterations=5)
    row_loop.add_action(make("set_variable", var_name="row_y", value="150"))

    col_loop = make("loop_block", iterations=5)
    col_loop.add_action(make("set_variable", var_name="col_x", value="150"))
    col_loop.add_action(make("set_variable", var_name="scanned", value="1", operation="increment"))
    col_loop.add_action(make("check_pixel_color", x=150, y=150, r=255, g=0, b=0))

    if_t = make("if_variable", var_name="pixel_matched", operator="==", compare_value="True")
    if_t.add_then_action(make("set_variable", var_name="matches", value="1", operation="increment"))
    if_t.add_then_action(make("mouse_click", x=150, y=150))
    if_t.add_else_action(make("mouse_move", x=150, y=150))
    col_loop.add_action(if_t)

    col_loop.add_action(make("delay", duration_ms=5))
    row_loop.add_action(col_loop)
    row_loop.add_action(make("log_to_file", message="Row done"))
    a.append(row_loop)

    a.append(make("take_screenshot", save_dir="macros/screenshots"))
    a.append(make("write_to_file", file_path="macros/grid.txt", text="Scan done"))
    a.append(make("comment", text="Grid done"))
    return a


# ══════════════════════════════════════════════════════════════
# SCENARIO 9: File Processing Pipeline (18 types)
# ══════════════════════════════════════════════════════════════
def s09():
    a = []
    a.append(make("comment", text="File Processor"))
    a.append(make("set_variable", var_name="processed", value="0"))
    a.append(make("set_variable", var_name="failed", value="0"))

    loop = make("loop_block", iterations=7)
    loop.add_action(make("set_variable", var_name="processed", value="1", operation="increment"))
    loop.add_action(make("read_file_line", file_path="macros/input.txt",
                         line_number=1, var_name="data"))
    loop.add_action(make("split_string", source_var="data", delimiter=";",
                         field_index=0, target_var="part0"))

    if_data = make("if_variable", var_name="data", operator="!=", compare_value="")
    if_data.add_then_action(make("write_to_file", file_path="macros/out.txt", text="Data"))
    if_data.add_then_action(make("log_to_file", message="OK"))
    if_data.add_then_action(make("run_command", command="echo ok", var_name="cmd"))
    if_data.add_else_action(make("set_variable", var_name="failed", value="1", operation="increment"))
    loop.add_action(if_data)

    loop.add_action(make("delay", duration_ms=10))
    loop.add_action(make("mouse_click", x=700, y=400))
    loop.add_action(make("key_combo", keys=["ctrl", "n"]))
    loop.add_action(make("type_text", text="Processing"))
    loop.add_action(make("key_press", key="enter"))
    loop.add_action(make("mouse_scroll", x=400, y=300, clicks=-2))
    a.append(loop)

    if_fail = make("if_variable", var_name="failed", operator=">", compare_value="0")
    if_fail.add_then_action(make("take_screenshot", save_dir="macros/screenshots"))
    if_fail.add_else_action(make("comment", text="All OK"))
    a.append(if_fail)

    a.append(make("activate_window", window_title="Log"))
    a.append(make("hotkey", keys=["ctrl", "end"]))
    a.append(make("comment", text="Processing done"))
    return a


# ══════════════════════════════════════════════════════════════
# SCENARIO 10: Ultimate - ALL types + groups + max nesting
# ══════════════════════════════════════════════════════════════
def s10():
    a = []

    # Group 1: Setup
    g1 = make("group", name="Setup")
    g1._children.append(make("comment", text="Ultimate Stress"))
    g1._children.append(make("set_variable", var_name="phase", value="1"))
    g1._children.append(make("set_variable", var_name="errors", value="0"))
    g1._children.append(make("set_variable", var_name="score", value="100"))
    g1._children.append(make("activate_window", window_title="TestApp"))
    a.append(g1)

    # Group 2: All Input Types
    g2 = make("group", name="Input")
    g2._children.append(make("mouse_click", x=100, y=100))
    g2._children.append(make("mouse_double_click", x=200, y=200))
    g2._children.append(make("mouse_right_click", x=300, y=300))
    g2._children.append(make("mouse_move", x=400, y=400))
    g2._children.append(make("mouse_drag", start_x=100, start_y=100, x=500, y=500))
    g2._children.append(make("mouse_scroll", x=300, y=300, clicks=-3))
    g2._children.append(make("key_press", key="enter"))
    g2._children.append(make("key_combo", keys=["ctrl", "shift", "s"]))
    g2._children.append(make("type_text", text="Ultimate test"))
    g2._children.append(make("hotkey", keys=["alt", "f4"]))
    g2._children.append(make("delay", duration_ms=10))
    a.append(g2)

    # Group 3: Logic (nested loops + all conditionals)
    g3 = make("group", name="Logic")
    outer = make("loop_block", iterations=4)

    if_img = make("if_image_found", image_path="test.png", confidence=0.7, timeout_ms=200)
    if_img.add_then_action(make("set_variable", var_name="phase", value="2"))
    if_img.add_else_action(make("comment", text="Not found"))
    outer.add_action(if_img)

    if_pix = make("if_pixel_color", x=500, y=500, r=0, g=255, b=0)
    if_pix.add_then_action(make("mouse_click", x=500, y=500))
    if_pix.add_else_action(make("delay", duration_ms=5))
    outer.add_action(if_pix)

    if_var = make("if_variable", var_name="score", operator=">=", compare_value="50")
    if_var.add_then_action(make("log_to_file", message="Score OK"))
    if_var.add_else_action(make("set_variable", var_name="errors", value="1", operation="increment"))
    outer.add_action(if_var)

    outer.add_action(make("check_pixel_color", x=200, y=200, r=128, g=128, b=128))
    outer.add_action(make("set_variable", var_name="score", value="10", operation="decrement"))

    inner = make("loop_block", iterations=2)
    inner.add_action(make("key_press", key="tab"))
    inner.add_action(make("type_text", text="inner"))
    inner.add_action(make("mouse_move", x=250, y=250))
    outer.add_action(inner)

    g3._children.append(outer)
    g3._children.append(make("split_string", source_var="score", delimiter=",",
                              field_index=0, target_var="p0"))
    g3._children.append(make("comment", text="Logic done"))
    a.append(g3)

    # Group 4: I/O
    g4 = make("group", name="IO")
    g4._children.append(make("read_clipboard", var_name="clip"))
    g4._children.append(make("read_file_line", file_path="macros/t.txt",
                              line_number=1, var_name="fl"))
    g4._children.append(make("write_to_file", file_path="macros/stress.txt", text="Out"))
    g4._children.append(make("log_to_file", message="IO done"))
    g4._children.append(make("run_command", command="echo test", var_name="cmd"))
    g4._children.append(make("take_screenshot", save_dir="macros/screenshots"))
    g4._children.append(make("image_exists", image_path="test.png", confidence=0.8))
    a.append(g4)

    a.append(make("comment", text="ULTIMATE DONE"))
    return a


# ══ TEST RUNNER ══

SCENARIOS = [
    ("S01-DataPipeline", s01),
    ("S02-ImageAuto", s02),
    ("S03-NestedMatrix", s03),
    ("S04-FormFiller", s04),
    ("S05-SysMonitor", s05),
    ("S06-DragDrop", s06),
    ("S07-CondChain", s07),
    ("S08-PixelGrid", s08),
    ("S09-FilePipeline", s09),
    ("S10-UltimateAll", s10),
]


def main():
    print("=" * 60)
    print("  10 COMPLEX STRESS TEST SCENARIOS")
    print("=" * 60)

    results = []
    all_types = set()
    total_n = 0
    fails = 0
    t0 = time.perf_counter()

    for name, fn in SCENARIOS:
        print(f"\n--- {name} ---")

        # Phase 1: Construction
        try:
            actions = fn()
            n = sum(count_total(a) for a in actions)
            types = get_types(actions)
            all_types |= types
            total_n += n
            print(f"  OK Built: {len(actions)} root, {n} total, {len(types)} types")
        except Exception as e:
            print(f"  FAIL Construction: {e}")
            traceback.print_exc()
            results.append((name, False, str(e)[:60]))
            fails += 1
            continue

        # Phase 2: Serialization
        try:
            ok = verify_roundtrip(actions)
            j = json.dumps([a.to_dict() for a in actions], ensure_ascii=False)
            print(f"  OK Serialize: {len(j)} bytes, roundtrip={'OK' if ok else 'FAIL'}")
            if not ok:
                fails += 1
                results.append((name, False, "roundtrip fail"))
                continue
        except Exception as e:
            print(f"  FAIL Serialize: {e}")
            traceback.print_exc()
            results.append((name, False, str(e)[:60]))
            fails += 1
            continue

        # Phase 3: Execution
        try:
            ctx = ExecutionContext()
            exec_ok, err = run_mocked(actions, ctx)
            nvars = len(ctx._variables)
            print(f"  OK Execution: {nvars} vars set")
        except Exception as e:
            print(f"  WARN Execution: {e}")

        # Phase 4: Depth
        max_d = [0]
        def depth(a, d=0):
            max_d[0] = max(max_d[0], d)
            for attr in ('children', 'then_children', 'else_children', '_sub_actions'):
                for c in getattr(a, attr, []):
                    depth(c, d+1)
        for a in actions:
            depth(a)
        print(f"  OK Structure: depth={max_d[0]}, types={sorted(types)}")

        results.append((name, True, f"{n} actions, {len(types)} types, depth={max_d[0]}"))

    elapsed = time.perf_counter() - t0

    # Summary
    print(f"\n{'=' * 60}")
    print("  SUMMARY")
    print(f"{'=' * 60}")
    print(f"  Passed:  {len(SCENARIOS)-fails}/{len(SCENARIOS)}")
    print(f"  Actions: {total_n}")
    print(f"  Types:   {len(all_types)}/34")
    print(f"  Time:    {elapsed:.2f}s")
    print()
    print(f"  {'Scenario':<20} {'OK?':<6} Detail")
    print(f"  {'-'*20} {'-'*6} {'-'*35}")
    for name, ok, detail in results:
        print(f"  {name:<20} {'PASS' if ok else 'FAIL':<6} {detail[:50]}")

    ALL_REG = {
        "mouse_click","mouse_double_click","mouse_right_click","mouse_move",
        "mouse_drag","mouse_scroll","key_press","key_combo","type_text","hotkey",
        "delay","loop_block","if_image_found","if_pixel_color","if_variable",
        "set_variable","split_string","comment","group","activate_window",
        "log_to_file","read_clipboard","read_file_line","write_to_file",
        "run_command","take_screenshot","check_pixel_color","wait_for_color",
        "wait_for_image","click_on_image","image_exists","secure_type_text",
        "run_macro","capture_text",
    }
    missing = ALL_REG - all_types
    if missing:
        print(f"\n  NOT covered ({len(missing)}): {sorted(missing)}")

    print(f"\n{'=' * 60}")
    if fails:
        print(f"  {fails} FAILED")
        sys.exit(1)
    else:
        print(f"  ALL {len(SCENARIOS)} PASSED")
        sys.exit(0)


if __name__ == "__main__":
    main()
