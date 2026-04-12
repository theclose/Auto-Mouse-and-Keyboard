"""
Thread-Safety Lint — Scans Python files for common thread-safety violations.

Derived from 8 audit cycles of AutoMacro bug findings.

Usage:
    python scripts/lint_thread_safety.py [--fix-hints]

Checks:
    TS-1: Manual QMutex lock()/unlock() without QMutexLocker
    TS-2: threading.Thread without daemon=True
    TS-3: assert statements used for runtime validation
    TS-4: getattr(self, "_...", ...) in threaded modules (lazy init cross-thread)
"""

import re
import sys
from pathlib import Path

# Directories to scan
SCAN_DIRS = ["core", "gui", "modules"]
EXCLUDE_DIRS = {"__pycache__", ".venv", "tests", "scripts"}

# ANSI colors
RED = "\033[91m"
YELLOW = "\033[93m"
GREEN = "\033[92m"
CYAN = "\033[96m"
RESET = "\033[0m"


def find_python_files(root: Path) -> list[Path]:
    """Find all .py files in scan directories."""
    files = []
    for scan_dir in SCAN_DIRS:
        d = root / scan_dir
        if d.exists():
            for f in d.rglob("*.py"):
                if not any(part in EXCLUDE_DIRS for part in f.parts):
                    files.append(f)
    return sorted(files)


class Violation:
    def __init__(self, code: str, file: Path, line: int, message: str, hint: str = ""):
        self.code = code
        self.file = file
        self.line = line
        self.message = message
        self.hint = hint

    def __str__(self) -> str:
        rel = self.file.relative_to(self.file.parent.parent.parent) if len(self.file.parts) > 3 else self.file
        return f"  {YELLOW}{self.code}{RESET} {rel}:{self.line} — {self.message}"


def check_ts1_manual_mutex(filepath: Path, lines: list[str]) -> list[Violation]:
    """TS-1: Detect manual _mutex.lock() / _mutex.unlock() without QMutexLocker."""
    violations = []
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if re.search(r'\._mutex\.lock\(\)', stripped) and 'QMutexLocker' not in stripped:
            violations.append(Violation(
                "TS-1", filepath, i,
                "Manual _mutex.lock() — use QMutexLocker(self._mutex) instead",
                "locker = QMutexLocker(self._mutex)"
            ))
    return violations


def check_ts2_non_daemon_thread(filepath: Path, lines: list[str]) -> list[Violation]:
    """TS-2: Detect threading.Thread without daemon=True."""
    violations = []
    for i, line in enumerate(lines, 1):
        if 'threading.Thread(' in line and 'daemon' not in line:
            violations.append(Violation(
                "TS-2", filepath, i,
                "threading.Thread without daemon=True — may prevent clean exit",
                "Add daemon=True to Thread constructor"
            ))
    return violations


def check_ts3_assert_runtime(filepath: Path, lines: list[str]) -> list[Violation]:
    """TS-3: Detect assert used for runtime validation (not in tests)."""
    violations = []
    if "test_" in filepath.name:
        return violations  # Skip test files
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("assert ") and "is not None" in stripped:
            violations.append(Violation(
                "TS-3", filepath, i,
                "assert for runtime null check — stripped by python -O",
                "Use 'if x is None: return' instead"
            ))
    return violations


def check_ts4_lazy_getattr(filepath: Path, lines: list[str]) -> list[Violation]:
    """TS-4: getattr(self, '_...', ...) in files that use threading."""
    violations = []
    has_threading = any("threading" in line or "QMutex" in line for line in lines)
    if not has_threading:
        return violations
    for i, line in enumerate(lines, 1):
        if re.search(r'getattr\(self,\s*["\']_\w+["\'],', line):
            violations.append(Violation(
                "TS-4", filepath, i,
                "getattr(self, '_...') in threaded module — init in __init__ instead",
                "Initialize field in __init__ and access under lock"
            ))
    return violations


def main() -> int:
    show_hints = "--fix-hints" in sys.argv
    strict = "--strict" in sys.argv

    root = Path(__file__).parent.parent
    files = find_python_files(root)

    print(f"\n{CYAN}[SCAN] Thread-Safety Lint -- Scanning {len(files)} files{RESET}\n")

    all_violations: list[Violation] = []
    checks = [check_ts1_manual_mutex, check_ts2_non_daemon_thread,
              check_ts3_assert_runtime, check_ts4_lazy_getattr]

    for f in files:
        try:
            lines = f.read_text(encoding="utf-8").splitlines()
        except Exception:
            continue
        for check in checks:
            all_violations.extend(check(f, lines))

    if all_violations:
        # Group by code
        by_code: dict[str, list[Violation]] = {}
        for v in all_violations:
            by_code.setdefault(v.code, []).append(v)

        for code in sorted(by_code):
            vlist = by_code[code]
            print(f"{RED}[{code}] {len(vlist)} violation(s):{RESET}")
            for v in vlist:
                print(str(v))
                if show_hints and v.hint:
                    print(f"         [TIP] {v.hint}")
            print()

        total = len(all_violations)
        print(f"{YELLOW}[WARN] {total} thread-safety finding(s) -- review recommended{RESET}\n")
        return 1 if strict else 0
    else:
        print(f"{GREEN}[OK] 0 thread-safety violations -- clean!{RESET}\n")
        return 0


if __name__ == "__main__":
    sys.exit(main())
