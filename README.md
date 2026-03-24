# AutoMacro (by TungDo)

> **Desktop automation tool** — record, create, and run mouse + keyboard macros with visual flow control.

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![PyQt6](https://img.shields.io/badge/UI-PyQt6-41cd52.svg)](https://pypi.org/project/PyQt6/)
[![Tests](https://img.shields.io/badge/Tests-558%20passing-brightgreen.svg)](#testing)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Linting: Ruff](https://img.shields.io/badge/linting-ruff-261230.svg)](https://github.com/astral-sh/ruff)

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

## Development Setup

```bash
# Install dev dependencies (linting, testing, type checking)
pip install -r requirements-dev.txt

# Format code (Black)
python -m black core/ gui/ modules/ main.py

# Lint (Ruff)
python -m ruff check core/ gui/ modules/ main.py

# Type check (Mypy)
python -m mypy core/ gui/ modules/ main.py --ignore-missing-imports

# Run full test suite
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
│   ├── undo_commands.py   # Undo/redo stack (including sub-actions)
│   ├── smart_hints.py     # Recursive macro analysis engine
│   └── ...                # autosave, crash_handler, retry, secure, etc.
├── gui/                   # PyQt6 user interface
│   ├── main_window.py     # Main app window
│   ├── action_editor.py   # Action create/edit dialog
│   ├── action_tree_model.py # Tree view model (nested composites)
│   └── ...                # styles, tray, settings, panels, etc.
├── modules/               # 24 atomic action types
│   ├── mouse.py           # 6 mouse actions
│   ├── keyboard.py        # 4 keyboard actions
│   ├── image.py           # 4 image actions
│   ├── pixel.py           # 2 pixel actions
│   └── system.py          # 8 system actions
└── tests/                 # 558 tests across 27 files
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

**Current status:** 558 tests, 27 files, 0 failures.

## Performance

Measured on Windows 10, Python 3.11.5, Intel x64:

| Metric | Value |
|--------|-------|
| Baseline RAM | 17 MB |
| After all imports | 61 MB |
| With MainWindow (idle) | 74 MB |
| EXE idle | ~160 MB |
| Window startup | 27 ms |
| Action creation | 892K ops/sec |
| Serialize 1K actions | 1.4 ms |
| Deserialize 1K actions | 0.8 ms |
| Smart Hints (500 actions) | 0.2 ms |
| EXE size | 7.8 MB |
| Total dist folder | 265 MB |

## Building

```bash
# Build standalone EXE (PyInstaller)
python -m PyInstaller autopilot.spec
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development guidelines.

## License

MIT License — © TungDo
