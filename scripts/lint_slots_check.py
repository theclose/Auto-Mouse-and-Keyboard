"""
__slots__ Consistency Lint — Ensures Action subclasses define __slots__ correctly.

Derived from __slots__ implementation where 3 missing slots caused AttributeError:
  - ReadFileLine._cache
  - GroupAction._children
  - GroupAction._cancel_event

Usage:
    python scripts/lint_slots_check.py [--strict]

Rules:
    SLOT-1: Every Action subclass must declare __slots__
    SLOT-2: Every self.xxx = in __init__ must have matching slot (in class or parent)
    SLOT-3: Duplicate slot names between parent and child
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

SCAN_FILES = [
    "core/action.py",
    "core/scheduler.py",
    "modules/mouse.py",
    "modules/keyboard.py",
    "modules/image.py",
    "modules/pixel.py",
    "modules/system.py",
]


class Violation:
    def __init__(self, code: str, file: str, line: int, message: str):
        self.code = code
        self.file = file
        self.line = line
        self.message = message

    def __str__(self) -> str:
        return f"  {YELLOW}{self.code}{RESET} {self.file}:{self.line} — {self.message}"


def _get_slots(node: ast.ClassDef) -> set[str]:
    """Extract __slots__ tuple/list from a class definition."""
    for item in node.body:
        if isinstance(item, ast.Assign):
            for target in item.targets:
                if isinstance(target, ast.Name) and target.id == "__slots__":
                    if isinstance(item.value, ast.Tuple | ast.List):
                        return {
                            elt.value
                            for elt in item.value.elts
                            if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
                        }
    return set()


def _get_init_attrs(node: ast.ClassDef) -> list[tuple[str, int]]:
    """Get all self.xxx = ... assignments in __init__."""
    attrs = []
    for item in node.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == "__init__":
            for stmt in ast.walk(item):
                if isinstance(stmt, ast.Assign):
                    for target in stmt.targets:
                        if (isinstance(target, ast.Attribute)
                                and isinstance(target.value, ast.Name)
                                and target.value.id == "self"):
                            attrs.append((target.attr, stmt.lineno))
    return attrs


def _is_action_subclass(node: ast.ClassDef) -> bool:
    """Check if class appears to inherit from Action."""
    for base in node.bases:
        if isinstance(base, ast.Name) and base.id == "Action":
            return True
        if isinstance(base, ast.Attribute) and base.attr == "Action":
            return True
    return False


# Known base Action slots — these are inherited by all subclasses
BASE_ACTION_SLOTS = {
    "id", "delay_after", "repeat_count", "description",
    "enabled", "on_error", "color", "bookmarked", "last_duration_ms",
}


def scan_file(filepath: Path) -> list[Violation]:
    """Scan a single file for __slots__ violations."""
    violations = []
    try:
        source = filepath.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(filepath))
    except (SyntaxError, UnicodeDecodeError):
        return violations

    rel_path = filepath.as_posix()

    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        if not _is_action_subclass(node):
            continue

        slots = _get_slots(node)

        # SLOT-1: Action subclass must declare __slots__
        if not slots:
            has_slots_attr = any(
                isinstance(item, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == "__slots__" for t in item.targets)
                for item in node.body
            )
            if not has_slots_attr:
                violations.append(Violation(
                    "SLOT-1", rel_path, node.lineno,
                    f"class {node.name}(Action) missing __slots__ declaration",
                ))
                continue

        # SLOT-2: Every self.xxx in __init__ needs a slot
        init_attrs = _get_init_attrs(node)
        all_available = slots | BASE_ACTION_SLOTS

        for attr_name, attr_line in init_attrs:
            if attr_name not in all_available:
                violations.append(Violation(
                    "SLOT-2", rel_path, attr_line,
                    f"self.{attr_name} in {node.name}.__init__() has no matching slot",
                ))

        # SLOT-3: Duplicate slots with parent
        dupes = slots & BASE_ACTION_SLOTS
        if dupes:
            violations.append(Violation(
                "SLOT-3", rel_path, node.lineno,
                f"{node.name}.__slots__ duplicates parent slots: {dupes}",
            ))

    return violations


def main() -> int:
    strict = "--strict" in sys.argv
    root = Path(__file__).parent.parent

    print(f"\n{CYAN}[SCAN] __slots__ Consistency Lint — Scanning Action subclasses{RESET}\n")

    all_violations: list[Violation] = []

    for rel in SCAN_FILES:
        filepath = root / rel
        if filepath.exists():
            all_violations.extend(scan_file(filepath))

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
        print(f"{YELLOW}[WARN] {total} __slots__ finding(s){RESET}\n")
        return 1 if strict else 0
    else:
        print(f"{GREEN}[OK] 0 __slots__ violations — all Action subclasses consistent!{RESET}\n")
        return 0


if __name__ == "__main__":
    sys.exit(main())
