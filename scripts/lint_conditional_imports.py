"""
Conditional Import Lint — Detects imports inside if/try blocks that are
used on other code paths, risking NameError/UnboundLocalError.

Derived from real bug: `_on_copy_actions()` imported `json` inside
`if node.parent:` block, but the else branch also used `json` → crash.

Usage:
    python scripts/lint_conditional_imports.py [--strict]

Rules:
    CI-1: `import xxx` inside if/try body, AND `xxx` used in the SAME
          function but OUTSIDE that conditional block.

Excludes (not bugs):
    - Lazy imports of PyQt6 classes (QColor, QFont etc.) — performance pattern
    - Imports inside try/except ImportError — optional dependency pattern
    - Module-level conditional imports (if TYPE_CHECKING:)
"""

import ast
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

# Known safe lazy-import patterns (performance optimization, not bugs)
SAFE_IMPORT_NAMES = {
    "QColor", "QFont", "QBrush", "QPen", "QIcon", "QPixmap", "QImage",
    "QCursor", "QPainter", "QLinearGradient", "QRadialGradient",
    "QAction", "QMenu", "QMessageBox", "QFileDialog", "QInputDialog",
    "QApplication",
}


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


def _get_imported_names(node: ast.Import | ast.ImportFrom) -> list[str]:
    """Extract the bound names from an import statement."""
    names = []
    if isinstance(node, ast.Import):
        for alias in node.names:
            names.append(alias.asname or alias.name.split(".")[0])
    elif isinstance(node, ast.ImportFrom):
        for alias in node.names:
            names.append(alias.asname or alias.name)
    return names


def _is_in_try_except_importerror(node: ast.AST, func: ast.FunctionDef) -> bool:
    """Check if node is inside try/except ImportError (optional dependency pattern)."""
    for item in ast.walk(func):
        if isinstance(item, ast.Try):
            for handler in item.handlers:
                if handler.type is not None:
                    if isinstance(handler.type, ast.Name) and handler.type.id in (
                        "ImportError", "ModuleNotFoundError"
                    ):
                        for sub in ast.walk(item):
                            if sub is node:
                                return True
    return False


def check_ci1(filepath: Path, source: str) -> list[Violation]:
    """CI-1: Import inside if/try block, same name used elsewhere in function."""
    violations = []
    try:
        tree = ast.parse(source, filename=str(filepath))
    except SyntaxError:
        return violations

    for func in ast.walk(tree):
        if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        # Phase 1: Find imports inside if/try blocks within this function
        conditional_imports: dict[str, int] = {}  # name -> lineno

        for block in ast.walk(func):
            if not isinstance(block, (ast.If, ast.Try)):
                continue
            for child in ast.walk(block):
                if not isinstance(child, (ast.Import, ast.ImportFrom)):
                    continue

                # Skip try/except ImportError pattern
                if isinstance(block, ast.Try) and _is_in_try_except_importerror(child, func):
                    continue

                names = _get_imported_names(child)
                for name in names:
                    # Skip known safe lazy imports (QColor, QFont, etc.)
                    if name in SAFE_IMPORT_NAMES:
                        continue
                    conditional_imports[name] = child.lineno

        if not conditional_imports:
            continue

        # Phase 2: Check if same name is referenced on a DIFFERENT line
        # (meaning it's used outside the import's conditional block)
        for cond_name, import_line in conditional_imports.items():
            used_elsewhere = False
            for child in ast.walk(func):
                if isinstance(child, ast.Name) and child.id == cond_name:
                    if child.lineno != import_line:
                        used_elsewhere = True
                        break

            if used_elsewhere:
                violations.append(Violation(
                    "CI-1", filepath, import_line,
                    f"`import {cond_name}` inside conditional in {func.name}() "
                    f"— may cause NameError on other branches",
                    "Move import to top of function or module level",
                ))

    return violations


def main() -> int:
    strict = "--strict" in sys.argv
    root = Path(__file__).parent.parent
    files = find_python_files(root)

    print(f"\n{CYAN}[SCAN] Conditional Import Lint — Scanning {len(files)} files{RESET}\n")

    all_violations: list[Violation] = []
    for f in files:
        try:
            source = f.read_text(encoding="utf-8")
        except Exception:
            continue
        all_violations.extend(check_ci1(f, source))

    if all_violations:
        print(f"{RED}[CI-1] {len(all_violations)} violation(s):{RESET}")
        for v in all_violations:
            print(str(v))
            if v.hint:
                print(f"         [TIP] {v.hint}")
        print()
        print(f"{YELLOW}[WARN] {len(all_violations)} conditional import finding(s){RESET}\n")
        return 1 if strict else 0
    else:
        print(f"{GREEN}[OK] 0 conditional import violations — clean!{RESET}\n")
        return 0


if __name__ == "__main__":
    sys.exit(main())
