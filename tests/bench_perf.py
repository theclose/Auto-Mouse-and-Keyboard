# -*- coding: utf-8 -*-
"""Quick stress benchmark after optimizations."""
import sys, os, time, threading
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

results = []


def p(name, fn, n):
    t0 = time.perf_counter()
    for _ in range(n):
        fn()
    elapsed = time.perf_counter() - t0
    us = elapsed / n * 1e6
    results.append((name, n, elapsed, us))


# === Variables ===
ctx.set_var("row", 42)
ctx.set_var("name", "ProductX")
p("set_var", lambda: ctx.set_var("x", 1), 100000)
p("get_var", lambda: ctx.get_var("x"), 100000)
tpl1 = "Item ${row}"
tpl2 = "${row}_${name}"
tpl3 = "no vars here"
p("interpolate_simple", lambda: ctx.interpolate(tpl1), 100000)
p("interpolate_multi", lambda: ctx.interpolate(tpl2), 100000)
p("interpolate_static", lambda: ctx.interpolate(tpl3), 100000)

# === ROI ===
for i in range(5):
    ctx.set_image_match("b.png", (100 + i, 200 + i, 50, 30))
p("suggest_roi", lambda: ctx.suggest_roi("b.png"), 100000)
p("suggest_roi_cached", lambda: ctx.suggest_roi_cached("b.png"), 100000)
p("set_image_match", lambda: ctx.set_image_match("b.png", (100, 200, 50, 30)), 100000)
p("get_image_match", lambda: ctx.get_image_match("b.png"), 100000)

# === Actions ===
import core.scheduler
import modules.system
from core.action import get_action_class

SV = get_action_class("set_variable")
IV = get_action_class("if_variable")

sv = SV(var_name="c", value="", operation="increment")
ctx.set_var("c", 0)
p("SetVariable.execute(inc)", sv.execute, 100000)
p("SetVariable.run(inc)", sv.run, 50000)

iv = IV(var_name="c", operator=">", compare_value="0")
p("IfVariable.execute", iv.execute, 100000)

# === LoopBlock 10K ===
from core.scheduler import LoopBlock

sv2 = SV(var_name="lc", value="", operation="increment")
ctx.set_var("lc", 0)
loop = LoopBlock(iterations=10000)
loop.add_action(sv2)
t0 = time.perf_counter()
loop.execute()
e = time.perf_counter() - t0
results.append(("LoopBlock(10K)x1_action", 10000, e, e / 10000 * 1e6))

# === LoopBlock 50K ===
ctx.set_var("lc2", 0)
sv3 = SV(var_name="lc2", value="", operation="increment")
loop2 = LoopBlock(iterations=50000)
loop2.add_action(sv3)
t0 = time.perf_counter()
loop2.execute()
e = time.perf_counter() - t0
results.append(("LoopBlock(50K)x1_action", 50000, e, e / 50000 * 1e6))

# === LoopBlock 100K ===
ctx.set_var("lc3", 0)
sv4 = SV(var_name="lc3", value="", operation="increment")
loop3 = LoopBlock(iterations=100000)
loop3.add_action(sv4)
t0 = time.perf_counter()
loop3.execute()
e = time.perf_counter() - t0
results.append(("LoopBlock(100K)x1_action", 100000, e, e / 100000 * 1e6))

# === DPAPI ===
from core.secure import encrypt, decrypt
enc = encrypt("P@ssw0rd123!")
p("DPAPI_encrypt", lambda: encrypt("P@ssw0rd123!"), 1000)
p("DPAPI_decrypt", lambda: decrypt(enc), 1000)

# === Print ===
print("%-35s | %8s | %7s | %9s" % ("Test", "Iters", "Total", "Per-iter"))
print("-" * 70)
for name, n, elapsed, us in results:
    print("%-35s | %8d | %6.3fs | %7.1f us" % (name, n, elapsed, us))

# Final check
print("\nFinal values: lc=%s, lc2=%s, lc3=%s" % (
    ctx.get_var("lc"), ctx.get_var("lc2"), ctx.get_var("lc3")))
