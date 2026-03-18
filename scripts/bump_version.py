"""
Auto version bump script for AutoMacro.

Usage:
    python scripts/bump_version.py patch   # 1.0.0 → 1.0.1
    python scripts/bump_version.py minor   # 1.0.0 → 1.1.0
    python scripts/bump_version.py major   # 1.0.0 → 2.0.0
    python scripts/bump_version.py         # defaults to patch

Reads version.py, increments the specified part, writes back.
Returns the new version string to stdout for use in scripts.
"""

import re
import sys
import datetime
from pathlib import Path


VERSION_FILE = Path(__file__).parent.parent / "version.py"


def read_version() -> str:
    """Read current __version__ from version.py."""
    content = VERSION_FILE.read_text(encoding="utf-8")
    match = re.search(r'__version__\s*=\s*"([^"]+)"', content)
    if not match:
        raise ValueError(f"Cannot find __version__ in {VERSION_FILE}")
    return match.group(1)


def bump(version: str, part: str = "patch") -> str:
    """Bump a semantic version string."""
    parts = version.split(".")
    if len(parts) != 3:
        raise ValueError(f"Invalid version format: {version}")

    major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])

    if part == "major":
        major += 1
        minor = 0
        patch = 0
    elif part == "minor":
        minor += 1
        patch = 0
    else:  # patch
        patch += 1

    return f"{major}.{minor}.{patch}"


def write_version(new_version: str) -> None:
    """Update version.py with new version and build date."""
    content = VERSION_FILE.read_text(encoding="utf-8")

    # Update __version__
    content = re.sub(
        r'__version__\s*=\s*"[^"]+"',
        f'__version__ = "{new_version}"',
        content,
    )

    # Update __build_date__
    today = datetime.date.today().isoformat()
    content = re.sub(
        r'__build_date__\s*=\s*"[^"]+"',
        f'__build_date__ = "{today}"',
        content,
    )

    VERSION_FILE.write_text(content, encoding="utf-8")


def main() -> None:
    part = sys.argv[1] if len(sys.argv) > 1 else "patch"
    if part not in ("major", "minor", "patch"):
        print(f"Usage: {sys.argv[0]} [major|minor|patch]", file=sys.stderr)
        sys.exit(1)

    old = read_version()
    new = bump(old, part)
    write_version(new)
    print(f"{old} → {new}")


if __name__ == "__main__":
    main()
