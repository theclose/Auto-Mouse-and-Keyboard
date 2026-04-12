"""
Memory Pattern Lint — Scans for common memory-related anti-patterns.

Derived from real bugs fixed in AutoMacro audit sessions:
  - QPixmap leak in ImageCaptureOverlay
  - 33MB numpy array churn in ImagePreviewWidget._do_scan()
  - Per-frame QPixmap.copy() in paintEvent

Usage:
    python scripts/lint_memory_patterns.py [--strict]

Rules:
    MEM-1: QPixmap.copy() or QImage.copy() inside paintEvent (per-frame alloc)
    MEM-2: cv2.cvtColor inside a loop body (array churn)
    MEM-3: Large numpy allocation pattern inside loop (np.array, np.zeros, etc.)
    MEM-4: QPixmap/QImage constructed without cleanup in non-__init__ method
"""

import ast
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


# ── MEM-1: .copy() on QPixmap/QImage inside paintEvent ──────────────

def check_mem1_copy_in_paint(filepath: Path, lines: list[str]) -> list[Violation]:
    """MEM-1: QPixmap/QImage .copy() inside paintEvent → per-frame allocation."""
    violations = []
    in_paint = False
    indent_level = 0

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if re.match(r"def paintEvent\s*\(", stripped):
            in_paint = True
            indent_level = len(line) - len(line.lstrip())
            continue
        if in_paint:
            current_indent = len(line) - len(line.lstrip()) if stripped else indent_level + 1
            if stripped and current_indent <= indent_level and not stripped.startswith("#"):
                in_paint = False
                continue
            if stripped.startswith("#"):
                continue
            if re.search(r"\.(copy|scaled)\s*\(", stripped) and any(
                kw in stripped for kw in ("Pixmap", "pixmap", "Image", "image", "_screenshot", "src")
            ):
                violations.append(Violation(
                    "MEM-1", filepath, i,
                    "QPixmap/QImage .copy() inside paintEvent — per-frame allocation",
                    "Use painter.drawPixmap(targetRect, src, srcRect) instead",
                ))
    return violations


# ── MEM-2: cv2.cvtColor inside loop ─────────────────────────────────

def check_mem2_cvtcolor_in_loop(filepath: Path, source: str) -> list[Violation]:
    """MEM-2: cv2.cvtColor inside a loop → repeated large array creation."""
    violations = []
    try:
        tree = ast.parse(source, filename=str(filepath))
    except SyntaxError:
        return violations

    loop_bodies: list[tuple[int, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.For, ast.While)):
            start = node.lineno
            end = max(getattr(n, "lineno", start) for n in ast.walk(node))
            loop_bodies.append((start, end))

    lines = source.splitlines()
    for i, line in enumerate(lines, 1):
        if "cvtColor" in line and "cv2" in line:
            for ls, le in loop_bodies:
                if ls <= i <= le:
                    violations.append(Violation(
                        "MEM-2", filepath, i,
                        "cv2.cvtColor inside loop — creates new array each iteration",
                        "Pre-allocate buffer or use grayscale capture directly",
                    ))
                    break
    return violations


# ── MEM-3: numpy allocation inside loop ──────────────────────────────

_NP_ALLOC = re.compile(r"np\.(array|zeros|ones|empty|full|copy)\s*\(")


def check_mem3_numpy_in_loop(filepath: Path, source: str) -> list[Violation]:
    """MEM-3: Large numpy allocation inside tight loop."""
    violations = []
    try:
        tree = ast.parse(source, filename=str(filepath))
    except SyntaxError:
        return violations

    loop_bodies: list[tuple[int, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.For, ast.While)):
            start = node.lineno
            end = max(getattr(n, "lineno", start) for n in ast.walk(node))
            loop_bodies.append((start, end))

    lines = source.splitlines()
    for i, line in enumerate(lines, 1):
        if _NP_ALLOC.search(line):
            for ls, le in loop_bodies:
                if ls <= i <= le:
                    violations.append(Violation(
                        "MEM-3", filepath, i,
                        "numpy allocation inside loop — potential array churn",
                        "Pre-allocate outside loop or reuse buffer",
                    ))
                    break
    return violations


# ── MEM-4: QPixmap/QImage in non-__init__ without cleanup ───────────

_QT_IMAGE_CTOR = re.compile(r"(QPixmap|QImage)\s*\(")


def check_mem4_qt_image_no_cleanup(filepath: Path, source: str) -> list[Violation]:
    """MEM-4: QPixmap/QImage created in method without cleanup in same scope."""
    violations = []
    try:
        tree = ast.parse(source, filename=str(filepath))
    except SyntaxError:
        return violations

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name == "__init__":
            continue

        func_source_lines = source.splitlines()[node.lineno - 1: node.end_lineno or node.lineno]
        func_text = "\n".join(func_source_lines)

        if _QT_IMAGE_CTOR.search(func_text):
            has_cleanup = any(kw in func_text for kw in (
                "deleteLater", "del ", "= None", ".fill(", "return",
                "self._screenshot", "self._pixmap",
            ))
            if not has_cleanup:
                violations.append(Violation(
                    "MEM-4", filepath, node.lineno,
                    f"QPixmap/QImage created in {node.name}() without visible cleanup",
                    "Store as self.field and release in close()/cleanup, or use 'del' explicitly",
                ))
    return violations


def main() -> int:
    strict = "--strict" in sys.argv
    root = Path(__file__).parent.parent
    files = find_python_files(root)

    print(f"\n{CYAN}[SCAN] Memory Pattern Lint — Scanning {len(files)} files{RESET}\n")

    all_violations: list[Violation] = []

    for f in files:
        try:
            source = f.read_text(encoding="utf-8")
            lines = source.splitlines()
        except Exception:
            continue

        all_violations.extend(check_mem1_copy_in_paint(f, lines))
        all_violations.extend(check_mem2_cvtcolor_in_loop(f, source))
        all_violations.extend(check_mem3_numpy_in_loop(f, source))
        all_violations.extend(check_mem4_qt_image_no_cleanup(f, source))

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
        print(f"{YELLOW}[WARN] {total} memory pattern finding(s){RESET}\n")
        return 1 if strict else 0
    else:
        print(f"{GREEN}[OK] 0 memory pattern violations — clean!{RESET}\n")
        return 0


if __name__ == "__main__":
    sys.exit(main())
