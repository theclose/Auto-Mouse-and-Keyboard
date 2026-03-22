# -*- coding: utf-8 -*-
"""
High-Iteration Stress Test — profiles all action types under extreme loads.
Tests: 10K, 50K, 100K iterations for core paths.
"""
import sys
import os
import time
import tracemalloc
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock pyautogui/pynput to avoid physical side effects
import unittest.mock as mock
sys.modules['pyautogui'] = mock.MagicMock()
sys.modules['pynput'] = mock.MagicMock()
sys.modules['pynput.mouse'] = mock.MagicMock()
sys.modules['pynput.keyboard'] = mock.MagicMock()

from core.execution_context import ExecutionContext
from core.engine_context import set_context, set_stop_event, set_speed

# Setup context
ctx = ExecutionContext()
ctx.reset()
set_context(ctx)
set_speed(1.0)
stop_event = threading.Event()
set_stop_event(stop_event)


def profile(name, fn, iterations):
    """Profile a function over N iterations."""
    tracemalloc.start()
    mem_before = tracemalloc.get_traced_memory()[0]
    
    start = time.perf_counter()
    for _ in range(iterations):
        fn()
    elapsed = time.perf_counter() - start
    
    mem_after = tracemalloc.get_traced_memory()[0]
    tracemalloc.stop()
    
    per_iter = (elapsed / iterations) * 1_000_000  # microseconds
    mem_delta = (mem_after - mem_before) / 1024  # KB
    
    print(f"  {name:40s} | {iterations:>8,} iters | "
          f"{elapsed:>7.3f}s | {per_iter:>7.1f} µs/iter | "
          f"mem Δ: {mem_delta:>+8.1f} KB")
    return elapsed, per_iter, mem_delta


print("=" * 100)
print("HIGH-ITERATION STRESS TEST — AutoMacro v2.2.0")
print("=" * 100)

# ============================================================================
# Test 1: ExecutionContext — variables
# ============================================================================
print("\n▶ Test 1: ExecutionContext.set_var / get_var")
ctx.reset()
profile("set_var (int)", lambda: ctx.set_var("counter", 42), 100_000)
profile("get_var (int)", lambda: ctx.get_var("counter"), 100_000)
profile("set_var (string)", lambda: ctx.set_var("name", "hello world test"), 100_000)

# ============================================================================
# Test 2: Template interpolation
# ============================================================================
print("\n▶ Test 2: Template interpolation — ctx.interpolate()")
ctx.set_var("row", 42)
ctx.set_var("name", "ProductX")
ctx.set_var("server_id", 5)
profile("interpolate simple '${row}'",
        lambda: ctx.interpolate("Item ${row}"), 100_000)
profile("interpolate multi '${row} ${name}'",
        lambda: ctx.interpolate("Row ${row}: ${name} on server ${server_id}"), 100_000)
profile("interpolate no-var 'static text'",
        lambda: ctx.interpolate("Just a static text with no vars"), 100_000)

# ============================================================================
# Test 3: SetVariable action
# ============================================================================
print("\n▶ Test 3: SetVariable action")
import core.scheduler  # register actions
from core.action import get_action_class
SetVariable = get_action_class("set_variable")

sv_set = SetVariable(var_name="x", value="0", operation="set")
sv_inc = SetVariable(var_name="x", value="", operation="increment")
sv_add = SetVariable(var_name="total", value="3.14", operation="add")

profile("SetVariable(set)", sv_set.execute, 100_000)
profile("SetVariable(increment)", sv_inc.execute, 100_000)
ctx.set_var("total", 0)
profile("SetVariable(add)", sv_add.execute, 50_000)

# ============================================================================
# Test 4: IfVariable action
# ============================================================================
print("\n▶ Test 4: IfVariable action (empty branches)")
IfVariable = get_action_class("if_variable")
iv = IfVariable(var_name="x", operator=">", compare_value="0")
profile("IfVariable (x > 0, no branches)", iv.execute, 100_000)

iv2 = IfVariable(var_name="x", operator="==", compare_value="100000")
profile("IfVariable (x == 100000, no match)", iv2.execute, 100_000)

# ============================================================================
# Test 5: Image match result chaining
# ============================================================================
print("\n▶ Test 5: ExecutionContext — image chaining")
profile("set_image_match",
        lambda: ctx.set_image_match("btn.png", (100, 200, 50, 30)), 100_000)
profile("get_image_match",
        lambda: ctx.get_image_match("btn.png"), 100_000)
profile("get_image_center",
        lambda: ctx.get_image_center("btn.png"), 100_000)
profile("suggest_roi",
        lambda: ctx.suggest_roi("btn.png"), 100_000)

# ============================================================================
# Test 6: Smart ROI history memory check
# ============================================================================
print("\n▶ Test 6: Smart ROI — memory under high churn")
ctx.reset()
tracemalloc.start()
mem_before = tracemalloc.get_traced_memory()[0]
for i in range(10_000):
    ctx.set_image_match(f"template_{i % 100}.png", (i % 1920, i % 1080, 50, 30))
mem_after = tracemalloc.get_traced_memory()[0]
tracemalloc.stop()
print(f"  10K set_image_match (100 templates) | mem Δ: {(mem_after - mem_before)/1024:>+8.1f} KB")

# ============================================================================
# Test 7: LogToFile throughput
# ============================================================================
print("\n▶ Test 7: LogToFile throughput")
import modules.system  # register actions
LogToFile = get_action_class("log_to_file")
log_file = os.path.join(os.path.dirname(__file__), "_stress_log.txt")
lf = LogToFile(message="Test iteration ${row}", file_path=log_file)
ctx.set_var("row", 1)
profile("LogToFile (write + interpolate)", lf.execute, 10_000)
# Cleanup
if os.path.exists(log_file):
    size_kb = os.path.getsize(log_file) / 1024
    print(f"  Log file size: {size_kb:.1f} KB for 10K entries")
    os.unlink(log_file)

# ============================================================================
# Test 8: ReadFileLine throughput
# ============================================================================
print("\n▶ Test 8: ReadFileLine throughput")
test_file = os.path.join(os.path.dirname(__file__), "_stress_data.txt")
with open(test_file, "w") as f:
    for i in range(1000):
        f.write(f"data_line_{i},value_{i*10}\n")

ReadFileLine = get_action_class("read_file_line")
rfl = ReadFileLine(file_path=test_file, line_number="500", var_name="data")
profile("ReadFileLine (line 500 of 1000)", rfl.execute, 10_000)
os.unlink(test_file)

# ============================================================================
# Test 9: LoopBlock simulation (nested)
# ============================================================================
print("\n▶ Test 9: LoopBlock × SetVariable (simulated 10K iterations)")
from core.scheduler import LoopBlock
sv_counter = SetVariable(var_name="loop_counter", value="", operation="increment")
ctx.set_var("loop_counter", 0)

loop = LoopBlock(iterations=10_000)
loop.add_action(sv_counter)

start = time.perf_counter()
tracemalloc.start()
mem_before = tracemalloc.get_traced_memory()[0]
loop.execute()
mem_after = tracemalloc.get_traced_memory()[0]
elapsed = time.perf_counter() - start
tracemalloc.stop()

final_val = ctx.get_var("loop_counter")
print(f"  LoopBlock(10K) × SetVariable(inc) | {elapsed:.3f}s | "
      f"{elapsed/10000*1e6:.1f} µs/iter | final={final_val} | "
      f"mem Δ: {(mem_after-mem_before)/1024:>+.1f} KB")

# ============================================================================
# Test 10: DPAPI encrypt/decrypt throughput
# ============================================================================
print("\n▶ Test 10: DPAPI encrypt/decrypt")
from core.secure import encrypt, decrypt
encrypted = encrypt("P@ssw0rd123!Secret")
profile("encrypt (18 chars)", lambda: encrypt("P@ssw0rd123!Secret"), 1_000)
profile("decrypt (18 chars)", lambda: decrypt(encrypted), 1_000)

# ============================================================================
# Summary
# ============================================================================
print("\n" + "=" * 100)
print("STRESS TEST COMPLETE")
print("=" * 100)
