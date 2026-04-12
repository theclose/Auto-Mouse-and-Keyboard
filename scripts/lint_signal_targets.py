"""
Signal-Target Lint — Verifies .connect(self._method) targets actually exist.

Catches "phantom method" bugs where a signal is connected to a method
that was never defined (e.g. self._on_record_toggle).

Usage:
    python scripts/lint_signal_targets.py

Derived from BS-2 audit finding: 89 .connect() calls in main_window.py
were never verified by any QA gate.
"""

import ast
import sys
from pathlib import Path

# ANSI
RED = "\033[91m"
GREEN = "\033[92m"
RESET = "\033[0m"

# Qt base methods that won't appear as def in our code but are valid targets
QT_BASE_METHODS = {
    "close", "show", "hide", "accept", "reject", "update", "repaint",
    "deleteLater", "setEnabled", "setDisabled", "setVisible",
    "expandAll", "collapseAll", "clearSelection", "reset",
    "setFocus", "raise_", "lower", "showNormal", "showMaximized",
    "showMinimized", "showFullScreen", "activateWindow",
}

SCAN_DIRS = ["gui"]


def scan_file(filepath: Path) -> list[str]:
    """Scan a single Python file for .connect(self._xxx) with missing targets."""
    try:
        source = filepath.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(filepath))
    except (SyntaxError, UnicodeDecodeError):
        return []

    # Collect all method names defined in this file
    defined_methods: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            defined_methods.add(node.name)

    errors: list[str] = []

    for node in ast.walk(tree):
        # Match: xxx.connect(self._yyy) or xxx.connect(self.yyy)
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute) or func.attr != "connect":
            continue
        if not node.args:
            continue

        arg = node.args[0]

        # Case 1: .connect(self._method)
        if (isinstance(arg, ast.Attribute)
                and isinstance(arg.value, ast.Name)
                and arg.value.id == "self"):
            target = arg.attr
            if target not in defined_methods and target not in QT_BASE_METHODS:
                errors.append(
                    f"{filepath}:{node.lineno}  .connect(self.{target})"
                    f" — method '{target}' not defined in this file"
                )

    return errors


def main() -> int:
    all_errors: list[str] = []

    for scan_dir in SCAN_DIRS:
        root = Path(scan_dir)
        if not root.exists():
            continue
        for py_file in sorted(root.rglob("*.py")):
            if "__pycache__" in str(py_file):
                continue
            all_errors.extend(scan_file(py_file))

    if all_errors:
        print(f"{RED}Signal target errors found:{RESET}")
        for err in all_errors:
            print(f"  {RED}{err}{RESET}")
        return 1

    print(f"{GREEN}OK: All signal .connect() targets verified{RESET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
