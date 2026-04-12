"""
Getattr Typo Lint — Detects getattr() calls on Action objects with attribute
names that don't exist in any Action subclass __slots__.

Derived from real bugs:
  - smart_hints.py: getattr(action, "template_path", "") — real attr is "image_path"
  - smart_hints.py: getattr(action, "loop_count", 1)     — real attr is "repeat_count"

Usage:
    python scripts/lint_getattr_typos.py [--strict]

Rules:
    GA-1: getattr(action/self, "attr_name", default) where:
          - Variable name suggests it's an Action object (action, act, child, a)
          - OR it's self.xxx in an Action subclass file
          - AND attr_name is not in any known Action __slots__

Scoped to: core/smart_hints.py, core/scheduler.py, core/engine.py,
           gui/action_tree_model.py, gui/action_editor.py, gui/main_window.py
           (files that access Action attributes via getattr)
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

# Files that define Action subclasses with __slots__
ACTION_DEF_FILES = [
    "core/action.py",
    "core/scheduler.py",
    "modules/mouse.py",
    "modules/keyboard.py",
    "modules/image.py",
    "modules/pixel.py",
    "modules/system.py",
]

# Files known to use getattr on Action objects — targeted scan
TARGET_FILES = [
    "core/smart_hints.py",
    "core/scheduler.py",
    "core/engine.py",
    "gui/action_tree_model.py",
    "gui/action_editor.py",
    "gui/main_window.py",
    "gui/panels/properties_panel.py",
]

# Variable names that typically hold Action objects
ACTION_VAR_NAMES = {
    "action", "act", "a", "child", "parent_action",
    "then_action", "else_action", "sub_action",
    "source_action", "target_action", "new_action",
    "restored", "original",
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


def collect_all_action_slots(root: Path) -> set[str]:
    """Collect ALL __slots__ from ALL Action subclasses."""
    all_slots: set[str] = set()

    for rel in ACTION_DEF_FILES:
        filepath = root / rel
        if not filepath.exists():
            continue
        try:
            source = filepath.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(filepath))
        except (SyntaxError, UnicodeDecodeError):
            continue

        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            for item in node.body:
                if isinstance(item, ast.Assign):
                    for target in item.targets:
                        if isinstance(target, ast.Name) and target.id == "__slots__":
                            if isinstance(item.value, (ast.Tuple, ast.List)):
                                for elt in item.value.elts:
                                    if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                                        all_slots.add(elt.value)

    # Also add base Action attrs and properties
    all_slots.update({
        "ACTION_TYPE", "is_composite", "has_branches",
        "children", "then_children", "else_children",
        "enabled", "delay_after", "description", "on_error",
        "repeat_count", "color", "bookmarked", "last_duration_ms", "id",
    })

    return all_slots


# Pattern: getattr(var_name, "attr_name", default)
_GETATTR_RE = re.compile(
    r'getattr\s*\(\s*(\w+)\s*,\s*["\'](\w+)["\']\s*,'
)


def check_ga1(filepath: Path, source: str, known_attrs: set[str]) -> list[Violation]:
    """GA-1: getattr on Action variable with unknown attribute name."""
    violations = []
    lines = source.splitlines()

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue

        match = _GETATTR_RE.search(line)
        if not match:
            continue

        var_name = match.group(1)
        attr_name = match.group(2)

        # Only check if variable name looks like an Action object
        if var_name not in ACTION_VAR_NAMES:
            continue

        # Skip dunder attrs
        if attr_name.startswith("__") and attr_name.endswith("__"):
            continue

        # Check against known slots (with/without leading underscore)
        candidates = {attr_name, f"_{attr_name}", attr_name.lstrip("_")}
        if candidates & known_attrs:
            continue

        # Find similar names for hint
        similar = _find_similar(attr_name, known_attrs)
        violations.append(Violation(
            "GA-1", filepath, i,
            f'getattr({var_name}, "{attr_name}", ...) — not in any Action __slots__',
            f"Did you mean: {similar}" if similar else "No similar attribute found",
        ))

    return violations


def _find_similar(name: str, known: set[str], max_results: int = 3) -> str:
    """Find similar attribute names for hint."""
    candidates = []
    name_clean = name.lower().replace("_", "")
    for k in sorted(known):
        k_clean = k.lower().replace("_", "")
        if name_clean in k_clean or k_clean in name_clean:
            candidates.append(k)
    return ", ".join(candidates[:max_results])


def main() -> int:
    strict = "--strict" in sys.argv
    root = Path(__file__).parent.parent

    print(f"\n{CYAN}[SCAN] Getattr Typo Lint — Collecting Action __slots__{RESET}")
    known_attrs = collect_all_action_slots(root)
    print(f"  Found {len(known_attrs)} known attributes\n")

    all_violations: list[Violation] = []

    for rel in TARGET_FILES:
        filepath = root / rel
        if not filepath.exists():
            continue
        try:
            source = filepath.read_text(encoding="utf-8")
        except Exception:
            continue
        all_violations.extend(check_ga1(filepath, source, known_attrs))

    if all_violations:
        print(f"{RED}[GA-1] {len(all_violations)} violation(s):{RESET}")
        for v in all_violations:
            print(str(v))
            if v.hint:
                print(f"         [TIP] {v.hint}")
        print()
        print(f"{YELLOW}[WARN] {len(all_violations)} getattr typo finding(s){RESET}\n")
        return 1 if strict else 0
    else:
        print(f"{GREEN}[OK] 0 getattr typo violations — clean!{RESET}\n")
        return 0


if __name__ == "__main__":
    sys.exit(main())
