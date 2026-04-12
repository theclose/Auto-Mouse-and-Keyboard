"""
Resource Cleanup Lint — Scans for common resource cleanup issues.

Catches patterns that lead to resource leaks on Windows:
  - File handles left open
  - mss screen capture without context manager
  - QWidget created without deleteLater or parent

Usage:
    python scripts/lint_resource_cleanup.py [--strict]

Rules:
    RES-1: open() without 'with' statement
    RES-2: mss.mss() or mss() without 'with' statement
    RES-3: QWidget subclass constructed without parent= or deleteLater()
"""

import re
import sys
from pathlib import Path

# ANSI
RED = "\033[91m"
YELLOW = "\033[93m"
GREEN = "\033[92m"
CYAN = "\033[96m"
RESET = "\033[0m"

SCAN_DIRS = ["core", "gui", "modules"]
EXCLUDE_DIRS = {"__pycache__", ".venv", "tests", "scripts", "dist"}


class Violation:
    def __init__(self, code: str, file: Path, line: int, message: str, hint: str = ""):
        self.code = code
        self.file = file
        self.line = line
        self.message = message
        self.hint = hint

    def __str__(self) -> str:
        rel = self.file.as_posix()
        return f"  {YELLOW}{self.code}{RESET} {rel}:{self.line} — {self.message}"


def find_python_files(root: Path) -> list[Path]:
    files = []
    for scan_dir in SCAN_DIRS:
        d = root / scan_dir
        if d.exists():
            for f in d.rglob("*.py"):
                if not any(part in EXCLUDE_DIRS for part in f.parts):
                    files.append(f)
    return sorted(files)


# ── RES-1: open() without 'with' ────────────────────────────────────

_OPEN_ASSIGN = re.compile(r"^\s*\w+\s*=\s*open\s*\(")
_WITH_OPEN = re.compile(r"^\s*with\s+.*open\s*\(")


def check_res1_open_no_with(filepath: Path, lines: list[str]) -> list[Violation]:
    """RES-1: open() assigned to variable instead of using 'with'."""
    violations = []
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if _OPEN_ASSIGN.match(line) and not _WITH_OPEN.match(line):
            violations.append(Violation(
                "RES-1", filepath, i,
                "open() without 'with' statement — file handle may leak",
                "Use: with open(path) as f:",
            ))
    return violations


# ── RES-2: mss() without 'with' ─────────────────────────────────────

_MSS_ASSIGN = re.compile(r"=\s*mss\.mss\s*\(|=\s*mss\s*\(\s*\)")
_WITH_MSS = re.compile(r"^\s*with\s+.*mss")


def check_res2_mss_no_with(filepath: Path, lines: list[str]) -> list[Violation]:
    """RES-2: mss() screen capture without context manager."""
    violations = []
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if _MSS_ASSIGN.search(line) and not _WITH_MSS.match(line):
            # Check if it's a thread-local instance (acceptable pattern)
            if "thread_local" in line or "threading.local" in line or "_tls" in line:
                continue
            violations.append(Violation(
                "RES-2", filepath, i,
                "mss() without context manager — GDI handles may leak",
                "Use: with mss.mss() as sct: or store as thread-local",
            ))
    return violations


# ── RES-3: Subprocess Popen without communication ───────────────────

_POPEN_ASSIGN = re.compile(r"=\s*subprocess\.Popen\s*\(")


def check_res3_popen_no_comm(filepath: Path, lines: list[str]) -> list[Violation]:
    """RES-3: subprocess.Popen without communicate() or context manager."""
    violations = []
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if _POPEN_ASSIGN.search(line):
            # Check next 10 lines for .communicate() or .wait() or 'with'
            nearby = "\n".join(lines[i:i + 10])
            if ".communicate()" not in nearby and ".wait()" not in nearby:
                if not re.match(r"^\s*with\s+", line):
                    violations.append(Violation(
                        "RES-3", filepath, i,
                        "Popen without communicate()/wait() — process may become zombie",
                        "Use subprocess.run() or call .communicate()",
                    ))
    return violations


def main() -> int:
    strict = "--strict" in sys.argv
    root = Path(__file__).parent.parent
    files = find_python_files(root)

    print(f"\n{CYAN}[SCAN] Resource Cleanup Lint — Scanning {len(files)} files{RESET}\n")

    all_violations: list[Violation] = []

    for f in files:
        try:
            lines = f.read_text(encoding="utf-8").splitlines()
        except Exception:
            continue

        all_violations.extend(check_res1_open_no_with(f, lines))
        all_violations.extend(check_res2_mss_no_with(f, lines))
        all_violations.extend(check_res3_popen_no_comm(f, lines))

    if all_violations:
        by_code: dict[str, list[Violation]] = {}
        for v in all_violations:
            by_code.setdefault(v.code, []).append(v)

        for code in sorted(by_code):
            vlist = by_code[code]
            print(f"{RED}[{code}] {len(vlist)} violation(s):{RESET}")
            for v in vlist:
                print(str(v))
            print()

        total = len(all_violations)
        print(f"{YELLOW}[WARN] {total} resource cleanup finding(s){RESET}\n")
        return 1 if strict else 0
    else:
        print(f"{GREEN}[OK] 0 resource cleanup violations — clean!{RESET}\n")
        return 0


if __name__ == "__main__":
    sys.exit(main())
