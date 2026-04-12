# Auto Mouse & Keyboard — Architecture Guide

> **Version**: 3.0.0 · **Codebase**: 52 source files · **34 registered action types**
> **Framework**: PyQt6 (desktop), pyautogui + opencv (automation)
> **CI**: GitHub Actions (Ruff + pytest)

## Table of Contents
1. [System Overview](#system-overview)
2. [Core Layer](#core-layer)
3. [Modules Layer](#modules-layer)
4. [GUI Layer](#gui-layer)
5. [Action Registration & Import Order](#action-registration--import-order)
6. [Data Flow](#data-flow)
7. [Undo/Redo Framework](#undoredo-framework)
8. [Event-Driven Architecture](#event-driven-architecture)
9. [Security Architecture](#security-architecture)
10. [CI/CD Pipeline](#cicd-pipeline)
11. [Design Patterns](#design-patterns)
12. [File Size Map](#file-size-map)

---

## System Overview

```mermaid
graph TB
    subgraph Entry
        M[main.py]
    end

    subgraph GUI["gui/ — User Interface"]
        MW[main_window.py<br/>TreeView + Toolbar]
        CN[constants.py<br/>Theme & Icons]
        AE[action_editor.py<br/>Create/Edit Actions]
        ATM[action_tree_model.py<br/>QAbstractItemModel]
        RP[recording_panel.py<br/>Record Controls]
        SD[settings_dialog.py<br/>App Settings]
        ST[styles.py<br/>Theme System]
        TR[tray.py<br/>System Tray]
        CP[coordinate_picker.py<br/>XY Picker Overlay]
        IC[image_capture.py<br/>Screen Snip Tool]
        IP[image_preview_widget.py<br/>Image Preview]
        HD[help_dialog.py<br/>Action Help]
        HC[help_content.py<br/>Help HTML Data]
    end

    subgraph Panels["gui/panels/ — Dockable UI Panels"]
        ALP[action_list_panel.py]
        EXP[execution_panel.py]
        LP[log_panel.py]
        MMP[minimap_panel.py]
        PP[playback_panel.py]
        VP[variable_panel.py]
    end

    subgraph Core["core/ — Engine & Logic"]
        A[action.py<br/>Base Class + Registry]
        E[engine.py<br/>Macro Executor]
        S[scheduler.py<br/>7 Flow Actions]
        EC[execution_context.py<br/>Variables + State]
        ECtx[engine_context.py<br/>Thread-local Speed/Stop]
        R[recorder.py<br/>Input Recording]
        HK[hotkey_manager.py<br/>Global Hotkeys]
        UC[undo_commands.py<br/>Undo/Redo Commands]
        EB[event_bus.py<br/>Pub/Sub Events]
        SH[smart_hints.py<br/>Macro Analysis]
        MT[macro_templates.py<br/>Preset Templates]
        AS[autosave.py<br/>Auto-Save Timer]
        CH[crash_handler.py<br/>Exception Handler]
        MM[memory_manager.py<br/>Memory Monitor]
        PR[profiler.py<br/>Perf Timing]
        RT[retry.py<br/>Retry Decorator]
        SE[secure.py<br/>DPAPI Encryption]
    end

    subgraph Modules["modules/ — Atomic Actions"]
        MO[mouse.py — 6 types]
        KB[keyboard.py — 4 types]
        IM[image.py — 4 types]
        PX[pixel.py — 2 types]
        SY[system.py — 8 types]
        SC[screen.py — utilities]
    end

    M --> MW
    MW --> AE & RP & SD & TR
    MW --> ATM & Panels
    AE --> CP & IC & HD & IP
    HD --> HC
    MW --> E & R & HK & UC & AS
    E --> A & S & EC & ECtx
    S --> A
    A --> MO & KB & IM & PX & SY
    MW --> ST & EB & SH
```

---

## Core Layer

`core/` contains the engine, action model, and infrastructure services.

| File | Size | Key Classes | Purpose |
|------|------|-------------|---------|
| `action.py` | 11KB | `Action`, `DelayAction`, `register_action()`, `audit_registry()` | Base class, registry, serialization |
| `app_paths.py` | 1KB | `APP_DIR`, `LOG_DIR`, `CONFIG_PATH` | **Single source of truth** for all paths (no import side-effects) |
| `engine.py` | 15KB | `MacroEngine` | Threaded macro execution with pause/resume/stop, signals, `__current_macro_dir__` |
| `scheduler.py` | 37KB | `LoopBlock`, `IfImageFound`, `IfPixelColor`, `IfVariable`, `SetVariable`, `SplitString`, `Comment` | **7 flow control actions** (Composite Pattern) |
| `execution_context.py` | 8KB | `ExecutionContext` | Shared state: variables, image matches, system vars, interpolation |
| `engine_context.py` | 3KB | `set_speed()`, `get_context()`, `is_stopped()`, `scaled_sleep()` | Thread-local context helpers |
| `recorder.py` | 16KB | `Recorder` | Mouse + keyboard input recording with thread-safe snapshot API |
| `hotkey_manager.py` | 6KB | `HotkeyManager` | Win32 RegisterHotKey integration |
| `undo_commands.py` | 7KB | `AddActionCommand`, `DeleteActionsCommand`, `ReorderActionsCommand`, `CompositeChildrenCommand` | Qt QUndoCommand for action list + nested sub-action mutations |
| `event_bus.py` | 2KB | `EventBus` | Global publish/subscribe for decoupled GUI↔Core communication |
| `smart_hints.py` | 12KB | `analyze_hints()` | **11-rule** preflight analyzer: detects empty commands, plaintext secrets, missing paths, infinite loops, etc. (recursive) |
| `macro_templates.py` | 8KB | `get_templates()` | Preset macro templates (e.g., auto-clicker, form filler) |
| `autosave.py` | 3KB | `AutoSaveManager` | Timer-based auto-save with backup rotation |
| `crash_handler.py` | 6KB | `CrashHandler`, `CrashDialog` | Global sys.excepthook with crash report dialog |
| `memory_manager.py` | 6KB | `MemoryManager` | Memory monitoring + cleanup callbacks |
| `profiler.py` | 3KB | `PerformanceProfiler`, `get_profiler()` | Context-manager timing tracker |
| `retry.py` | 2KB | `retry()` decorator | Exponential backoff retry for transient failures |
| `secure.py` | 2KB | `encrypt()`, `decrypt()`, `is_encrypted()` | Windows DPAPI encryption for passwords |

---

## Modules Layer

`modules/` registers **24 atomic action types** via `@register_action()`.
Each module is imported at startup in `gui/main_window.py`.

| Module | Types | Count | Notes |
|--------|-------|-------|-------|
| `mouse.py` | mouse_click, mouse_double_click, mouse_right_click, mouse_move, mouse_drag, mouse_scroll | 6 | pyautogui-based, supports dynamic `${var}` coordinates |
| `keyboard.py` | key_press, key_combo, type_text, hotkey | 4 | pyautogui + SendInput |
| `image.py` | wait_for_image, click_on_image, image_exists, take_screenshot | 4 | OpenCV template matching |
| `pixel.py` | check_pixel_color, wait_for_color | 2 | Single-pixel fast check |
| `system.py` | activate_window, log_to_file, read_clipboard, read_file_line, write_to_file, secure_type_text, run_macro, run_command, capture_text | 9 | Window mgmt, file I/O, OCR |
| `screen.py` | *(no registered types)* | 0 | Screenshot utilities |

> **7 additional** flow control types are in `core/scheduler.py` (NOT modules/).
> **Total: 34 registered types** across all files.

---

## GUI Layer

### Main Components

| File | Size | Key Classes | Purpose |
|------|------|-------------|---------|
| `main_window.py` | 82KB | `MainWindow` | Main app: TreeView, toolbar, log panel, drag-drop, undo stack |
| `constants.py` | 2KB | `TYPE_ICONS` | Centralized action icons and colors |
| `action_editor.py` | 46KB | `ActionEditor` | Create/edit dialog: per-type param builders |
| `action_tree_model.py` | 12KB | `ActionTreeModel` | QAbstractItemModel for hierarchical action display (composites as tree nodes) |
| `settings_dialog.py` | 13KB | `SettingsDialog` | Hotkeys, speed, defaults, paths |
| `recording_panel.py` | 9KB | `RecordingPanel` | Record/pause/stop controls |
| `coordinate_picker.py` | 9KB | `CoordinatePickerOverlay` | Full-screen crosshair + magnifier + color preview |
| `image_preview_widget.py` | 5KB | `ImagePreviewWidget` | Image template preview with screen capture |
| `help_dialog.py` | 7KB | `HelpPopup` | Floating help window for action types |
| `help_content.py` | 36KB | `_ACTION_HELP` dict | Rich HTML help text with scenarios for all 34 types |
| `styles.py` | 12KB | `DARK_COLORS`, `get_stylesheet()` | Theme palette + QSS template engine |
| `tray.py` | 4KB | `SystemTrayManager` | System tray icon with state-colored indicator |
| `image_capture.py` | 5KB | `ImageCaptureOverlay` | Screen snipping for image templates |

### Dockable Panels (`gui/panels/`)

| File | Size | Purpose |
|------|------|---------|
| `action_list_panel.py` | 11KB | Alternative list view for actions |
| `playback_panel.py` | 6KB | Play/pause/stop controls with progress |
| `minimap_panel.py` | 6KB | Scrollable overview of all actions |
| `log_panel.py` | 4KB | Execution log output |
| `variable_panel.py` | 3KB | Live variable inspector (ExecutionContext) |
| `execution_panel.py` | 3KB | Engine state dashboard |

---

## Action Registration & Import Order

> ⚠️ **CRITICAL**: Import order determines which registration wins.
> If two files register the same `action_type`, the **LAST import wins** silently.
> `register_action()` now warns in log when a type is overwritten.

```python
# gui/main_window.py — import order (ALL modules must be imported here)
import modules.mouse        # 6 types
import modules.keyboard     # 4 types
import modules.image        # 4 types
import modules.pixel        # 2 types
import modules.system       # 8 types
import core.scheduler        # 7 types ← MUST be last (flow control)
```

**Rules:**
1. Each `action_type` string must be **globally unique** across ALL files
2. `register_action()` logs `WARNING` if a type is registered twice
3. Call `audit_registry()` at startup to verify (done in `main.py`)
4. **NEVER** create duplicate `@register_action()` for types already in `scheduler.py`

---

## Data Flow

### Create Action (User → Storage)
```
ActionEditor._on_type_changed()
    → _build_*_params() creates widgets
    → _collect_params() reads widget values → dict
    → get_action_class(type)(**params) → Action instance
    → UndoStack.push(AddActionCommand)
    → ActionTreeModel updated
    → engine.save_macro() → JSON file
```

### Execute Macro (Play)
```
MainWindow._on_play()
    → _preflight_check() — smart_hints blocks errors, warns warnings
    → MacroEngine.load_actions(deep_copy of _actions)
    → QThread: engine._run_action_list()
        → for action in actions:
            action.run()  → execute() + delay + repeat
            ├── Atomic: mouse.click, key.press, etc
            └── Composite: LoopBlock.execute()
                ├── for i in range(N):
                │   for sub in _sub_actions:
                │       sub.run()  ← recursive!
                └── IfImageFound.execute()
                    ├── found → run _then_actions
                    └── not_found → run _else_actions
    → Signals: progress_signal, step_signal, nested_step_signal
```

### Record (Input → Actions)
```
RecordingPanel → Recorder.start()
    → pynput listeners (mouse + keyboard)
    → Events filtered (skip hotkeys, debounce)
    → Recorder.stop()
    → List of Action objects (thread-safe snapshot via get_actions_snapshot())
    → MainWindow._actions.extend(recorded)
```

### Import/Export (JSON)
```
Save: action.to_dict() → {"type": "loop_block", "params": {..., "sub_actions": [...]}}
Load: Action.from_dict(data) → recursive deserialization
Format: {"version": "1.x", "actions": [...], "settings": {...}}
```

---

## Undo/Redo Framework

Built on `QUndoStack` with 4 command types:

| Command | Scope | Usage |
|---------|-------|-------|
| `AddActionCommand` | Top-level list | Insert/append actions |
| `DeleteActionsCommand` | Top-level list | Remove selected actions |
| `ReorderActionsCommand` | Top-level list | Drag-drop / move up-down |
| `CompositeChildrenCommand` | Nested children | Snapshot-based undo for sub-action mutations |

`CompositeChildrenCommand` uses a **snapshot strategy**: captures before/after state of `_sub_actions`, `_then_actions`, `_else_actions` as lists, and restores them on undo/redo. This avoids complex per-item tracking for deeply nested composites.

---

## Event-Driven Architecture

`core/event_bus.py` provides global publish/subscribe:

```python
from core.event_bus import EventBus
bus = EventBus.instance()
bus.subscribe("action_added", handler)
bus.publish("action_added", action=new_action)
```

Used for decoupling GUI panels from core logic (e.g., variable panel updates when engine sets variables).

---

## Security Architecture

```
User enters password in ActionEditor
    → SecureTypeText.__init__(encrypted_text=...)
    → core.secure.encrypt(password)  → "DPAPI:base64blob"
    → Stored encrypted in macro JSON
    → At runtime: core.secure.decrypt() → plaintext
    → pyautogui.typewrite(plaintext)
    → Log shows "****" only
```

**Implementation**: Windows DPAPI (`win32crypt.CryptProtectData`)
- Encrypted data is machine-bound (cannot decrypt on another PC)
- Fallback: plaintext if `win32crypt` not available
- Prefix: `"DPAPI:"` identifies encrypted values

---

## CI/CD Pipeline

`.github/workflows/ci.yml` runs on every push:

```yaml
steps:
  1. Black (formatting check)
  2. Ruff (linting — unused imports, style)
  3. Mypy (type checking — strict on core/)
  4. Thread-Safety Scan (scripts/lint_thread_safety.py)
  5. pytest (880 tests, QT_QPA_PLATFORM=offscreen)
```

Local development tools:
- `requirements-dev.txt`: black, ruff, mypy, pytest, pytest-benchmark
- `pyproject.toml`: centralised tool configs (mypy, ruff, pytest)

---

## Design Patterns

| Pattern | Where | Purpose |
|---------|-------|---------|
| **Command** | `Action` subclasses, `QUndoCommand` | Each action = self-contained command with execute/undo |
| **Registry** | `@register_action()` + `_ACTION_REGISTRY` | Type string → class lookup |
| **Composite** | `LoopBlock`, `IfImageFound`, `IfVariable`, `IfPixelColor` | Actions contain child action lists |
| **Builder** | `ActionEditor._build_*_params()` | Per-type widget construction |
| **Observer** | Qt signals/slots, `EventBus` | Loose coupling between components |
| **Singleton** | `MemoryManager.instance()`, `EventBus.instance()`, `get_profiler()` | Global singletons for services |
| **Decorator** | `@retry()`, `@register_action()` | Cross-cutting behavior |
| **Template Method** | `Action.run()` calls `execute()` | Base handles delay/repeat, subclass handles logic |
| **Strategy** | `_ACTION_HELP`, `ACTION_CATEGORIES` | Data-driven help and categories |
| **Snapshot** | `CompositeChildrenCommand` | Capture/restore sub-action lists for undo |
| **Pub/Sub** | `EventBus` | Decoupled cross-module communication |

---

## File Size Map

```
82KB  gui/main_window.py        ██████████████████████████████████████████ ← Largest
46KB  gui/action_editor.py      ███████████████████████
37KB  core/scheduler.py         ███████████████████
36KB  gui/help_content.py       ██████████████████
21KB  modules/system.py         ███████████
18KB  modules/image.py          █████████
16KB  core/recorder.py          ████████
14KB  modules/mouse.py          ███████
13KB  gui/settings_dialog.py    ███████
13KB  core/engine.py            ███████
12KB  gui/styles.py             ██████
12KB  gui/action_tree_model.py  ██████
11KB  gui/panels/action_list    ██████
11KB  core/action.py            ██████
 9KB  gui/recording_panel.py    █████
 9KB  gui/coordinate_picker.py  █████
 9KB  core/smart_hints.py       █████
 8KB  core/macro_templates.py   ████
 8KB  core/execution_context.py ████
 7KB  modules/keyboard.py       ████
 7KB  gui/help_dialog.py        ████
 7KB  core/undo_commands.py     ████
 6KB  modules/pixel.py          ███
 6KB  gui/panels/playback       ███
 6KB  gui/panels/minimap        ███
 6KB  core/memory_manager.py    ███
 6KB  core/hotkey_manager.py    ███
 6KB  core/crash_handler.py     ███
 5KB  main.py                   ███
 5KB  gui/image_preview_widget  ███
 5KB  gui/image_capture.py      ███
 4KB  modules/screen.py         ██
 4KB  gui/tray.py               ██
 4KB  gui/panels/log_panel      ██
 3KB  gui/panels/variable       ██
 3KB  gui/panels/execution      ██
 3KB  core/profiler.py          ██
 3KB  core/engine_context.py    ██
 3KB  core/autosave.py          ██
 2KB  core/secure.py            █
 2KB  core/retry.py             █
 2KB  core/event_bus.py         █
```
