# AutoMacro v3.0.0 (by TungDo)

> **Trusted local desktop automation tool** — record, create, and run mouse + keyboard macros with visual flow control, image recognition, and preflight validation.

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![PyQt6](https://img.shields.io/badge/UI-PyQt6-41cd52.svg)](https://pypi.org/project/PyQt6/)
[![Tests](https://img.shields.io/badge/Tests-880%20passing-brightgreen.svg)](#testing)
[![QA](https://img.shields.io/badge/QA-11%2F11%20PASS-brightgreen.svg)](#testing)

## Features

| Category | Capabilities |
|----------|-------------|
| **Mouse** | Click, double-click, right-click, move, drag, scroll (6 types) |
| **Keyboard** | Key press, combos, text typing, hotkeys (4 types) |
| **Image** | Wait for image, click on image, image exists, screenshot (4 types) |
| **Pixel** | Check pixel color, wait for color change (2 types) |
| **Flow Control** | Loop, If Image Found, If Pixel Color, If Variable (4 types) |
| **Variables** | Set, increment, arithmetic, eval expressions, split strings (3 types) |
| **System** | Window activation, file I/O, clipboard, run command, run sub-macro, OCR (8 types) |
| **Security** | DPAPI-encrypted text input (Fernet), path traversal prevention |
| **Preflight** | 11-rule smart analysis — blocks errors, warns issues before execution |

**34 action types** total across **7 modules**.

### Trust Model

AutoMacro is a **trusted local automation tool** for personal and internal use. It is NOT a sandboxed environment:
- `RunCommand` uses `shell=True` (required for Windows CMD builtins)
- File actions allow absolute paths for flexibility
- `RunMacro` has additional guards: `.json` only, depth limit 10, path validation
- Secure text uses Windows DPAPI (Fernet encryption) — tied to machine + user account

## Quick Start

### From source
```bash
pip install -r requirements.txt
python main.py
```

### From EXE (end-user)
1. Download `AutoPilot/` folder from dist
2. Run `AutoPilot.exe`
3. Logs → `logs/autopilot.log`, Config → `config.json`, Macros → `macros/`

## Development Setup

```bash
# Install dev dependencies
pip install -r requirements-dev.txt

# Lint (Ruff)
python -m ruff check core/ gui/ modules/ main.py

# Run full QA (lint + tests + security scan)
python scripts/qa_check.py

# Run only tests
python -m pytest tests/ -q

# Build EXE
build.bat
```

### Adding a new Action type

1. Create action class in `modules/<category>.py` with `@register_action("type_name")`
2. Add `TYPE_ICON` class variable for auto-discovery  
3. Add editor support in `gui/action_editor.py`
4. Add test coverage in `tests/`
5. Update help content in `gui/help_content.py`

## Architecture

```
AutoMacro/
├── main.py                 # Entry point (no import side-effects)
├── core/
│   ├── action.py           # Action base class + registry
│   ├── app_paths.py        # Single source of truth for all paths
│   ├── engine.py           # Threaded macro executor (QThread)
│   ├── scheduler.py        # 7 flow control actions (composite pattern)
│   ├── smart_hints.py      # 11-rule preflight analyzer (recursive)
│   ├── recorder.py         # Mouse + keyboard recording
│   ├── secure.py           # DPAPI/Fernet encryption
│   ├── crash_handler.py    # Global exception handler with UI
│   ├── memory_manager.py   # 24/7 memory watchdog
│   └── ...                 # autosave, undo, event_bus, etc.
├── gui/                    # PyQt6 user interface
│   ├── main_window.py      # Main app (preflight + engine control)
│   ├── action_editor.py    # Action create/edit dialog
│   └── ...                 # styles, tray, settings, panels
├── modules/                # 27 atomic action types
│   ├── mouse.py            # 6 mouse actions
│   ├── keyboard.py         # 4 keyboard actions
│   ├── image.py            # 4 image actions
│   ├── pixel.py            # 2 pixel actions
│   └── system.py           # 8 system actions (+ RunCommand, SecureType)
├── scripts/
│   ├── qa_check.py         # 11-rule QA gatekeeper
│   └── test_*.py           # Stress tests
└── tests/                  # 880 tests across 27+ files
```

## Testing

```bash
# Full QA suite (lint + tests + security)
python scripts/qa_check.py

# Only unit tests
python -m pytest tests/ -q

# Stress tests (10 deep nested scenarios)
python scripts/test_deep_nested.py
```

**Current status:** 880 tests, 11/11 QA checks, 0 failures.

## Building

```bash
# Build standalone EXE (PyInstaller one-dir)
build.bat
# or manually:
python -m PyInstaller autopilot.spec
```

Output: `dist/AutoPilot/AutoPilot.exe`

## License

MIT License — © TungDo
