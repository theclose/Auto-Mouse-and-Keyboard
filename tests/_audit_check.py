# -*- coding: utf-8 -*-
"""Quick audit check for remaining bugs."""
import sys, os, threading, tempfile, shutil
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import unittest.mock as mock
sys.modules['pyautogui'] = mock.MagicMock()
sys.modules['pynput'] = mock.MagicMock()
sys.modules['pynput.mouse'] = mock.MagicMock()
sys.modules['pynput.keyboard'] = mock.MagicMock()

from core.execution_context import ExecutionContext
from core.engine_context import set_context, set_stop_event, set_speed
ctx = ExecutionContext()
ctx.reset()
set_context(ctx)
set_speed(1.0)
set_stop_event(threading.Event())

import core.scheduler, modules.system, modules.mouse, modules.keyboard, modules.image
from core.action import get_action_class

bugs = []
passed = []
limitations = []

# 1: SplitString with quoted CSV
SS = get_action_class("split_string")
ctx.set_var("csv_line", 'John,"New York, NY",25')
ss = SS(source_var="csv_line", delimiter=",", field_index=1, target_var="city")
ss.execute()
city = ctx.get_var("city")
if city != "New York, NY":
    bugs.append(("BUG-1", "SplitString naive split: got %r instead of 'New York, NY'" % city))
else:
    passed.append("SplitString quoted CSV")

# 2: SetVariable add with non-numeric
SV = get_action_class("set_variable")
ctx.set_var("total", 0)
ctx.set_var("amt_str", "not_a_number")
sv = SV(var_name="total", value="${amt_str}", operation="add")
try:
    result = sv.execute()
    if result:
        bugs.append(("BUG-2", "SetVariable add with non-numeric silently succeeds"))
    else:
        passed.append("SetVariable add with non-numeric returns False")
except Exception as e:
    bugs.append(("BUG-2", "SetVariable add crashes with non-numeric: %s" % type(e).__name__))

# 3: Serialize roundtrip for all new action types
for name in ["split_string", "delay", "run_macro", "capture_text", "set_variable"]:
    cls = get_action_class(name)
    a = cls()
    d = a.to_dict()
    a2 = type(a).from_dict(d)
    d2 = a2.to_dict()
    if d == d2:
        passed.append("Roundtrip: %s" % name)
    else:
        bugs.append(("BUG-3-%s" % name, "Roundtrip mismatch"))

# 4: MouseMove dynamic serialize roundtrip
from modules.mouse import MouseMove, MouseDrag
mm = MouseMove(x=100, y=200)
mm._dynamic_x = "${tx}"
mm._dynamic_y = "${ty}"
d = mm.to_dict()
mm2 = MouseMove.from_dict(d)
if mm2._dynamic_x == "${tx}" and mm2._dynamic_y == "${ty}":
    passed.append("MouseMove dynamic roundtrip")
else:
    bugs.append(("BUG-4a", "MouseMove dynamic lost"))

md = MouseDrag(x=100, y=200)
md._dynamic_x = "${tx}"
md._dynamic_y = "${ty}"
d = md.to_dict()
md2 = MouseDrag.from_dict(d)
if md2._dynamic_x == "${tx}" and md2._dynamic_y == "${ty}":
    passed.append("MouseDrag dynamic roundtrip")
else:
    bugs.append(("BUG-4b", "MouseDrag dynamic lost"))

# 5: DelayAction dynamic roundtrip
DA = get_action_class("delay")
da = DA(duration_ms=1000)
da._dynamic_ms = "${delay_var}"
d = da.to_dict()
da2 = type(da).from_dict(d)
if da2._dynamic_ms == "${delay_var}":
    passed.append("Delay dynamic roundtrip")
else:
    bugs.append(("BUG-5", "Delay dynamic lost"))

# 6: ReadFileLine nonexistent file
RFL = get_action_class("read_file_line")
rfl = RFL(file_path="nonexistent_file_xyz.txt", line_number="1", var_name="v")
result = rfl.execute()
if not result:
    passed.append("ReadFileLine nonexistent -> False")
else:
    bugs.append(("BUG-6", "ReadFileLine nonexistent -> True"))

# 7: SplitString out-of-range index
ctx.set_var("short", "a,b")
ss2 = SS(source_var="short", delimiter=",", field_index=5, target_var="oob")
result = ss2.execute()
oob = ctx.get_var("oob")
if oob == "":
    passed.append("SplitString OOB -> empty (graceful)")
else:
    bugs.append(("BUG-7", "SplitString OOB: %r" % oob))

# 8: System vars with no image match
ctx._last_image_match = None
x = ctx.interpolate("${__last_img_x__}")
if x == "0":
    passed.append("__last_img_x__ no match -> '0'")
else:
    bugs.append(("BUG-8", "__last_img_x__ no match -> %r" % x))

# 9: LogToFile special chars
tmp = tempfile.mkdtemp()
LTF = get_action_class("log_to_file")
log_path = os.path.join(tmp, "test.log")
ctx.set_var("msg", 'Line with "quotes" and tabs')
ltf = LTF(message="${msg}", file_path=log_path)
ltf.execute()
with open(log_path) as f:
    content = f.read()
if "quotes" in content:
    passed.append("LogToFile handles special chars")
else:
    bugs.append(("BUG-9", "LogToFile lost special chars"))
shutil.rmtree(tmp)

# 10: WriteToFile no rotation
limitations.append("WriteToFile/LogToFile: no log rotation (unbounded file growth)")
limitations.append("SplitString: no CSV quote escaping (naive split)")
limitations.append("OCR (CaptureText): requires Tesseract installed separately")
limitations.append("IfImageFound: no ELSE action from GUI editor (only via JSON)")
limitations.append("No expression language (only increment/decrement/add/set)")
limitations.append("No step-by-step debugger in GUI")
limitations.append("No action groups / folders for organizing 100+ step macros")

# Report
print("=" * 60)
print("REMAINING ISSUES AUDIT - AutoMacro v2.3.1")
print("=" * 60)
print("\nPASSED (%d):" % len(passed))
for p in passed:
    print("  [OK] %s" % p)
print("\nBUGS (%d):" % len(bugs))
for bid, desc in bugs:
    print("  [%s] %s" % (bid, desc))
print("\nKNOWN LIMITATIONS (%d):" % len(limitations))
for i, lim in enumerate(limitations, 1):
    print("  [L%d] %s" % (i, lim))
print("\nTotal: %d passed, %d bugs, %d limitations" % (len(passed), len(bugs), len(limitations)))
