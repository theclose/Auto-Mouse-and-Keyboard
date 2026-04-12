"""
Shortcut Conflict Lint — Detects duplicate keyboard shortcut bindings across files.

Derived from real bug: Del key was bound in 3 places simultaneously
(main_window.py toolbar, main_window.py QShortcut, action_list_panel.py button)
causing unpredictable behavior.

Usage:
    python scripts/lint_shortcut_conflicts.py [--strict]

Rules:
    SC-1: Same keyboard shortcut bound in multiple locations
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

SCAN_DIRS = ["gui"]
EXCLUDE_DIRS = {"__pycache__", ".venv", "tests", "scripts", "dist"}

# Patterns that assign keyboard shortcuts
_PATTERNS = [
    # .setShortcut(QKeySequence("Ctrl+Z")) or .setShortcut(QKeySequence.StandardKey.Delete)
    re.compile(r'\.setShortcut\s*\(\s*(?:QKeySequence\s*\()?\s*["\']?([^"\')\s]+)["\']?\s*\)?', re.IGNORECASE),
    # QShortcut(QKeySequence("Ctrl+Z"), self._tree)
    re.compile(r'QShortcut\s*\(\s*(?:QKeySequence\s*\()?\s*["\']([^"\']+)["\']', re.IGNORECASE),
    # QShortcut(QKeySequence(Qt.Key.Key_Delete), ...)
    re.compile(r'QShortcut\s*\(\s*QKeySequence\s*\(\s*(Qt\.Key\.\w+)', re.IGNORECASE),
    # .setShortcut(QKeySequence(Qt.Key.Key_Delete))
    re.compile(r'\.setShortcut\s*\(\s*QKeySequence\s*\(\s*(Qt\.Key\.\w+)', re.IGNORECASE),
    # QKeySequence.StandardKey.xxx
    re.compile(r'QKeySequence\.StandardKey\.(\w+)', re.IGNORECASE),
]


class Violation:
    def __init__(self, code: str, message: str, locations: list[str]):
        self.code = code
        self.message = message
        self.locations = locations

    def __str__(self) -> str:
        lines = [f"  {YELLOW}{self.code}{RESET} {self.message}"]
        for loc in self.locations:
            lines.append(f"         → {loc}")
        return "\n".join(lines)


def find_python_files(root: Path) -> list[Path]:
    files = []
    for scan_dir in SCAN_DIRS:
        d = root / scan_dir
        if d.exists():
            for f in d.rglob("*.py"):
                if not any(part in EXCLUDE_DIRS for part in f.parts):
                    files.append(f)
    return sorted(files)


def _normalize_key(key: str) -> str:
    """Normalize shortcut key to comparable form."""
    key = key.strip().strip('"').strip("'")
    # Qt.Key.Key_Delete → Delete
    key = re.sub(r'^Qt\.Key\.Key_', '', key)
    # QKeySequence.StandardKey.Delete → Delete
    key = re.sub(r'^QKeySequence\.StandardKey\.', '', key)
    return key.lower()


def scan_shortcuts(root: Path) -> list[Violation]:
    """Scan all GUI files for shortcut bindings, detect duplicates."""
    files = find_python_files(root)

    # key_name → list[(file, line, raw_match)]
    bindings: dict[str, list[tuple[str, int, str]]] = {}

    for filepath in files:
        try:
            lines = filepath.read_text(encoding="utf-8").splitlines()
        except Exception:
            continue

        rel = filepath.relative_to(root).as_posix()

        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue

            for pattern in _PATTERNS:
                match = pattern.search(line)
                if match:
                    raw_key = match.group(1)
                    norm_key = _normalize_key(raw_key)
                    if norm_key and len(norm_key) > 1:  # Skip single chars
                        bindings.setdefault(norm_key, []).append((rel, i, raw_key))

    violations = []
    for key, locs in sorted(bindings.items()):
        if len(locs) > 1:
            # Check if they're in different files (cross-file conflict)
            files_involved = {loc[0] for loc in locs}
            if len(files_involved) > 1:
                # Exclude dialog-scoped shortcuts: dialogs have their own
                # widget scope, so Escape/Enter in a dialog doesn't conflict
                # with the same key in main_window.
                dialog_files = {
                    "gui/action_editor.py",
                    "gui/settings_dialog.py",
                    "gui/help_dialog.py",
                    "gui/coordinate_picker.py",
                    "gui/region_picker.py",
                }
                non_dialog = {f for f in files_involved if f not in dialog_files}
                # Only report if 2+ non-dialog files bind the same key
                if len(non_dialog) > 1:
                    non_dialog_locs = [
                        f"{f}:{line} ({raw})"
                        for f, line, raw in locs if f not in dialog_files
                    ]
                    violations.append(Violation(
                        "SC-1",
                        f"Shortcut '{key}' bound in {len(non_dialog_locs)} locations "
                        f"across {len(non_dialog)} files",
                        non_dialog_locs,
                    ))

    return violations


def main() -> int:
    strict = "--strict" in sys.argv
    root = Path(__file__).parent.parent

    print(f"\n{CYAN}[SCAN] Shortcut Conflict Lint — Scanning GUI files{RESET}\n")

    violations = scan_shortcuts(root)

    if violations:
        for v in violations:
            print(f"{RED}{v}{RESET}")
            print()

        total = len(violations)
        print(f"{YELLOW}[WARN] {total} shortcut conflict(s) — review recommended{RESET}\n")
        return 1 if strict else 0
    else:
        print(f"{GREEN}[OK] 0 shortcut conflicts — clean!{RESET}\n")
        return 0


if __name__ == "__main__":
    sys.exit(main())
