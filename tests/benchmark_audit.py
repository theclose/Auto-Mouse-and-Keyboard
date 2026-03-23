# -*- coding: utf-8 -*-
"""
OCR Accuracy Benchmark + Low-Spec System Profiling

Fix #2: Generate synthetic screenshots and measure pytesseract accuracy
Fix #5: Profile memory usage, CPU time, and GDI handles under load
"""
import sys
import os
import time
import threading
import tracemalloc
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest.mock as mock
sys.modules['pyautogui'] = mock.MagicMock()
sys.modules['pynput'] = mock.MagicMock()
sys.modules['pynput.mouse'] = mock.MagicMock()
sys.modules['pynput.keyboard'] = mock.MagicMock()

from core.execution_context import ExecutionContext
from core.engine_context import set_context, set_stop_event, set_speed

results = []


def setup():
    ctx = ExecutionContext()
    ctx.reset()
    set_context(ctx)
    set_speed(1.0)
    set_stop_event(threading.Event())
    return ctx


# ============================================================================
# FIX #2: OCR Accuracy Benchmark
# ============================================================================
def benchmark_ocr():
    """Generate synthetic images with known text, measure OCR accuracy."""
    print("=" * 70)
    print("OCR ACCURACY BENCHMARK")
    print("=" * 70)
    
    try:
        import pytesseract
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("  SKIP: pytesseract or Pillow not available")
        return

    # Check if Tesseract is actually installed
    try:
        pytesseract.get_tesseract_version()
    except Exception:
        print("  SKIP: Tesseract executable not found")
        print("  Install: https://github.com/tesseract-ocr/tesseract")
        return

    test_cases = [
        # (text, font_size, bg_color, fg_color, description)
        ("Hello World", 24, "white", "black", "Simple text 24px"),
        ("12345.67", 20, "white", "black", "Number 20px"),
        ("$1,234.56", 18, "white", "black", "Currency 18px"),
        ("Item-001", 16, "white", "black", "Alphanumeric 16px"),
        ("ABC123", 14, "white", "black", "Short code 14px"),
        ("Hello World", 12, "white", "black", "Small 12px"),
        ("2026-03-22", 20, "white", "black", "Date format"),
        ("test@email.com", 16, "white", "black", "Email"),
        ("192.168.1.1", 18, "white", "black", "IP address"),
        ("Hello World", 24, "#333333", "#FFFFFF", "Dark bg light text"),
        ("Price: 99.99", 20, "#2D2D2D", "#E0E0E0", "Dark mode"),
        ("Status: OK", 16, "#004400", "#00FF00", "Green on dark"),
        ("ERROR 404", 24, "#440000", "#FF0000", "Red on dark"),
        ("Hello World", 30, "white", "black", "Large 30px"),
        ("999", 36, "white", "black", "Large number 36px"),
        ("ABCDEFGHIJ", 20, "white", "black", "Uppercase"),
        ("abcdefghij", 20, "white", "black", "Lowercase"),
        ("Mixed Case", 20, "white", "black", "Mixed case"),
        ("Line 1", 14, "#F0F0F0", "#333333", "Gray bg 14px"),
        ("$0.01", 12, "white", "black", "Tiny currency 12px"),
    ]

    correct = 0
    close = 0  # Within edit distance 2
    total = len(test_cases)

    print(f"\n  {'#':>3} | {'Expected':20s} | {'OCR Result':20s} | {'Match':5s} | Description")
    print("  " + "-" * 80)

    for i, (text, size, bg, fg, desc) in enumerate(test_cases):
        # Generate image
        w, h = max(300, len(text) * size), size * 3
        img = Image.new("RGB", (w, h), bg)
        draw = ImageDraw.Draw(img)
        
        try:
            font = ImageFont.truetype("arial.ttf", size)
        except (IOError, OSError):
            font = ImageFont.load_default()

        draw.text((10, size // 2), text, fill=fg, font=font)

        # OCR
        ocr_text = pytesseract.image_to_string(img, config="--psm 7").strip()
        
        match = ocr_text == text
        if match:
            correct += 1
            status = "OK"
        elif _edit_distance(ocr_text, text) <= 2:
            close += 1
            status = "~"
        else:
            status = "FAIL"

        print(f"  {i+1:3d} | {text:20s} | {ocr_text:20s} | {status:5s} | {desc}")

    # Summary
    exact_pct = correct / total * 100
    close_pct = (correct + close) / total * 100
    print(f"\n  Exact match: {correct}/{total} ({exact_pct:.0f}%)")
    print(f"  Close match: {correct+close}/{total} ({close_pct:.0f}%)")
    print(f"  Failed:      {total - correct - close}/{total}")
    
    results.append(("OCR exact accuracy", f"{exact_pct:.0f}%"))
    results.append(("OCR close accuracy", f"{close_pct:.0f}%"))


def _edit_distance(s1, s2):
    """Simple Levenshtein distance."""
    if len(s1) < len(s2):
        return _edit_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)
    prev = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        curr = [i + 1]
        for j, c2 in enumerate(s2):
            curr.append(min(prev[j + 1] + 1, curr[j] + 1,
                           prev[j] + (c1 != c2)))
        prev = curr
    return prev[-1]


# ============================================================================
# FIX #5: Low-Spec System Profiling
# ============================================================================
def profile_low_spec():
    """Simulate low-spec constraints and measure actual resource usage."""
    print("\n" + "=" * 70)
    print("LOW-SPEC SYSTEM PROFILING")
    print("=" * 70)

    ctx = setup()

    # Import all actions
    import core.scheduler
    import modules.system
    from core.action import get_action_class

    # 1. Memory baseline
    tracemalloc.start()
    mem_base = tracemalloc.get_traced_memory()[0]

    # 2. Simulate 1000 iterations with variable churn
    SV = get_action_class("set_variable")
    IV = get_action_class("if_variable")
    RFL = get_action_class("read_file_line")
    SS = get_action_class("split_string")
    WTF = get_action_class("write_to_file")
    LTF = get_action_class("log_to_file")

    tmp = tempfile.mkdtemp()
    csv_path = os.path.join(tmp, "test_data.csv")
    out_path = os.path.join(tmp, "output.txt")
    log_path = os.path.join(tmp, "log.txt")

    with open(csv_path, "w") as f:
        for i in range(1000):
            f.write(f"item{i},Product{i},{i * 10}\n")

    t0 = time.perf_counter()

    for i in range(1, 1001):
        ctx.set_var("i", i)
        
        # Read + Split + Add
        rfl = RFL(file_path=csv_path, line_number=str(i), var_name="line")
        rfl.execute()
        
        ss = SS(source_var="line", delimiter=",", field_index=2, target_var="amount")
        ss.execute()
        
        sv = SV(var_name="total", value="${amount}", operation="add")
        sv.execute()

        # Log every 100
        if i % 100 == 0:
            ltf = LTF(message="Progress: ${i}/1000 total=${total}", file_path=log_path)
            ltf.execute()

    elapsed = time.perf_counter() - t0
    mem_after = tracemalloc.get_traced_memory()[0]
    mem_peak = tracemalloc.get_traced_memory()[1]
    tracemalloc.stop()

    mem_used_kb = (mem_after - mem_base) / 1024
    mem_peak_kb = (mem_peak - mem_base) / 1024

    print(f"\n  Workload: 1000 iterations x (ReadFileLine + SplitString + SetVariable)")
    print(f"  Total time:    {elapsed:.3f}s ({elapsed/1000*1000:.1f} ms/iter)")
    print(f"  Memory used:   {mem_used_kb:.1f} KB")
    print(f"  Memory peak:   {mem_peak_kb:.1f} KB")
    print(f"  Final total:   {ctx.get_var('total')}")
    print(f"  Variables:     {len(ctx._variables)} active")

    # Verify correctness
    expected = sum(i * 10 for i in range(1000))
    actual = ctx.get_var("total")
    print(f"  Correctness:   {'PASS' if actual == expected else 'FAIL'} "
          f"(expected={expected}, got={actual})")

    results.append(("1K pipeline time", f"{elapsed:.3f}s"))
    results.append(("Memory used", f"{mem_used_kb:.1f} KB"))
    results.append(("Memory peak", f"{mem_peak_kb:.1f} KB"))

    # 3. GDI / Handle check (Windows-specific)
    try:
        import ctypes
        process = ctypes.windll.kernel32.GetCurrentProcess()
        gdi = ctypes.windll.user32.GetGuiResources(process, 0)  # GDI
        user = ctypes.windll.user32.GetGuiResources(process, 1)  # USER
        print(f"  GDI handles:   {gdi}")
        print(f"  USER handles:  {user}")
        results.append(("GDI handles", str(gdi)))
    except Exception:
        print("  GDI check: N/A (non-Windows)")

    # 4. Cleanup
    import shutil
    shutil.rmtree(tmp)

    # 5. Low-spec verdict
    print("\n  LOW-SPEC VERDICT:")
    if mem_peak_kb < 1024:
        print("    Memory: PASS (< 1 MB peak)")
    elif mem_peak_kb < 5120:
        print(f"    Memory: WARN ({mem_peak_kb:.0f} KB peak)")
    else:
        print(f"    Memory: FAIL ({mem_peak_kb:.0f} KB peak)")

    if elapsed < 5:
        print(f"    CPU: PASS ({elapsed:.1f}s for 1K pipeline)")
    else:
        print(f"    CPU: FAIL ({elapsed:.1f}s for 1K pipeline)")


# ============================================================================
# Main
# ============================================================================
if __name__ == "__main__":
    benchmark_ocr()
    profile_low_spec()

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    for name, value in results:
        print(f"  {name:25s}: {value}")
