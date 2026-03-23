# AutoMacro (by TungDo)

> **Desktop automation tool** — record, create, and run mouse + keyboard macros with visual flow control.

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![PyQt6](https://img.shields.io/badge/UI-PyQt6-41cd52.svg)](https://pypi.org/project/PyQt6/)
[![Tests](https://img.shields.io/badge/Tests-448%20passing-brightgreen.svg)](#testing)

## Features

| Category | Capabilities |
|----------|-------------|
| **Mouse** | Click, double-click, right-click, move, drag, scroll (6 types) |
| **Keyboard** | Key press, combos, text typing, hotkeys (4 types) |
| **Image** | Wait for image, click on image, image exists, screenshot (4 types) |
| **Pixel** | Check pixel color, wait for color change (2 types) |
| **Flow Control** | Loop, If Image Found, If Pixel Color, If Variable (4 types) |
| **Variables** | Set, increment, arithmetic, eval expressions, split strings (3 types) |
| **System** | Window activation, file I/O, clipboard, run sub-macro, OCR (8 types) |
| **Security** | DPAPI-encrypted text input, path traversal prevention |

**31 action types** total across **7 modules**.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run the application
python main.py

# Run tests
python -m pytest tests/ -q
```

## Architecture

```
AutoMacro/
├── main.py                # Entry point
├── core/                  # Engine & logic
│   ├── action.py          # Action base class + registry
│   ├── engine.py          # Threaded macro executor
│   ├── scheduler.py       # 7 flow control actions (composite pattern)
│   ├── recorder.py        # Mouse + keyboard recording
│   └── ...                # autosave, crash_handler, retry, secure, etc.
├── gui/                   # PyQt6 user interface
│   ├── main_window.py     # Main app window
│   ├── action_editor.py   # Action create/edit dialog
│   ├── action_tree_model.py # v3.0 tree view model
│   └── ...                # styles, tray, settings, etc.
├── modules/               # 24 atomic action types
│   ├── mouse.py           # 6 mouse actions
│   ├── keyboard.py        # 4 keyboard actions
│   ├── image.py           # 4 image actions
│   ├── pixel.py           # 2 pixel actions
│   └── system.py          # 8 system actions
└── tests/                 # 448 tests across 15 files
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed design documentation.

## Testing

```bash
# Run full suite
python -m pytest tests/ -q

# Run specific test file
python -m pytest tests/test_action_tree_model.py -v

# Run with benchmark
python -m pytest tests/test_benchmarks.py --benchmark-only
```

**Current status:** 448 tests, 15 files, 0 failures.

## Building

```bash
# Build standalone EXE (PyInstaller)
python -m PyInstaller AutoMacro.spec
```

## Contributing

1. All action types use `@register_action("type_name")` — see `core/action.py`
2. Never duplicate `action_type` strings across files
3. Run `python -m pytest tests/ -q` before committing
4. Follow the Composite Pattern for flow control actions

## License

© TungDo — All rights reserved.
