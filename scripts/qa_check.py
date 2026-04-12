"""
Pre-Release QA Runner -- One command to run the full QA checklist.

Usage:
    python scripts/qa_check.py           # Run all checks
    python scripts/qa_check.py --quick   # Skip slow tests, lint only

Checks (11 total):
    1. pytest (880+ tests)
    2. ruff lint
    3. Thread-safety scan (TS-1..4)
    4. Signal target scan (SIG-1)
    5. Memory pattern scan (MEM-1..4)
    6. __slots__ consistency (SLOT-1..3)
    7. Resource cleanup scan (RES-1..3)
    8. Conditional import scan (CI-1)
    9. Shortcut conflict scan (SC-1)
   10. Getattr typo scan (GA-1)
   11. Import cycle check (39 modules)
"""

import os
import subprocess
import sys
import time

# Fix Windows console encoding for Unicode output (ruff uses → arrows)
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

# ANSI
GREEN = "\033[92m"
RED = "\033[91m"
CYAN = "\033[96m"
YELLOW = "\033[93m"
BOLD = "\033[1m"
RESET = "\033[0m"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run_check(name: str, cmd: list[str], timeout: int = 120) -> tuple[bool, str]:
    """Run a check command, return (passed, output)."""
    try:
        result = subprocess.run(
            cmd, cwd=ROOT, capture_output=True, text=True, timeout=timeout,
            encoding="utf-8", errors="replace",
            env={**os.environ, "QT_QPA_PLATFORM": "offscreen", "PYTHONPATH": ROOT},
        )
        passed = result.returncode == 0
        output = result.stdout + result.stderr
        return passed, output.strip()
    except subprocess.TimeoutExpired:
        return False, f"Timeout ({timeout}s)"
    except FileNotFoundError:
        return False, "Command not found"


def extract_test_count(output: str) -> str:
    """Extract '700 passed' from pytest output."""
    for line in output.splitlines()[-5:]:
        if "passed" in line:
            return line.strip()
    return "unknown"


def main() -> int:
    quick = "--quick" in sys.argv

    print(f"\n{BOLD}{CYAN}=== AutoMacro QA Check ==={RESET}")
    print("=" * 50)

    checks: list[tuple[str, list[str], int]] = []

    # ── Stage 1: Unit Tests (skip in --quick mode) ───────────────
    if not quick:
        checks.append((
            "Running tests",
            [sys.executable, "-m", "pytest", "tests/", "-q", "--tb=no",
             "--benchmark-disable",
             "--ignore=tests/bench_perf.py",
             "--ignore=tests/bench_stress.py",
             "--ignore=tests/benchmark_audit.py"],
            180,
        ))

    # ── Stage 2: Code Quality ────────────────────────────────────
    checks.extend([
        (
            "Ruff lint",
            [sys.executable, "-m", "ruff", "check", "."],
            30,
        ),
    ])

    # ── Stage 3: Custom Lint Rules ───────────────────────────────
    checks.extend([
        (
            "Thread-safety scan",
            [sys.executable, "scripts/lint_thread_safety.py"],
            15,
        ),
        (
            "Signal target scan",
            [sys.executable, "scripts/lint_signal_targets.py"],
            15,
        ),
        (
            "Memory pattern scan",
            [sys.executable, "scripts/lint_memory_patterns.py", "--strict"],
            15,
        ),
        (
            "__slots__ consistency",
            [sys.executable, "scripts/lint_slots_check.py", "--strict"],
            15,
        ),
        (
            "Resource cleanup scan",
            [sys.executable, "scripts/lint_resource_cleanup.py", "--strict"],
            15,
        ),
    ])

    # ── Stage 3b: Audit-derived Lint Rules ────────────────────────
    checks.extend([
        (
            "Conditional import scan",
            [sys.executable, "scripts/lint_conditional_imports.py"],
            15,
        ),
        (
            "Shortcut conflict scan",
            [sys.executable, "scripts/lint_shortcut_conflicts.py", "--strict"],
            15,
        ),
        (
            "Getattr typo scan",
            [sys.executable, "scripts/lint_getattr_typos.py"],
            15,
        ),
    ])

    # ── Stage 4: Import Health (all core/modules/gui modules) ────
    checks.append((
        "Import cycle check",
        [sys.executable, "-c",
         # -- core (14 modules) --
         "import core.action; import core.engine; import core.scheduler; "
         "import core.engine_context; import core.execution_context; "
         "import core.event_bus; import core.hotkey_manager; "
         "import core.memory_manager; import core.smart_hints; "
         "import core.undo_commands; import core.crash_handler; "
         "import core.autosave; import core.recorder; import core.secure; "
         # -- modules (5 modules) --
         "import modules.mouse; import modules.keyboard; import modules.image; "
         "import modules.pixel; import modules.system; "
         # -- gui (13 modules) --
         "import gui.main_window; import gui.action_editor; import gui.styles; "
         "import gui.settings_dialog; import gui.action_tree_model; "
         "import gui.coordinate_picker; import gui.image_capture; "
         "import gui.help_dialog; import gui.recording_panel; "
         "import gui.tray; import gui.constants; "
         "import gui.no_scroll_widgets; import gui.image_preview_widget; "
         # -- gui.panels (8 modules) --
         "import gui.panels.action_list_panel; import gui.panels.execution_panel; "
         "import gui.panels.log_panel; import gui.panels.minimap_panel; "
         "import gui.panels.playback_panel; import gui.panels.properties_panel; "
         "import gui.panels.variable_panel; import gui.panels.multi_run_panel; "
         "print('OK — 40 modules checked')"],
        30,
    ))

    results: list[tuple[str, bool, str]] = []
    total = len(checks)

    for i, (name, cmd, timeout) in enumerate(checks, 1):
        status = f"[{i}/{total}] {name}"
        print(f"  {status}{'.' * (35 - len(name))}", end=" ", flush=True)

        t0 = time.perf_counter()
        passed, output = run_check(name, cmd, timeout)
        elapsed = time.perf_counter() - t0

        if passed:
            detail = ""
            if "tests" in name.lower():
                detail = f" ({extract_test_count(output)})"
            print(f"{GREEN}[PASS]{detail} ({elapsed:.1f}s){RESET}")
        else:
            print(f"{RED}[FAIL] ({elapsed:.1f}s){RESET}")
            # Show first 5 lines of error
            for line in output.splitlines()[:5]:
                print(f"    {RED}{line}{RESET}")

        results.append((name, passed, output))

    # ── Summary ──────────────────────────────────────────────────
    passed_count = sum(1 for _, p, _ in results if p)
    print(f"\n{'=' * 50}")

    # Rule counts
    lint_names = ["Thread-safety", "Signal target", "Memory pattern", "__slots__",
                  "Resource cleanup", "Conditional import", "Shortcut conflict", "Getattr typo"]
    rule_counts = {
        "Thread-safety": 4,
        "Signal target": 1,
        "Memory pattern": 4,
        "__slots__": 3,
        "Resource cleanup": 3,
        "Conditional import": 1,
        "Shortcut conflict": 1,
        "Getattr typo": 1,
    }
    total_rules = sum(rule_counts.values())
    print(f"  {CYAN}Custom lint rules: {total_rules} ({', '.join(f'{v} {k}' for k, v in rule_counts.items())}){RESET}")

    if passed_count == total:
        print(f"{GREEN}{BOLD}  QA Score: {passed_count}/{total} [ALL PASS] ✅ Ready for release{RESET}\n")
        return 0
    else:
        failed = [name for name, p, _ in results if not p]
        print(f"{RED}{BOLD}  QA Score: {passed_count}/{total} [FAIL] ❌ Not ready{RESET}")
        print(f"  Failed: {', '.join(failed)}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
